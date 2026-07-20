# 設計:切換本地 LLM + 遷移到新 Supabase 專案

日期:2026-07-20
狀態:已核准

## 目標

1. LLM 從遠端 OpenAI(`api.openai.com` / `gpt-4o-mini`)切換到本地 vLLM(`localhost:8000` / `qwen3.6-35b`,即 `Qwen/Qwen3.6-35B-A3B-FP8`)。
2. Supabase 從舊專案 `uophyhknfzkaiefjtqgb` 遷移到新專案 `xydpujhfzikjcmcjmlev`(空專案,需建 schema/RPC/edge functions;舊資料不搬,重爬)。

## 現狀

- `utils/llm.py` 與 `scripts/analyze_bias.py` 都從環境變數讀 `LLM_URL` / `LLM_MODEL` / `OPENAPI_KEY`,程式碼不需修改。
- `api_server.py` 有兩種執行模式:docker compose(容器內 `localhost` 連不到宿主機服務)與本機 `uv run`。`docker-compose.yml` 已有 `host-gateway` 的 `extra_hosts` 對映。
- 根目錄 `.env` 的 `DATABASE_URL` 目前為空;`VITE_SUPABASE_ANON_KEY` 為空;`frontend/.env` 仍指向舊專案。
- `supabase/` 內有 4 個 SQL 檔(`get_article_stats.sql`、`get_bias_stats.sql`、`get_distinct_sources.sql`、`revoke_embedding_columns.sql`)與 3 個 edge functions(`search`、`bias`、`graph`),舊專案曾部署過。
- 無 supabase CLI、無 psql;採用 Supabase MCP(使用者瀏覽器授權)執行遠端操作。

## 變更內容

### 1. LLM 設定(純設定檔)

- `.env`:
  - `LLM_URL=http://localhost:8000/v1`
  - `LLM_MODEL=qwen3.6-35b`
  - `OPENAPI_KEY=EMPTY`(移除真實 OpenAI key)
  - `FIRECRAWL_URL=http://localhost:3002`
- `docker-compose.yml` api service 加 `environment:` 覆蓋(容器模式專用):
  - `LLM_URL=http://host-gateway:8000/v1`
  - `FIRECRAWL_URL=http://host-gateway:3002`

原則:`.env` 保存本機視角的值,容器差異由 compose 覆蓋,兩種執行模式都正確。

### 2. Supabase 遷移(透過 MCP)

依序執行:

1. 新專案啟用 `vector` extension。
2. `.env` 補上新專案 `DATABASE_URL`(以 `SUPABASE_PASS` 組 pooler 連線字串;已確認該密碼屬於新專案)。
3. `uv run alembic upgrade head` 建立 schema(7 個 migrations)。
4. 透過 MCP 執行 `supabase/*.sql`(3 個 RPC + revoke embedding columns 的權限收斂 + 新增的 RLS 設定,見下)。
5. 部署 3 個 edge functions(`search`、`bias`、`graph`);部署前檢查各 `index.ts` 引用的 secrets(如 Jina API key)並在新專案設定。
6. RLS:新增 `supabase/enable_rls.sql` 進 repo 並在新專案執行:
   - 對全部 4 張表(`news_articles`、`news_topic_statistics`、`topic_clusters`、`article_bias`)啟用 RLS。
   - 每張表加一條 anon/authenticated 的 SELECT 政策(`using (true)`,公開唯讀新聞資料)。4 張都要:3 個 RPC 非 SECURITY DEFINER,以呼叫者(anon)身分讀這些表。
   - 不加任何寫入政策 — 寫入只走後端 `DATABASE_URL`(postgres role,表擁有者不受 RLS 限制)與 edge functions 的 service_role。
   - embedding 欄位仍由 `revoke_embedding_columns.sql` 的欄位級 REVOKE 擋住。
7. 從 MCP 取得新專案 anon key,更新 `frontend/.env`(URL + anon key)與根目錄 `.env` 的 `VITE_SUPABASE_ANON_KEY`。

### 3. 驗證

- `curl http://localhost:8000/v1/chat/completions` 確認本地 LLM 回應。
- `uv run alembic current` 為 head;以 SQL 查詢確認 RPC 存在。
- 限量跑一次 scraper(1 頁、少量文章)驗證本地 LLM 抽取 + 寫入新 DB。
- RLS:用 anon key 直接查 `news_articles` 應回資料、呼叫 3 個 RPC 應正常、嘗試 anon INSERT 應被拒。
- 前端指向新專案後,手動確認 browse/search 頁正常。

## 不做的事

- 不搬舊專案資料(含 embeddings),新專案重爬。
- 不修改 `utils/llm.py` 等程式碼。
- 不動 Jina embedding 流程。

## 錯誤處理

- alembic 失敗且訊息涉及 `vector` 型別 → 確認 extension 已啟用後重跑。
- edge function 執行期錯誤 → 檢查新專案的 function secrets 是否齊全。
- 容器內連不到 vLLM/Firecrawl → 確認 `extra_hosts` 的 `host-gateway` 對映與宿主機服務監聽位址(不可只綁 127.0.0.1)。
