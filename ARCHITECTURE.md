# Architecture

A map of how `news_analyze` actually fits together, so reviewing the system later
doesn't require re-deriving it. For build/run commands and the scraper-authoring
guide, see `CLAUDE.md`.

> **Reading tip:** the single most important mental model is the **two egress
> surfaces** (§3). Almost every performance/cost decision in this repo traces back
> to which surface a query lives on.

---

## 1. Component map

```
                         ┌──────────────────────────────────────────────┐
                         │                 Supabase                      │
                         │                                               │
  React frontend ──────► │  Edge Functions        PostgREST + RPCs       │
  (browser)              │   • search              • get_distinct_sources│
   • SearchPage          │   • graph               • get_article_stats   │
   • GraphPage           │   • bias                • get_bias_stats       │
   • BiasPage            │       │                 • match_articles       │
   • BrowsePage          │       │                     │                  │
   • TopicStats          │       └─────────┐   ┌───────┘                  │
                         │                 ▼   ▼                          │
                         │            Postgres (pgvector)                 │
                         │   news_articles · topic_clusters ·             │
                         │   article_bias · news_topic_statistics         │
                         └───────────────▲────────────────────────────────┘
                                         │  DATABASE_URL (external, over the wire)
                                         │
   ┌─────────────────────────────────────┴───────────────────────────────┐
   │  Python backend  (docker service `api`, FastAPI on :8001)            │
   │                                                                       │
   │  api_server.py ── HTTP endpoints (/, /health, /api/search, ...)       │
   │       │           ⚠ NOT used by the React frontend (see §6)          │
   │       └── APScheduler ── run_scrapers ─┐                              │
   │                          run_embeddings │  (utils/scheduler/tasks.py) │
   │                          run_obsidian_export                          │
   │                          run_bias_analysis ──► calls graph Edge Fn    │
   └───────────────────────────────────────────────────────────────────────┘
        │ scrapers/*.py            │ utils/jina_client.py     │ utils/llm.py
        ▼                          ▼                          ▼
   list pages (requests)      Jina embeddings API        local LLM (vLLM, :8000)
   + Firecrawl (:3002)        (jina-embeddings-v3)        Qwen3-4B
```

External services: **Firecrawl** (self-hosted, default `localhost:3002`, scrapes
article bodies), **Jina AI** (`jina-embeddings-v3`, 1024-dim vectors), **vLLM**
(local OpenAI-compatible LLM for extraction/classification), **SearXNG** (`:8081`).

---

## 2. Data model (Postgres + pgvector)

Defined in `database/models.py`. Bias tables were added later (see migrations).

| Table | Purpose | Key columns | Notes |
|-------|---------|-------------|-------|
| `news_articles` | one row per scraped article | `id`, `title`, `reporter`, `summary`, `publish_date`, `source_url` (unique), `source_site`, `title_embedding Vector(1024)`, `summary_embedding Vector(1024)`, `created_at`, `updated_at` | HNSW cosine indexes on both embeddings. **`summary` is usually empty** — the scraper LLM only extracts `reporter` (see CLAUDE.md). So `summary_embedding` is effectively always NULL. |
| `topic_clusters` | a bias-analysis topic for a given run | `id`, `run_date`, `cluster_label`, `side_a`, `side_b`, `cluster_type` (`controversial`\|`informational`), `article_count`, `attempted_count` | One set of clusters per `run_date` (daily). |
| `article_bias` | per-article stance within a cluster | `id`, `cluster_id`→`topic_clusters`, `article_id`→`news_articles`, `verdict` (`neutral`\|`side_a`\|`side_b`), `reasoning` (LLM text), `confidence` | Unique `(cluster_id, article_id)`. `reasoning` is the heaviest user-facing field. |
| `news_topic_statistics` | daily topic/keyword stats | `analysis_date` (unique), `total_articles`, `topics_data JSON` | Produced by `analyze_news_topics.py` (manual CLI). |

The 1024-dim `Vector` columns are ~**4 KB each (~8 KB/row for both)** — the dominant
egress cost when read over the wire (§3).

---

## 3. The two egress surfaces ⭐

Supabase **egress = bytes leaving Supabase**. There are two boundaries, and they are
billed differently:

| # | Surface | What crosses it | Billed egress? |
|---|---------|-----------------|----------------|
| 1 | **External Python ↔ Supabase Postgres** (`DATABASE_URL`) | every column of every row read by `api_server.py`, the scheduler jobs, and `scripts/*.py` | **Yes** — runs outside Supabase. Reading vector columns here is the expensive case. |
| 2 | **Browser ↔ Edge Functions / PostgREST** | JSON response payloads to the React app | **Yes** — leaves Supabase to the client. Scales with traffic. |
| — | **Edge Function ↔ its own Postgres** | e.g. `graph` reading `title_embedding` internally | **No** — Supabase-internal. A memory/CPU cost, not egress. |

**Consequences / patterns established in the codebase:**
- On surface #1, use SQLAlchemy `.options(load_only(...))` to exclude the vector
  columns from `SELECT` whenever they aren't needed. (Applied in
  `export_to_obsidian`, `analyze_news_topics`, `fix_missing_reporters`,
  `operations.search_articles_keyword`.) `load_only` keeps ORM objects mutable, so
  write-back still works.
- Prefer **server-side RPCs/aggregation** over pulling rows to the client
  (`get_distinct_sources`, `get_article_stats`, `get_bias_stats`).
- Vector similarity is computed **server-side** (`match_articles` RPC, the `<=>`
  operator) and the response carries only distances/scalars — never the vectors.
- Defense in depth: `revoke_embedding_columns.sql` revokes `SELECT` on the embedding
  columns from `anon`/`authenticated`, so they can never leak via PostgREST.
- The `graph` Edge Function pulling embeddings is internal, so it is **not** an
  egress concern (but it is a memory cost — bounded by `max_nodes ≤ 300`).

History: `git log` commit `ca88802` and `562fc2a` are the egress-reduction passes.

---

## 4. Python backend (`docker` service `api`)

### 4a. `api_server.py` — FastAPI on `:8001`
- HTTP endpoints: `/`, `/health`, `POST /api/search` (pgvector search, no embeddings
  in the response), `GET /api/sources`, `GET /api/stats`.
- **These HTTP endpoints are not called by the current React frontend** (the
  frontend talks to Supabase directly — see §6). Treat them as a separate/legacy
  interface or for non-browser clients.
- On startup it launches an **APScheduler** and registers the jobs below (jobs also
  fire **once immediately** on startup).

### 4b. Scheduled jobs (`utils/scheduler/tasks.py`)

| Job | Schedule (env) | What it does | Egress surface |
|-----|----------------|--------------|----------------|
| `run_scrapers` | `SCRAPE_SCHEDULE` (cron hours) or `SCRAPE_INTERVAL_MINUTES`; `SCRAPE_NO_DB` to skip DB | scrape list pages → LLM extracts `[{title,link}]` → filter existing → Firecrawl article fetch → LLM extracts reporter → insert | #1 (reads `source_url` only for dedup) |
| `run_embeddings` | `EMBED_INTERVAL_MINUTES` (default 60); `EMBED_BATCH_SIZE` (10), `EMBED_LIMIT`, `EMBED_FORCE` | finds rows missing a vector, calls Jina, writes back via `UPDATE ... WHERE id`. Selects only `id/title/summary` + NULL flags — **never reads existing vectors** | #1 |
| `run_obsidian_export` | daily at `OBSIDIAN_EXPORT_HOUR` (default 3), only if `OBSIDIAN_VAULT_PATH` set | exports **today's** articles to an Obsidian vault, builds a related-article map from `title_embedding` | #1 (reads `title_embedding`) |
| `run_bias_analysis` | daily at `BIAS_ANALYSIS_HOUR` (default 4); `days_back=3`, `k=10`, `min_similarity=0.65` | clusters recent articles, classifies stance per article, writes `topic_clusters` + `article_bias` | calls the **graph Edge Function** for clustering; fetches article bodies via Firecrawl |

### 4c. Scrapers (`news_scraper/`, `scrapers/`)
Base `NewsScraper` in `news_scraper/scraper.py`; each site subclass implements
`get_site_name` / `get_config` / `extract_news_block` (+ `build_full_link`). Register
new ones in `scripts/run_all_scrapers.py`. (Full guide in `CLAUDE.md`.)

### 4d. Standalone scripts (`scripts/`, repo root)
- `scripts/generate_embeddings.py` — embedding backfill (also the scheduled job).
- `scripts/analyze_bias.py` — bias pipeline (also scheduled). `_fetch_clusters()`
  calls the `graph` Edge Function; `_fetch_article_content()` uses Firecrawl.
- `scripts/export_to_obsidian.py` — Obsidian export (also scheduled).
- `scripts/fix_missing_reporters.py` — re-scrape articles whose reporter is `未提及`.
- `analyze_news_topics.py` — daily keyword/topic stats → `news_topic_statistics`
  (manual CLI, not scheduled).

---

## 5. Supabase layer

### 5a. Edge Functions (`supabase/functions/`, Deno; use `SERVICE_ROLE_KEY`)

| Function | Input | Reads | Returns | Notes |
|----------|-------|-------|---------|-------|
| `search` | `query`, `top_k`, `search_field` (`title`\|`summary`\|`both`), `source`, date range | Jina query embedding → `match_articles` RPC | `{ results: [...] }` with `similarity`, no vectors | bounded by `top_k ≤ 100` |
| `graph` | `date_from/to`, `source`, `max_nodes`, `k`, `min_similarity`, `seed`, `restarts` | up to `min(max_nodes, 300)` rows incl. `title_embedding` | `{ nodes, edges }` — cluster nodes + inter-cluster edges (cosine ≥ 0.7) | seeded k-means (mulberry32) + multi-restart; embedding read is **internal** |
| `bias` | `run_date` **or** `date_from/to` | `topic_clusters` + nested `article_bias` + `news_articles` over the run_date window | `{ run_date, clusters: [{ ..., articles: [{..., verdict, reasoning}] }] }` | merges clusters across run_dates when article overlap > 50%; `reasoning` makes this the heaviest browser payload |

### 5b. RPCs / SQL (`supabase/*.sql`, run manually in the SQL editor)

| File / function | Used by | Purpose |
|-----------------|---------|---------|
| `get_distinct_sources()` | BrowsePage dropdown | distinct `source_site[]` server-side (avoids a full-column scan to the client) |
| `get_article_stats(since_date)` | TopicStats | `{ daily, by_site, total }` aggregates |
| `get_bias_stats(date_from, date_to)` | BiasPage | per-source `total/neutral/partisan/partisan_rate` |
| `match_articles(...)` | `search` Edge Function | pgvector cosine search, returns scalars + `similarity` only |
| `revoke_embedding_columns.sql` | — (one-time) | revoke `SELECT` on embedding columns from `anon`/`authenticated` |

---

## 6. Frontend (`frontend/`, React + Vite, served by nginx on `:3000`)

Client config in `frontend/src/lib/supabase.ts` (`VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY`). **The frontend talks to Supabase directly — it does not
call the Python `api_server.py`.**

| Page (`src/components/`) | Backend call | Surface |
|--------------------------|--------------|---------|
| `SearchPage.tsx` | `functions.invoke('search')` | Edge Fn |
| `GraphPage.tsx` | `functions.invoke('graph')` | Edge Fn |
| `BiasPage.tsx` | `functions.invoke('bias')` + `rpc('get_bias_stats')` | Edge Fn + RPC |
| `BrowsePage.tsx` | `.from('news_articles').select(...)` paginated (`PAGE_SIZE=50`) + `rpc('get_distinct_sources')` | PostgREST + RPC |
| `TopicStats.tsx` | `rpc('get_article_stats')` | RPC |

No client-side caching today — pages refetch on mount / filter change. (Flagged as a
potential optimization; see the egress plan under `.omc/plans/`.)

---

## 7. Key data flows

**Scrape → Embed → Search**
`run_scrapers` inserts articles (empty `summary`) → `run_embeddings` backfills
`title_embedding` via Jina → user searches in `SearchPage` → `search` Edge Function
embeds the query and calls `match_articles` (cosine `<=>`) → ranked results.

**Bias pipeline (daily)**
`run_bias_analysis` → `graph` Edge Function clusters recent articles by
`title_embedding` → for each controversial cluster, fetch article bodies (Firecrawl)
and classify stance (LLM) → write `topic_clusters` + `article_bias` → `BiasPage`
reads them via the `bias` Edge Function + `get_bias_stats`.

**Graph view**
`GraphPage` → `graph` Edge Function → seeded k-means over `title_embedding` →
topic nodes + similarity edges.

---

## 8. Deployment (`docker-compose.yml`)

| Service | Image / build | Port | Role |
|---------|---------------|------|------|
| `api` | build `.` | `127.0.0.1:8001` | FastAPI + APScheduler (scrapers/embeddings/exports/bias) |
| `frontend` | build `frontend/` | `127.0.0.1:3000` | nginx serving the Vite build (Supabase URL/key baked at build time) |
| `searxng` | `searxng/searxng` | `:8081` | meta-search |
| `vllm` | `vllm/vllm-openai` | `:8000` | local LLM (Qwen3-4B), GPU |

Firecrawl runs separately (`firecrawl/`, default `localhost:3002`). To ship code
changes: `docker compose up -d --build api frontend` (leave `vllm`/`searxng` running).
The `api` container runs the startup scheduler jobs immediately on boot, so
`/health` may lag a few seconds while the first embed batch runs.
