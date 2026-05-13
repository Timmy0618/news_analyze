# 新聞向量搜尋系統

一個完整的台灣新聞爬取、向量化與語義搜尋系統。

## 功能特色

- **新聞爬取**: 自動爬取 TVBS、三立、中時政治新聞，使用 BeautifulSoup + regex 解析，不依賴 LLM
- **固定時間排程**: 每天 06:00 / 12:00 / 18:00 / 22:00 自動爬取，DB 去重確保不重複
- **向量嵌入**: 使用 Jina AI (`jina-embeddings-v3`) 將新聞標題轉換為 1024 維向量
- **語義搜尋**: FastAPI + pgvector 餘弦距離搜尋，支援自然語言查詢
- **網頁介面**: Streamlit 網頁應用程式

## 部署應用

[新聞向量搜尋系統](https://newsanalyze-ntnu4778vxnabxkhkfmg69.streamlit.app/)

## 系統架構

```
[Scrape phase]       →  [Embed phase]       →  [Search API]
scrapers/*.py            scripts/generate        api_server.py
BeautifulSoup+regex      _embeddings.py              ↑
Firecrawl (文章)         Jina AI API           Streamlit UI
      ↓                       ↓
  news_articles         title_embedding
  (PostgreSQL)          summary_embedding
  Supabase/pgvector
```

## 快速開始

```bash
# 安裝依賴
uv sync

# 啟動 Firecrawl + API server
make start

# 或分步驟
make firecrawl   # 啟動 Firecrawl (port 3002)
make migrate     # 執行資料庫 migration
make api         # 啟動 API server (port 8001)
make ui          # 啟動 Streamlit UI (port 8501)
```

### 所有 make 指令

| 指令 | 說明 |
|------|------|
| `make start` | 啟動 Firecrawl + API server |
| `make firecrawl` | 僅啟動 Firecrawl (port 3002) |
| `make db` | 啟動本地 postgres + pgadmin（開發用） |
| `make stop` | 停止所有 docker 服務 |
| `make api` | 啟動 API server |
| `make ui` | 啟動 Streamlit UI |
| `make scrape` | 手動執行爬蟲（`PAGES=3 MAX=50 DATE=2026-05-12`） |
| `make embed` | 生成嵌入向量 |
| `make migrate` | 執行 alembic upgrade head |
| `make logs` | 查看 Firecrawl logs |

## 環境需求

- Python 3.14+
- [Firecrawl](https://github.com/mendableai/firecrawl) 自架（`docker compose -f firecrawl/docker-compose.yml up -d`）
- PostgreSQL + pgvector（推薦使用 Supabase）

## 環境變數設定

```bash
cp .env.example .env
```

```env
# 資料庫（Supabase 格式）
DATABASE_URL=postgresql://postgres:<password>@db.<project-id>.supabase.co:5432/postgres

# Jina AI
JINA_API_KEY=your_jina_api_key

# OpenAI-compatible API key（Firecrawl 用，可填任意值）
OPENAPI_KEY=EMPTY

# 排程設定
SCHEDULER_ENABLED=true
SCRAPE_SCHEDULE=06:00,12:00,18:00,22:00   # 固定時間爬取（推薦）
SCRAPE_INTERVAL_MINUTES=0                  # 設為 0 停用 interval 模式

# 爬取設定
SCRAPE_PAGES=5
SCRAPE_MAX_ARTICLES=50

# 向量嵌入設定
EMBED_INTERVAL_MINUTES=60
EMBED_BATCH_SIZE=10
```

### 排程說明

- `SCRAPE_SCHEDULE` 有值時使用 **cron 模式**，在指定時間點爬取
- `SCRAPE_SCHEDULE` 未設定時回落至 `SCRAPE_INTERVAL_MINUTES` **interval 模式**
- 每次爬取前透過 DB `source_url` 唯一約束自動去重

## 資料庫初始化

```bash
make migrate
# 等同於: uv run alembic upgrade head
```

## 手動爬取

```bash
# 基本
make scrape

# 自訂參數
make scrape PAGES=3 MAX=50 DATE=2026-05-12

# 或直接執行腳本
uv run python scripts/run_all_scrapers.py --pages 3 --max-articles 50 --date 2026-05-12
```

## 診斷工具

```bash
# 驗證三個爬蟲的 HTML 解析是否正確（需 Firecrawl 運行中）
uv run python scripts/diagnose_scrapers.py
```

輸出每個站點的 news block 長度、parse 結果、日期過濾驗證、reporter 提取結果。

## API 介面

```bash
# 搜尋新聞
curl -X POST "http://localhost:8001/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "台灣政治", "search_field": "both", "top_k": 10}'

# 統計資訊
curl "http://localhost:8001/api/stats"
```

## 專案結構

```
.
├── Makefile                   # 快速啟動指令
├── api_server.py              # FastAPI + APScheduler
├── streamlit_app.py           # Streamlit 網頁應用程式
├── run_streamlit.py           # Streamlit 啟動腳本
├── alembic/                   # 資料庫遷移
├── database/                  # 資料庫模型和操作
├── news_scraper/              # 基底爬蟲（BeautifulSoup 解析）
├── scrapers/                  # 各網站爬取器（tvbs, setn, chinatimes）
├── scripts/
│   ├── run_all_scrapers.py    # 執行所有爬蟲
│   ├── generate_embeddings.py # 生成嵌入向量
│   └── diagnose_scrapers.py   # 爬蟲診斷工具
├── utils/
│   ├── jina_client.py         # Jina AI embedding
│   ├── llm.py                 # LLM client（用於其他功能）
│   └── scheduler/             # APScheduler 任務
├── firecrawl/                 # Firecrawl docker-compose
└── logs/                      # 日誌檔案
```

## 環境變數完整列表

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DATABASE_URL` | — | PostgreSQL 連線字串 |
| `JINA_API_KEY` | — | Jina AI API 金鑰 |
| `OPENAPI_KEY` | — | OpenAI-compatible key |
| `SCHEDULER_ENABLED` | `true` | 是否啟用排程 |
| `SCRAPE_SCHEDULE` | 空 | 固定時間爬取，逗號分隔 HH:MM |
| `SCRAPE_INTERVAL_MINUTES` | `60` | interval 模式間隔（`SCRAPE_SCHEDULE` 為空時生效） |
| `SCRAPE_PAGES` | `1` | 每站爬取頁數 |
| `SCRAPE_MAX_ARTICLES` | `15` | 每站最多文章數 |
| `SCRAPE_NO_DB` | `false` | 只輸出 JSON，不寫 DB |
| `EMBED_INTERVAL_MINUTES` | `60` | 嵌入排程間隔 |
| `EMBED_BATCH_SIZE` | `10` | 嵌入批次大小 |
| `EMBED_FORCE` | `false` | 強制重新生成所有嵌入 |

## 授權

MIT
