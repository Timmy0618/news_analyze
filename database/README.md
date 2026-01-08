# 新聞爬蟲資料庫

## 資料庫架構

使用 PostgreSQL + pgvector 擴展來支援向量語義搜尋。

### 資料表: news_articles

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| id | Integer | 主鍵 |
| title | String(500) | 新聞標題 |
| reporter | String(100) | 記者 |
| summary | Text | 新聞大綱 |
| content | Text | 完整內容（選填） |
| publish_date | String(20) | 發布日期 (YYYY/MM/DD) |
| source_url | String(1000) | 新聞連結（唯一） |
| source_site | String(50) | 來源網站 |
| title_embedding | Vector(1536) | 標題向量 |
| summary_embedding | Vector(1536) | 大綱向量 |
| created_at | DateTime(TZ) | 建立時間 |
| updated_at | DateTime(TZ) | 更新時間 |

### 索引

- `idx_title`: 標題索引（一般搜尋）
- `idx_publish_date`: 日期索引
- `idx_source_site`: 來源網站索引
- `idx_title_embedding_hnsw`: 標題向量 HNSW 索引（語義搜尋）
- `idx_summary_embedding_hnsw`: 大綱向量 HNSW 索引（語義搜尋）

## 安裝依賴

```bash
pip install sqlalchemy psycopg2-binary alembic pgvector python-dotenv
```

## 環境設定

在 `.env` 檔案中設定資料庫連線：

```env
DATABASE_URL=postgresql://username:password@localhost:5432/news_db
```

## 資料庫初始化

### 1. 建立資料庫

```bash
# 使用 psql 建立資料庫
createdb news_db

# 或使用 SQL
psql -U postgres -c "CREATE DATABASE news_db;"
```

### 2. 執行遷移

```bash
# 初始化 Alembic（如果還沒初始化）
alembic init alembic

# 查看當前版本
alembic current

# 升級到最新版本
alembic upgrade head

# 查看遷移歷史
alembic history

# 降級一個版本
alembic downgrade -1

# 降級到特定版本
alembic downgrade 001
```

### 3. 創建新的遷移

```bash
# 自動生成遷移腳本（偵測模型變更）
alembic revision --autogenerate -m "描述變更內容"

# 手動建立空白遷移腳本
alembic revision -m "描述變更內容"
```

## 使用範例

### 插入新聞資料

```python
from database import Session, NewsArticle
from datetime import datetime

# 建立 session
db = Session()

try:
    # 建立新聞物件
    article = NewsArticle(
        title="新聞標題",
        reporter="記者姓名",
        summary="新聞大綱內容...",
        publish_date="2026/01/07",
        source_url="https://example.com/news/123",
        source_site="TVBS"
    )
    
    # 加入到 session
    db.add(article)
    
    # 提交變更
    db.commit()
    
    # 重新載入物件以獲取自動生成的 ID
    db.refresh(article)
    print(f"新聞已儲存，ID: {article.id}")
    
except Exception as e:
    db.rollback()
    print(f"錯誤: {e}")
finally:
    db.close()
```

### 查詢新聞

```python
from database import Session, NewsArticle

db = Session()

try:
    # 查詢所有新聞
    all_news = db.query(NewsArticle).all()
    
    # 依日期篩選
    today_news = db.query(NewsArticle).filter(
        NewsArticle.publish_date == "2026/01/07"
    ).all()
    
    # 依來源網站篩選
    tvbs_news = db.query(NewsArticle).filter(
        NewsArticle.source_site == "TVBS"
    ).all()
    
    # 標題搜尋（包含關鍵字）
    search_results = db.query(NewsArticle).filter(
        NewsArticle.title.contains("選舉")
    ).all()
    
finally:
    db.close()
```

### 向量語義搜尋

```python
from database import Session, NewsArticle
from sqlalchemy import select
from pgvector.sqlalchemy import Vector

db = Session()

try:
    # 假設已有查詢文本的向量
    query_embedding = [0.1, 0.2, ...]  # 1536 維向量
    
    # 使用餘弦相似度搜尋最相關的新聞
    results = db.query(
        NewsArticle,
        NewsArticle.title_embedding.cosine_distance(query_embedding).label('distance')
    ).order_by('distance').limit(10).all()
    
    for article, distance in results:
        print(f"相似度: {1 - distance:.4f}, 標題: {article.title}")
        
finally:
    db.close()
```

## 維護指令

### 備份資料庫

```bash
pg_dump -U postgres news_db > backup.sql
```

### 還原資料庫

```bash
psql -U postgres news_db < backup.sql
```

### 檢查 pgvector 擴展

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 查看資料表大小

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename = 'news_articles';
```
