# 本地 LLM 切換 + Supabase 專案遷移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM 從 OpenAI 遠端切到本地 vLLM(`qwen3.6-35b`),Supabase 遷移到新空專案 `xydpujhfzikjcmcjmlev`(schema/RPC/RLS/edge functions 全部重建,舊資料不搬)。

**Architecture:** 純設定切換(程式碼不動):`.env` 存本機視角的值,docker-compose 用 `environment:` 覆蓋容器差異。Supabase 端操作全部透過 Supabase MCP(SQL 執行、edge function 部署、取 anon key);schema 用既有 alembic migrations 建。

**Tech Stack:** vLLM(宿主機 :8000)、Supabase MCP、alembic、pgvector、Supabase Edge Functions(Deno)。

**Spec:** `docs/superpowers/specs/2026-07-20-local-llm-supabase-migration-design.md`

## Global Constraints

- 本地模型 id 固定為 `qwen3.6-35b`(vLLM served-model-name,底層 `Qwen/Qwen3.6-35B-A3B-FP8`)。
- 新 Supabase 專案 ref:`xydpujhfzikjcmcjmlev`;舊專案 `uophyhknfzkaiefjtqgb` 不再使用、不搬資料。
- 秘密值(`SUPABASE_PASS`、`JINA_API_KEY`、anon key、DATABASE_URL)只寫進 gitignored 的 `.env` / `frontend/.env`,絕不進 git 或本計畫文件。
- `.env` 與 `frontend/.env` 未被 git 追蹤;可 commit 的只有 `docker-compose.yml`、`.env.example`、`database/migrations/*.sql`、文件。
- 所有 commit 訊息附 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- RLS 原則:4 張表(`news_articles`、`news_topic_statistics`、`topic_clusters`、`article_bias`)全部啟用 RLS,只給 anon SELECT 政策,不加寫入政策(後端走 postgres role、edge functions 走 service_role,皆不受 RLS 限制)。
- 3 個讀取用 RPC(`get_distinct_sources`、`get_article_stats`、`get_bias_stats`)非 SECURITY DEFINER,以 anon 身分讀表 — 這是 RLS 必須涵蓋 4 張表的原因。

---

### Task 1: LLM / Firecrawl 設定切換(.env + docker-compose)

**Files:**
- Modify: `.env`(第 4-6、9 行)
- Modify: `.env.example`(第 9-11 行)
- Modify: `docker-compose.yml`(api service、vllm service)

**Interfaces:**
- Produces: `.env` 中 `LLM_URL=http://localhost:8000/v1`、`LLM_MODEL=qwen3.6-35b`;容器內生效值為 `http://host-gateway:8000/v1`。後續 Task 的 scraper 驗證依賴此設定。

- [ ] **Step 1: 改 `.env` 的 LLM 與 Firecrawl 設定**

把第 4-6 行:

```env
OPENAPI_KEY=sk-proj-…(現有真實 key)
LLM_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

改成:

```env
OPENAPI_KEY=EMPTY
LLM_URL=http://localhost:8000/v1
LLM_MODEL=qwen3.6-35b
```

把第 9 行 `FIRECRAWL_URL=http://host-gateway:3002` 改成:

```env
FIRECRAWL_URL=http://localhost:3002
```

- [ ] **Step 2: 改 `.env.example` 第 9-11 行對齊**

```env
OPENAPI_KEY=EMPTY  # 本地 OpenAI 相容伺服器填任意非空字串
LLM_URL=http://localhost:8000/v1
LLM_MODEL=qwen3.6-35b
```

- [ ] **Step 3: `docker-compose.yml` api service 加容器覆蓋**

在 `api` service 的 `extra_hosts:` 區塊後加(`environment:` 優先於 `env_file`,容器內覆蓋 localhost 值):

```yaml
    environment:
      LLM_URL: http://host-gateway:8000/v1
      FIRECRAWL_URL: http://host-gateway:3002
```

- [ ] **Step 4: 更新 `docker-compose.yml` vllm service 的 command 到新模型**

把:

```yaml
    command: --model Qwen/Qwen3-4B-Instruct-2507 --gpu-memory-utilization 0.90 --max-model-len 8192
```

改成(對齊宿主機現跑實例的模型與 262144 context;`--served-model-name` 讓 model id 在兩種模式下都是 `qwen3.6-35b`):

```yaml
    command: --model Qwen/Qwen3.6-35B-A3B-FP8 --served-model-name qwen3.6-35b --gpu-memory-utilization 0.90 --max-model-len 262144
```

- [ ] **Step 5: 驗證本地 LLM 連線**

Run: `uv run python utils/llm.py`
Expected: 印出 `使用模型: qwen3.6-35b`、`Base URL: http://localhost:8000/v1`、`測試成功！回應: …`

- [ ] **Step 6: 驗證 compose 覆蓋有生效**

Run: `docker compose config api | grep -A3 environment`
Expected: 看到 `LLM_URL: http://host-gateway:8000/v1` 與 `FIRECRAWL_URL: http://host-gateway:3002`

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: switch LLM to local vLLM qwen3.6-35b with per-mode URL overrides

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: RLS SQL 補齊到全部 4 張表

**Files:**
- Create: `database/migrations/20260720_rls_read_only_all_tables.sql`

**Interfaces:**
- Consumes: 既有 `database/migrations/20260513_rls_read_only.sql` 已涵蓋 `news_articles`。
- Produces: 新檔涵蓋其餘 3 張表;Task 5 會把兩個 RLS 檔都套用到新專案。

- [ ] **Step 1: 建立 SQL 檔(完整內容如下)**

```sql
-- 補齊 20260513_rls_read_only.sql 之後新增的三張表。
-- anon 唯讀;寫入走 postgres role(後端 DATABASE_URL)與 service_role(edge functions),不受 RLS 限制。
-- get_distinct_sources / get_article_stats / get_bias_stats 皆非 SECURITY DEFINER,
-- 以呼叫者(anon)身分讀表,故 RLS 政策必須涵蓋這些表。

ALTER TABLE news_topic_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_bias ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read" ON news_topic_statistics FOR SELECT TO anon USING (true);
CREATE POLICY "public read" ON topic_clusters FOR SELECT TO anon USING (true);
CREATE POLICY "public read" ON article_bias FOR SELECT TO anon USING (true);
```

- [ ] **Step 2: Commit**

```bash
git add database/migrations/20260720_rls_read_only_all_tables.sql
git commit -m "feat: extend read-only RLS to all public tables

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Supabase MCP 授權 + 新專案基礎設置

**Files:**
- Modify: `.env`(第 2 行 `DATABASE_URL`、第 28 行 `VITE_SUPABASE_ANON_KEY`)
- Modify: `frontend/.env`(整檔 2 行)

**Interfaces:**
- Consumes: `.env` 既有的 `SUPABASE_PASS` 值(新專案 DB 密碼,已與使用者確認)。
- Produces: 可用的 `DATABASE_URL`(Task 4 alembic 依賴)、新專案 anon key(Task 5 驗證與前端依賴)。

- [ ] **Step 1: Supabase MCP 授權**

呼叫 `mcp__plugin_supabase_supabase__authenticate`,請使用者在瀏覽器完成授權後以 `complete_authentication` 收尾。確認可列出專案且包含 `xydpujhfzikjcmcjmlev`。

- [ ] **Step 2: 啟用 pgvector extension**

透過 MCP 對新專案執行 SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Expected: 成功;`SELECT extname FROM pg_extension WHERE extname = 'vector';` 回 1 列。

- [ ] **Step 3: 組出 DATABASE_URL 並寫入 `.env`**

從 MCP 取得專案連線資訊(region / pooler host),組 session pooler 字串(port 5432,alembic 需要 session mode;密碼用 `.env` 的 `SUPABASE_PASS` 值):

```env
DATABASE_URL=postgresql://postgres.xydpujhfzikjcmcjmlev:<SUPABASE_PASS 的值>@<MCP 回傳的 pooler host>:5432/postgres
```

- [ ] **Step 4: 驗證 DB 連線**

Run: `uv run python -c "from sqlalchemy import create_engine, text; import os; from dotenv import load_dotenv; load_dotenv(); e = create_engine(os.environ['DATABASE_URL']); print(e.connect().execute(text('SELECT 1')).scalar())"`
Expected: 印出 `1`

- [ ] **Step 5: 取新專案 anon key,更新兩個 env 檔**

從 MCP 取 anon key,然後:
- `frontend/.env` 全檔改為:

```env
VITE_SUPABASE_URL=https://xydpujhfzikjcmcjmlev.supabase.co
VITE_SUPABASE_ANON_KEY=<MCP 回傳的 anon key>
```

- 根目錄 `.env` 第 28 行 `VITE_SUPABASE_ANON_KEY=` 填入同一把 key(docker compose build args 用)。

- [ ] **Step 6: 驗證 anon key 可用**

Run: `source .env 2>/dev/null; curl -s -o /dev/null -w "%{http_code}" "https://xydpujhfzikjcmcjmlev.supabase.co/rest/v1/" -H "apikey: $VITE_SUPABASE_ANON_KEY"`
Expected: `200`(此時還沒有表,root endpoint 回 OpenAPI 描述即可)

(env 檔不入 git,本 task 無 commit。)

---

### Task 4: 用 alembic 建 schema

**Files:**
- 無檔案變更(執行既有 migrations)

**Interfaces:**
- Consumes: Task 3 的 `DATABASE_URL`。
- Produces: 4 張表 + HNSW 向量索引,Task 5/6/7 依賴。

- [ ] **Step 1: 跑 migrations**

Run: `uv run alembic upgrade head`
Expected: 依序執行 7 個 migrations 無錯誤。若出現 `type "vector" does not exist`,回 Task 3 Step 2 確認 extension 後重跑。

- [ ] **Step 2: 驗證 schema**

Run: `uv run alembic current`
Expected: 顯示 head revision(帶 `(head)` 標記)。

透過 MCP 執行:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
```

Expected: 至少包含 `alembic_version`、`article_bias`、`news_articles`、`news_topic_statistics`、`topic_clusters`。

---

### Task 5: 套用 RPC / 權限 / RLS SQL

**Files:**
- 無檔案變更(把 repo 既有 SQL 套到新專案)

**Interfaces:**
- Consumes: Task 4 的表;repo SQL 檔。
- Produces: RPC `match_articles`(search edge function 依賴)、`get_distinct_sources`、`get_article_stats`、`get_bias_stats`(前端依賴);RLS 政策。

- [ ] **Step 1: 依序透過 MCP 執行 7 個 SQL 檔**

順序(先函式後權限):

1. `database/migrations/20260513_match_articles_fn.sql`
2. `supabase/get_distinct_sources.sql`
3. `supabase/get_article_stats.sql`
4. `supabase/get_bias_stats.sql`
5. `supabase/revoke_embedding_columns.sql`
6. `database/migrations/20260513_rls_read_only.sql`
7. `database/migrations/20260720_rls_read_only_all_tables.sql`

每檔用 Read 讀出內容後原樣執行,不改寫。

- [ ] **Step 2: 驗證政策與函式都在**

透過 MCP 執行:

```sql
SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename;
```

Expected: 4 列,4 張表各一條 `public read`。

```sql
SELECT proname FROM pg_proc WHERE proname IN ('match_articles','get_distinct_sources','get_article_stats','get_bias_stats');
```

Expected: 4 列。

- [ ] **Step 3: 驗證 anon 行為(讀可、寫拒、embedding 欄位拒)**

```bash
source .env 2>/dev/null
BASE=https://xydpujhfzikjcmcjmlev.supabase.co
# 讀:200 + 空陣列(還沒資料)
curl -s -w "\n%{http_code}" "$BASE/rest/v1/news_articles?select=id&limit=1" -H "apikey: $VITE_SUPABASE_ANON_KEY" -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY"
# RPC:200 + []
curl -s -w "\n%{http_code}" "$BASE/rest/v1/rpc/get_distinct_sources" -X POST -H "apikey: $VITE_SUPABASE_ANON_KEY" -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY" -H "Content-Type: application/json" -d '{}'
# 寫:應被拒(RLS 無 INSERT 政策 → 401/403)
curl -s -w "\n%{http_code}" "$BASE/rest/v1/news_articles" -X POST -H "apikey: $VITE_SUPABASE_ANON_KEY" -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY" -H "Content-Type: application/json" -d '{"title":"x","source_url":"http://x"}'
# embedding 欄位:應被拒(欄位級 REVOKE → 401/403)
curl -s -w "\n%{http_code}" "$BASE/rest/v1/news_articles?select=title_embedding&limit=1" -H "apikey: $VITE_SUPABASE_ANON_KEY" -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY"
```

Expected: 依序 `[] / 200`、`[] / 200`、`4xx`(42501 new row violates row-level security 或 permission denied)、`4xx`(permission denied for column)。

---

### Task 6: 部署 edge functions + secrets

**Files:**
- 無檔案變更(部署 `supabase/functions/{search,bias,graph}/index.ts`)

**Interfaces:**
- Consumes: Task 5 的 `match_articles` RPC;`.env` 的 `JINA_API_KEY` 值。
- Produces: `https://xydpujhfzikjcmcjmlev.supabase.co/functions/v1/{search,bias,graph}` 三個端點。

- [ ] **Step 1: 設定 function secret `JINA_API_KEY`**

search function 用 `Deno.env.get('JINA_API_KEY')` 做查詢 embedding(`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` 平台自動注入,不用設)。優先用 MCP 設 secret;若 MCP 無此能力,退回 CLI(access token 向使用者要,用完不落地):

```bash
source .env 2>/dev/null
SUPABASE_ACCESS_TOKEN=<使用者提供> npx -y supabase secrets set JINA_API_KEY="$JINA_API_KEY" --project-ref xydpujhfzikjcmcjmlev
```

- [ ] **Step 2: 透過 MCP 部署三個 functions**

對 `search`、`bias`、`graph` 各執行一次:Read `supabase/functions/<name>/index.ts` → MCP deploy(function name 用目錄名)。

- [ ] **Step 3: 驗證三個端點**

```bash
source .env 2>/dev/null
BASE=https://xydpujhfzikjcmcjmlev.supabase.co/functions/v1
curl -s -w "\n%{http_code}" "$BASE/search" -X POST -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY" -H "Content-Type: application/json" -d '{"query":"測試","top_k":3}'
curl -s -w "\n%{http_code}" "$BASE/bias"   -X POST -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY" -H "Content-Type: application/json" -d '{}'
curl -s -w "\n%{http_code}" "$BASE/graph"  -X POST -H "Authorization: Bearer $VITE_SUPABASE_ANON_KEY" -H "Content-Type: application/json" -d '{}'
```

Expected: 三個都 `200`,回 JSON(空專案 → 空結果/空陣列屬正常;`search` 回 200 同時證明 JINA_API_KEY secret 有效)。

---

### Task 7: 端到端驗證(本地 LLM 爬蟲 → 新 DB → embeddings → 前端)

**Files:**
- 無檔案變更

**Interfaces:**
- Consumes: 前面全部 task 的成果。

- [ ] **Step 1: 啟動 Firecrawl(目前沒在跑)**

Run: `docker compose -f firecrawl/docker-compose.yml up -d`(背景執行,等待啟動)
驗證: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3002` → 非 `000`(Firecrawl root 通常回 200)。

- [ ] **Step 2: 限量跑一次 scraper(驗證本地 LLM 抽取 + 寫入新 DB)**

Run: `uv run python scripts/run_all_scrapers.py --pages 1 --max-articles 2`
Expected: 無 exception;log 顯示 LLM 抽取與 DB 寫入。

- [ ] **Step 3: 確認新 DB 有資料**

透過 MCP 執行:

```sql
SELECT COUNT(*), MAX(created_at) FROM news_articles;
```

Expected: count > 0。

- [ ] **Step 4: 產 embeddings 並驗證語意搜尋**

Run: `uv run python scripts/generate_embeddings.py`
Expected: 對剛入庫文章產生向量、無錯誤。

再用 Task 6 Step 3 的 search curl(query 換成剛爬到的標題關鍵字)。
Expected: `200` 且 results 非空。

- [ ] **Step 5: 前端手動確認**

Run: `cd frontend && npm run dev`
請使用者開 browse / search / bias 頁確認資料正常,無 4xx(RLS/權限)錯誤。

- [ ] **Step 6: 收尾 commit(若前面驗證過程有修正)**

Run: `git status --short`
若有未 commit 的修正,逐一檢視後 commit;env 檔不入 git。
