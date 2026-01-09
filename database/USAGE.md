# 資料庫儲存功能使用說明

本文檔說明如何在不同的新聞爬蟲中使用資料庫儲存功能。

## 功能概述

`database/operations.py` 提供了通用的資料庫操作函數，可以被所有爬蟲使用。

### 主要函數

1. **save_scraper_results_to_db** - 儲存爬蟲結果到資料庫
2. **save_articles_batch** - 批次儲存文章列表
3. **get_articles_by_date** - 根據日期查詢文章
4. **get_articles_by_source** - 根據來源網站查詢文章

## 快速開始

### 在爬蟲的 main 函數中使用

```python
def main():
    """主程式"""
    from datetime import datetime
    from database.operations import save_scraper_results_to_db
    
    # 執行爬蟲
    result = scraper.scrape_news(
        target_date=datetime.now(),
        num_pages=5,
        max_articles=50,
        output_file="result.json"
    )
    
    if result:
        # 儲存到資料庫
        stats = save_scraper_results_to_db(
            result=result,
            source_site="TVBS"  # 修改為你的網站名稱
        )
        
        print(f"資料庫儲存完成：新增 {stats['inserted']} 篇，更新 {stats['updated']} 篇")
```

## 資料格式

### 輸入格式（爬蟲結果）

```json
{
  "articles": [
    {
      "標題": "新聞標題",
      "記者": "記者姓名",
      "大綱": "新聞大綱或摘要",
      "日期": "2026/01/09",
      "連結": "https://news.example.com/article"
    }
  ]
}
```

**注意：** 
- 支援中文欄位（標題、記者、大綱、日期、連結）和英文欄位（title, reporter, summary, publish_date, source_url）
- 必填欄位：標題、日期、連結
- 選填欄位：記者、大綱、內容

## 使用範例

### 範例 1：TVBS 爬蟲

```python
from datetime import datetime
from database.operations import save_scraper_results_to_db

result = scraper.scrape_news(
    target_date=datetime.now(),
    num_pages=1,
    max_articles=10,
    output_file="tvbs_result.json"
)

if result:
    stats = save_scraper_results_to_db(result=result, source_site="TVBS")
    print(f"新增 {stats['inserted']} 篇，更新 {stats['updated']} 篇")
```

### 範例 2：批次儲存

```python
from database.operations import save_articles_batch

articles = [
    {"標題": "新聞1", "記者": "記者A", "日期": "2026/01/09", "連結": "http://..."},
    {"標題": "新聞2", "記者": "記者B", "日期": "2026/01/09", "連結": "http://..."},
]

stats = save_articles_batch(articles, source_site="TVBS")
```

### 範例 3：查詢文章

```python
from database.operations import get_articles_by_date, get_articles_by_source

# 查詢特定日期的文章
articles = get_articles_by_date("2026/01/09", source_site="TVBS")

# 查詢特定網站的最新文章
articles = get_articles_by_source("TVBS", limit=50)

for article in articles:
    print(f"{article.title} - {article.reporter}")
```

## 功能特性

1. **自動去重**：根據 `source_url` 自動判斷是否重複
2. **智能更新**：如果文章已存在但內容有變更，自動更新
3. **錯誤處理**：單篇失敗不影響其他文章
4. **詳細統計**：回傳新增、更新、跳過、失敗的數量

## 統計資訊

函數會回傳以下統計資訊：

```python
{
    "total": 總文章數,
    "inserted": 成功新增數,
    "updated": 更新數,
    "skipped": 跳過數（已存在且未更新）,
    "failed": 失敗數
}
```

## 其他爬蟲範例

可以用相同方式修改其他爬蟲：

```python
# setn_scraper.py
stats = save_scraper_results_to_db(result=result, source_site="三立")

# chinatimes_scraper.py
stats = save_scraper_results_to_db(result=result, source_site="中時")
```
