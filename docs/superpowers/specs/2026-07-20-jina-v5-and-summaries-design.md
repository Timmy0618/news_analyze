# Jina v5 切換 + 文章摘要（summary）產生與嵌入

日期：2026-07-20
狀態：已核可

## 目標

1. Embedding 模型從 `jina-embeddings-v3` 切換到 `jina-embeddings-v5-text-small`。
2. `news_articles.summary`（大綱）改為由本地 LLM 產生：新文章在抓取時產生，既有文章全部回填。
3. summary embedding 隨既有流程自動產生，供之後偏頗分析使用。

## 明確不做（本次範圍外）

- `scripts/analyze_bias.py` 不改，維持 Firecrawl 重抓全文的現行流程。
- 不在 DB 新增全文欄位。
- 不改向量維度、不需要 Alembic migration（v5-text-small 預設輸出 1024 維，與現有 `Vector(1024)` 及 HNSW 索引相容）。

## 變更點

### 1. `utils/jina_client.py` — 模型切換

- `self.model` 改讀環境變數 `JINA_MODEL`，預設 `jina-embeddings-v5-text-small`。
- API endpoint 不變（`https://api.jina.ai/v1/embeddings`）。
- 實作時對照 Jina 官方文件確認 v5 的 `task` 參數合法值（v3 用 `text-matching`，v5 可能不同）；必要時調整 `generate_embeddings` 的預設 task。
- `generate_embeddings.py` 與 `api_server.py` 的查詢向量共用此 client，改一處全部生效。

### 2. `news_scraper/scraper.py` — 抓取時產生摘要

- `extract_article_info()` 目前把全文丟給本地 LLM 只抽記者、大綱固定回空字串。
- 改為同一次 LLM 呼叫同時回傳 `{記者, 大綱}`：大綱為 2–3 句繁體中文摘要（約 100 字內）。
- 不增加 LLM 呼叫次數與 Firecrawl 抓取次數。
- LLM 回傳非 JSON 時沿用現有 `fix_json_response` 修復機制。

### 3. 新增 `scripts/backfill_summaries.py` — 舊文章回填

- 查詢 `summary IS NULL OR summary = ''` 的文章。
- 每篇：Firecrawl 重抓全文 → 本地 LLM 摘要 → `UPDATE news_articles SET summary WHERE id`。
- Firecrawl 抓取與內容驗證邏輯沿用 `analyze_bias.py` 現有實作（`_fetch_article_content`、`_is_valid_content`、`SITE_TAGS`），抽成共用 util 供兩邊使用。
- CLI 參數：`--limit`、`--batch-size`。每篇 commit，可中斷重跑（天然斷點續傳）。
- 抓取失敗或內容無效的文章記 log 並跳過，不中斷整批；結束時輸出成功/失敗統計。

### 4. 全量重嵌

- v3 與 v5 向量空間不相容，切換後所有既有向量失效。
- 執行順序：**切 v5 → 跑回填腳本 → `uv run python scripts/generate_embeddings.py --force`** 一次全量重嵌（title embedding 重嵌 + 新 summary 的 embedding 一起產生）。
- 之後排程的增量 embedding job 自動涵蓋新文章的 title + summary，不需改邏輯。
- 過渡期（切 v5 至重嵌完成之間）語義搜尋為新查詢向量比對舊空間向量，結果失準——暫時且預期。

## 錯誤處理

- 回填腳本：Firecrawl 失敗/內容無效 → 跳過 + 計數；LLM 失敗 → 跳過 + 記 log；單篇失敗不影響其他文章。
- 摘要抽取：LLM 回傳格式錯誤走 `fix_json_response`，仍失敗則該篇大綱留空（下次回填腳本可再撿起）。

## 測試

- `extract_article_info` 新 prompt 的回應解析：單元測試（模擬 LLM 回應含記者+大綱、只含記者、非 JSON）。
- 回填腳本：以 `--limit 5` 實測跑通並人工檢查摘要品質。
- 重嵌後：`/api/search` 手動查詢驗證結果合理。

## 驗收標準

1. 新抓文章的 `summary` 非空且為繁中摘要。
2. 舊文章回填後，`summary IS NULL OR summary = ''` 的列數趨近 0（僅剩 Firecrawl 抓不到的）。
3. 全部 `title_embedding`/`summary_embedding` 以 v5 重新產生，搜尋功能正常。
