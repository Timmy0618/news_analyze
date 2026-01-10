# 新聞向量搜尋系統

一個完整的台灣新聞爬取、向量化與語義搜尋系統。

## 🚀 功能特色

- 📰 **新聞爬取**: 自動爬取 TVBS、三立、中時等新聞網站的最新政治新聞
- 🧠 **向量嵌入**: 使用 Jina AI 將新聞內容轉換為向量表示
- 🔍 **語義搜尋**: 支援自然語言搜尋，理解查詢意圖而非僅匹配關鍵字
- 📊 **統計分析**: 提供資料庫統計和搜尋分析
- 🎨 **網頁介面**: Streamlit 網頁應用程式提供直觀的搜尋體驗

## 🌐 部署應用

[新聞向量搜尋系統](https://newsanalyze-ntnu4778vxnabxkhkfmg69.streamlit.app/)

## 📋 系統架構

```
新聞爬取 → 向量化 → 儲存 → 搜尋 API → 網頁介面
   ↓         ↓         ↓         ↓         ↓
TVBS新聞  Jina AI   PostgreSQL  FastAPI   Streamlit
三立新聞  pgvector   向量搜尋   REST API  互動介面
中時新聞  語義理解   相似度計算 OpenAPI   即時搜尋
```

## 🛠️ 安裝與設定

### 1. 環境需求

- Python 3.14+
- PostgreSQL 15+ (支援 pgvector)

### 2. 安裝依賴

```bash
# 安裝 Python 依賴
uv sync
```

### 3. 環境變數設定

複製並編輯 `.env` 文件：

```bash
cp .env.example .env
```

編輯 `.env` 文件，設定以下變數：

```env
# 資料庫設定
DATABASE_URL=postgresql://postgres:password@db.example.com:5432/news_db

# Jina AI API 金鑰
JINA_API_KEY=your_jina_api_key_here

# 排程設定
SCHEDULER_ENABLED=true
SCRAPE_INTERVAL_MINUTES=60
EMBED_INTERVAL_MINUTES=60

# 爬取設定
SCRAPE_TARGET_DATE=  # 留空表示今天，格式: YYYY-MM-DD (例如: 2026-01-10)
SCRAPE_PAGES=1
SCRAPE_MAX_ARTICLES=15
```

### 4. 資料庫初始化

```bash
# 建立資料庫遷移
uv run alembic revision --autogenerate -m "Initial migration"

# 應用遷移
uv run alembic upgrade head
```

## 🚀 運行系統

### 啟動完整系統

```bash
# 啟動 API 服務器 (包含爬取和嵌入排程)
uv run python api_server.py

# 在另一個終端啟動網頁介面
uv run python run_streamlit.py
```

### 個別啟動

```bash
# 1. 啟動 API 服務器
uv run python api_server.py

# 2. 啟動 Streamlit 網頁介面
uv run python run_streamlit.py

# 3. 手動執行爬取 (可選)
uv run python scripts/run_all_scrapers.py --pages 3 --max-articles 50
```

## 🎯 使用方法

### 網頁介面 (推薦)

1. 開啟瀏覽器訪問 `http://localhost:8501`
2. 在搜尋框輸入關鍵字，如："台灣政治"、"中美關係"
3. 選擇搜尋範圍 (標題+摘要 / 僅標題 / 僅摘要)
4. 設定結果數量和篩選條件
5. 點擊「開始搜尋」查看結果

### API 介面

```bash
# 搜尋新聞
curl -X POST "http://localhost:8001/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "台灣政治",
    "search_field": "both",
    "top_k": 10
  }'

# 查看統計資訊
curl "http://localhost:8001/api/stats"

# 查看新聞來源
curl "http://localhost:8001/api/sources"
```

### 命令列爬取

```bash
# 爬取所有新聞來源
uv run python scripts/run_all_scrapers.py

# 自訂參數
uv run python scripts/run_all_scrapers.py \
  --pages 5 \
  --max-articles 100 \
  --date 2026-01-10 \
  --debug
```

## 📁 專案結構

```
.
├── api_server.py              # FastAPI 服務器
├── streamlit_app.py           # Streamlit 網頁應用程式
├── run_streamlit.py           # Streamlit 啟動腳本
├── alembic/                   # 資料庫遷移
├── database/                  # 資料庫模型和操作
├── news_scraper/              # 新聞爬取模組
├── scrapers/                  # 各網站爬取器
├── scripts/                   # 工具腳本
├── utils/                     # 工具函數
├── results/                   # 爬取結果
├── raw_data_*/               # 原始資料 (debug 模式)
└── logs/                      # 日誌檔案
```

## 🔧 設定選項

### 環境變數

| 變數名稱 | 預設值 | 說明 |
|---------|--------|------|
| `DATABASE_URL` | - | PostgreSQL 連線字串 |
| `JINA_API_KEY` | - | Jina AI API 金鑰 |
| `SCHEDULER_ENABLED` | `true` | 是否啟用自動排程 |
| `SCRAPE_INTERVAL_MINUTES` | `60` | 爬取間隔 (分鐘) |
| `SCRAPE_TARGET_DATE` | 空 | 爬取目標日期 (格式: YYYY-MM-DD，空表示今天) |
| `SCRAPE_PAGES` | `1` | 每個網站爬取的頁數 |
| `SCRAPE_MAX_ARTICLES` | `15` | 每個網站最多處理的文章數 |
| `EMBED_INTERVAL_MINUTES` | `60` | 嵌入間隔 (分鐘) |
| `API_BASE_URL` | `http://localhost:8001` | API 服務地址 |

### 爬取參數

- `--pages N`: 每個網站爬取的頁數
- `--max-articles N`: 每個網站最多處理的文章數
- `--date YYYY-MM-DD`: 指定爬取日期
- `--no-db`: 只儲存 JSON，不寫入資料庫
- `--debug`: 啟用調試模式，儲存中間檔案

## 📊 資料庫統計

系統提供以下統計資訊：

- 總文章數量
- 已嵌入向量文章數量
- 嵌入覆蓋率
- 日期範圍
- 各來源文章數量

## 🐛 故障排除

### 常見問題

1. **資料庫連線失敗**
   ```bash
   # 檢查 PostgreSQL 服務
   sudo systemctl status postgresql

   # 檢查連線字串
   uv run python -c "import psycopg2; psycopg2.connect(os.getenv('DATABASE_URL'))"
   ```

2. **Jina AI API 錯誤**
   ```bash
   # 檢查 API 金鑰
   curl -H "Authorization: Bearer $JINA_API_KEY" https://api.jina.ai/v1/models
   ```

### 日誌查看

```bash
# 查看應用程式日誌
tail -f logs/api_server.log

# 查看爬取日誌
tail -f logs/scraper.log
```

## 🤝 貢獻指南

歡迎提交 Issue 和 Pull Request！

1. Fork 此專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 授權

本專案採用 MIT 授權條款。
