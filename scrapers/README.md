# 新聞爬蟲執行指南

本資料夾包含各個新聞網站的爬蟲程式。

## 資料夾結構

```
scrapers/
├── __init__.py              # 模組初始化
├── tvbs_scraper.py          # TVBS 新聞爬蟲
├── setn_scraper.py          # 三立新聞爬蟲
├── chinatimes_scraper.py    # 中時電子報爬蟲
└── example_other_site.py    # 範例爬蟲
```

## 使用方式

### 方式 1: 執行所有爬蟲（推薦）

使用根目錄的 `run_all_scrapers.py` 一次執行所有爬蟲：

```bash
# 基本用法（爬取今天的新聞，每個網站 1 頁，最多 15 篇）
uv run python run_all_scrapers.py

# 自訂參數
uv run python run_all_scrapers.py --pages 3 --max-articles 50

# 指定日期
uv run python run_all_scrapers.py --date 2026-01-09

# 只儲存 JSON，不儲存到資料庫
uv run python run_all_scrapers.py --no-db

# 完整範例
uv run python run_all_scrapers.py --pages 5 --max-articles 100 --date 2026-01-09
```

**參數說明：**
- `--pages N` - 每個網站要爬取的頁數（預設: 1）
- `--max-articles N` - 每個網站最多處理的文章數（預設: 15）
- `--no-db` - 不儲存到資料庫，只儲存 JSON 檔案
- `--date YYYY-MM-DD` - 目標日期（預設: 今天）

### 方式 2: 執行單一爬蟲

進入 scrapers 資料夾執行單一爬蟲：

```bash
# TVBS
uv run python scrapers/tvbs_scraper.py

# 三立新聞
uv run python scrapers/setn_scraper.py

# 中時電子報
uv run python scrapers/chinatimes_scraper.py
```

### 方式 3: 在程式中引用

```python
from datetime import datetime
from scrapers.tvbs_scraper import TvbsScraper
from news_scraper import NewsScraperConfig
from database.operations import save_scraper_results_to_db

# 配置爬蟲
config = NewsScraperConfig(
    base_url="https://news.tvbs.com.tw/politics",
    article_tags=["article", ".article_content", ".article-body"],
)

scraper = TvbsScraper(config)

# 執行爬蟲
result = scraper.scrape_news(
    target_date=datetime.now(),
    num_pages=3,
    max_articles=30,
    output_file="results/tvbs.json"
)

# 儲存到資料庫
if result:
    stats = save_scraper_results_to_db(result, source_site="TVBS")
    print(f"成功儲存 {stats['inserted']} 篇新聞")
```

## 輸出結果

### JSON 檔案

執行後會在 `results/` 資料夾中生成 JSON 檔案：

```
results/
├── tvbs_20260109.json
├── setn_20260109.json
└── chinatimes_20260109.json
```

### 資料庫

如果啟用資料庫儲存（預設啟用），新聞會自動儲存到 PostgreSQL 資料庫中。

## 支援的新聞網站

| 網站名稱 | 檔案名稱 | 說明 |
|---------|---------|------|
| TVBS 新聞 | tvbs_scraper.py | TVBS 政治新聞 |
| 三立新聞 | setn_scraper.py | 三立政治新聞 |
| 中時電子報 | chinatimes_scraper.py | 中時政治新聞 |

## 新增新網站爬蟲

1. 在 `scrapers/` 資料夾中創建新的爬蟲檔案（參考 `example_other_site.py`）
2. 繼承 `NewsScraper` 類別並實作必要的方法
3. 在 `run_all_scrapers.py` 的 `scrapers_config` 中加入新網站配置
4. 在 `scrapers/__init__.py` 中加入新爬蟲的 import

## 排程執行

### Windows 工作排程器

使用 Windows 工作排程器設定定時執行：

1. 開啟「工作排程器」
2. 建立基本工作
3. 設定觸發程序（例如：每天早上 8:00）
4. 動作：啟動程式
   - 程式或指令碼：`uv`
   - 新增引數：`run python f:\ollama\run_all_scrapers.py --pages 5 --max-articles 50`
   - 開始於：`f:\ollama`

### Cron (Linux/Mac)

```bash
# 每天早上 8:00 執行
0 8 * * * cd /path/to/ollama && uv run python run_all_scrapers.py --pages 5 --max-articles 50
```

## 注意事項

1. **執行時間**: 每個網站爬取時間約 1-5 分鐘，取決於頁數和文章數
2. **資料庫連線**: 確保 PostgreSQL 資料庫已啟動
3. **API 服務**: 確保 Firecrawl 和 LLM 服務已啟動
4. **錯誤處理**: 單一爬蟲失敗不會影響其他爬蟲的執行
5. **結果儲存**: JSON 和資料庫會同時儲存（除非使用 --no-db）

## 疑難排解

### 問題：找不到模組

**解決方式**: 確保在專案根目錄執行，或使用 `uv run python`

### 問題：資料庫連線失敗

**解決方式**: 
```bash
# 啟動資料庫
docker-compose -f docker-compose-db.yml up -d
```

### 問題：Firecrawl 服務無法連線

**解決方式**:
```bash
# 檢查 Firecrawl 服務狀態
curl http://localhost:3002/health

# 重啟服務（如果需要）
cd firecrawl
docker-compose restart
```
