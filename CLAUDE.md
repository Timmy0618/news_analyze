# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run API server (port 8001, includes background scheduler)
uv run python api_server.py

# Run Streamlit UI (port 8501)
uv run python run_streamlit.py

# Run all scrapers manually
uv run python scripts/run_all_scrapers.py --pages 3 --max-articles 50 --date 2026-01-10

# Generate embeddings for unenmbedded articles
uv run python scripts/generate_embeddings.py

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Lint
ruff check

# Tests
pytest
```

## Architecture

The system has three independent operational phases that run on a schedule inside `api_server.py`:

```
[Scrape phase]  →  [Embed phase]  →  [Search API]
scrapers/*.py      jina_client.py     api_server.py
     ↓                  ↓                  ↑
 results/*.json   news_articles         Streamlit
                (title/summary_embedding)
```

### Scraping (`news_scraper/`, `scrapers/`)

`news_scraper/scraper.py` contains the base `NewsScraper` class. Each site scraper in `scrapers/` extends it and must implement three class methods:
- `get_site_name()` — display name used as `source_site` in the DB
- `get_config()` — returns a `NewsScraperConfig` with the list-page URL and article HTML tags
- `extract_news_block(content)` — extracts the news list section from raw HTML (site-specific regex)

The scraping flow for each site:
1. Fetch list pages with `requests` (no Firecrawl for list pages)
2. Call `extract_news_block()` → clean HTML → send to local LLM to extract `[{title, link}]` JSON
3. Filter out URLs already in the DB (`filter_existing_links`)
4. For each new link: fetch article via Firecrawl (`/v2/scrape`) → send to LLM to extract reporter
5. Save results as JSON to `results/` and optionally insert to DB

The LLM (`utils/llm.py`) is a `ChatOpenAI` instance pointing to a local OpenAI-compatible server. It handles malformed JSON by calling itself again to fix it (`fix_json_response`). Article summaries (`大綱`) are intentionally left empty — the LLM only extracts the reporter field to reduce latency.

### Embedding (`scripts/generate_embeddings.py`, `utils/jina_client.py`)

Queries `news_articles` rows where `title_embedding IS NULL OR summary_embedding IS NULL`, batches them, and calls Jina AI's `jina-embeddings-v3` API to generate 1024-dimensional vectors. Vectors are stored back into the `title_embedding` and `summary_embedding` columns (pgvector `Vector(1024)`).

### API (`api_server.py`)

FastAPI server on port 8001. The `/api/search` endpoint:
1. Generates a query embedding via `jina_client.generate_embedding()` (async)
2. Runs a raw SQL query using pgvector's cosine distance operator `<=>` against `title_embedding`, `summary_embedding`, or the average of both
3. Supports filtering by `source_site`, `date_from`, `date_to`

The server starts an `APScheduler` on startup that runs scrapers and embeddings at configurable intervals (env vars `SCRAPE_INTERVAL_MINUTES`, `EMBED_INTERVAL_MINUTES`). Both jobs also fire once immediately on startup.

### Database (`database/`)

- `models.py`: `NewsArticle` (with HNSW vector indexes) and `NewsTopicStatistics`
- `config.py`: SQLAlchemy engine + `Session` (scoped) + `get_db()` generator
- `operations.py`: `save_scraper_results_to_db()` does bulk insert; duplicate `source_url` (unique constraint) causes the entire batch to fail and roll back — duplicates are pre-filtered via `filter_existing_links()`

Article dict keys accepted by `save_scraper_results_to_db` support both Chinese (`標題`, `記者`, `大綱`, `日期`, `連結`) and English field names.

## Required Environment Variables

```env
DATABASE_URL=postgresql://postgres:password@host:5432/news_db
JINA_API_KEY=...

# Local LLM server (OpenAI-compatible)
LLM_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen3-4B-Instruct-2507
OPENAPI_KEY=EMPTY  # can be any non-empty string for local servers

# Firecrawl (self-hosted)
# NewsScraper defaults to http://localhost:3002
```

Firecrawl and a local LLM server must be running for scraping to work. See `docker-compose.yml` for Firecrawl setup.

## Adding a New Scraper

1. Create `scrapers/yoursite_scraper.py` extending `NewsScraper`
2. Implement `get_site_name()`, `get_config()`, `extract_news_block()`, and `build_full_link()` (if links are relative)
3. Register the class in `scripts/run_all_scrapers.py`'s `scraper_classes` list
