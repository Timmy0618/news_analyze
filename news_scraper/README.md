# 新聞爬蟲模組

通用新聞網站爬蟲工具，支援多種新聞網站的爬取和分析。

## 專案結構

```
f:\ollama\
├── news_scraper/              # 爬蟲模組
│   ├── __init__.py           # 模組初始化
│   └── scraper.py            # 核心爬蟲類別
├── langchain_scraper.py      # 使用範例：三立新聞政治版
└── example_other_site.py     # 使用範例：其他新聞網站
```

## 使用方法

### 1. 基本使用

```python
from news_scraper import NewsScraperConfig, NewsScraper

# 配置網站參數
config = NewsScraperConfig(
    base_url="https://news-site.com/list",
    list_tags=["#NewsList"],
    article_tags=["#article-content"],
    date_pattern=r'{date}\s+\d{{2}}:\d{{2}}',
    category_pattern=r'\[([^\]]+)\]',
    link_pattern=r'\[([^\]]+)\]\((https://news-site\.com/news/\d+)\)',
    target_category="政治",  # 可選，None 表示不過濾
)

# 建立爬蟲
scraper = NewsScraper(config)

# 執行爬蟲
result = scraper.scrape_news(
    num_pages=10,        # 抓取頁數
    max_articles=15,     # 最多處理文章數
    output_file="news_result.json"
)
```

### 2. 自訂參數

```python
# 自訂 LLM 和 Firecrawl 設定
scraper = NewsScraper(
    config,
    firecrawl_url="http://localhost:3002",
    llm_url="http://localhost:8000/v1",  # 或設定環境變數 LLM_URL
    model_name="Qwen/Qwen3-4B-Instruct-2507"
)

# 如果不指定 llm_url，會自動從環境變數 LLM_URL 讀取
scraper = NewsScraper(config)

# 指定日期
from datetime import datetime
result = scraper.scrape_news(
    target_date=datetime(2026, 1, 4),
    num_pages=5
)
```

## 配置說明

### NewsScraperConfig 參數

- `base_url`: 新聞列表頁的基礎 URL
- `list_tags`: 新聞列表頁要抓取的 HTML 標籤（列表）
- `article_tags`: 文章頁要抓取的 HTML 標籤（列表）
- `date_pattern`: 日期的正則表達式（使用 `{date}` 作為佔位符）
- `category_pattern`: 類別的正則表達式
- `link_pattern`: 連結的正則表達式（需包含兩個群組：標題和連結）
- `target_category`: 目標類別（如 "政治"），`None` 表示不過濾

## 輸出格式

```json
{
  "articles": [
    {
      "標題": "新聞標題",
      "記者": "記者名字",
      "大綱": "- 重點1\n- 重點2\n- 重點3",
      "日期": "2026/01/04",
      "連結": "https://..."
    }
  ]
}
```

## 範例

### 三立新聞政治版

```bash
uv run langchain_scraper.py
```

### 其他網站範例

```bash
uv run example_other_site.py
```

## 依賴套件

- `langchain-openai`: LLM 支援
- `requests`: HTTP 請求
- Python 3.14+
