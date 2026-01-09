# 向量嵌入生成使用說明

本腳本使用 Jina AI API 為新聞文章生成向量嵌入（Embedding），並存儲到資料庫。

## 功能

- 使用 Jina AI 的 `jina-embeddings-v3` 模型生成 1536 維度的向量
- 為文章的標題（title）和摘要（summary）分別生成嵌入
- 批次處理，避免 API 請求過多
- 只處理缺少嵌入的文章（可選強制更新）
- 詳細的進度顯示和統計資訊

## 環境設定

### 1. 取得 Jina AI API 金鑰

前往 [Jina AI](https://jina.ai/) 註冊並取得 API 金鑰。

### 2. 設定環境變數

在 `.env` 檔案中添加：

```env
JINA_API_KEY=your_jina_api_key_here
```

## 使用方式

### 基本用法

```bash
# 處理所有缺少嵌入的文章
uv run python generate_embeddings.py

# 指定批次大小（每次處理 20 篇）
uv run python generate_embeddings.py --batch-size 20

# 只處理前 100 篇文章
uv run python generate_embeddings.py --limit 100

# 強制更新所有文章（包括已有嵌入的）
uv run python generate_embeddings.py --force

# 組合使用
uv run python generate_embeddings.py --batch-size 20 --limit 50
```

### 參數說明

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `--batch-size N` | 每批次處理的文章數量 | 10 |
| `--limit N` | 最多處理的文章數量 | 無限制 |
| `--force` | 強制更新已有嵌入的文章 | False |

## 工作流程

1. **連接資料庫** - 查詢需要處理的文章
2. **批次處理** - 將文章分批，避免一次請求太多
3. **生成嵌入** - 呼叫 Jina AI API 生成向量
4. **存儲結果** - 將向量存回資料庫的對應欄位
5. **顯示統計** - 輸出處理結果統計

## 輸出範例

```
================================================================================
開始生成文章向量嵌入
================================================================================
✓ Jina AI API 初始化成功
模式: 只處理缺少嵌入的文章
找到 150 篇需要處理的文章
批次大小: 10
================================================================================

處理批次 1/15 (10 篇文章)
  生成 10 個標題嵌入...
  ✓ 標題嵌入生成成功
  生成 10 個摘要嵌入...
  ✓ 摘要嵌入生成成功
  ✓ 已更新: 立院三讀通過！最低工資法明年上路...
  ✓ 已更新: 藍白合作推動...
  ...

================================================================================
嵌入生成完成 - 統計資訊
================================================================================
總文章數: 150
  ✓ 成功: 150
  ✗ 失敗: 0

生成的嵌入:
  標題嵌入: 150
  摘要嵌入: 145
================================================================================
```

## 整合到工作流程

### 方式 1: 爬蟲完成後自動生成嵌入

```bash
# 先執行爬蟲
uv run python run_all_scrapers.py --pages 5 --max-articles 50

# 再生成嵌入
uv run python generate_embeddings.py
```

### 方式 2: 整合到一個腳本

創建 `run_with_embeddings.sh`（Windows 用 `.bat`）:

```bash
#!/bin/bash
# 執行爬蟲
uv run python run_all_scrapers.py --pages 5 --max-articles 50

# 生成嵌入
uv run python generate_embeddings.py --batch-size 20

echo "完成！"
```

### 方式 3: 在 Python 中調用

```python
from generate_embeddings import generate_embeddings_for_articles

# 執行爬蟲後...
result = scraper.scrape_news(...)

# 立即生成嵌入
generate_embeddings_for_articles(batch_size=20)
```

## API 費用說明

Jina AI API 的計費方式：
- 免費額度：每月 1M tokens
- 超過後按使用量計費

建議：
- 使用 `--batch-size` 控制每次處理數量
- 使用 `--limit` 限制總處理數量
- 不使用 `--force` 避免重複生成

## 資料庫欄位

生成的嵌入會存儲在以下欄位：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `title_embedding` | Vector(1536) | 標題的向量嵌入 |
| `summary_embedding` | Vector(1536) | 摘要的向量嵌入 |

## 使用嵌入進行搜索

生成嵌入後，可以使用向量搜索來找相似文章：

```python
from database.models import NewsArticle
from database.config import Session

db = Session()

# 使用向量相似度搜索（需要 pgvector）
# 假設 query_embedding 是查詢文本的嵌入
similar_articles = db.query(NewsArticle).order_by(
    NewsArticle.title_embedding.cosine_distance(query_embedding)
).limit(10).all()
```

## 注意事項

1. **API 金鑰** - 確保已設定 `JINA_API_KEY` 環境變數
2. **網路連線** - 需要穩定的網路連線來訪問 Jina AI API
3. **批次大小** - 建議 10-50 之間，太大可能超過 API 限制
4. **錯誤處理** - 單篇文章失敗不影響其他文章
5. **資料庫連線** - 確保 PostgreSQL 資料庫正在運行

## 疑難排解

### 問題：API 金鑰錯誤

```
✗ 錯誤: 請設定 JINA_API_KEY 環境變數或提供 API 金鑰
```

**解決方式**: 在 `.env` 檔案中設定 `JINA_API_KEY`

### 問題：API 請求失敗

```
✗ Jina API 請求失敗: HTTPError...
```

**解決方式**: 
1. 檢查網路連線
2. 確認 API 金鑰是否正確
3. 檢查 Jina AI 服務狀態

### 問題：資料庫連線失敗

**解決方式**: 確保 PostgreSQL 資料庫正在運行
```bash
docker-compose -f docker-compose-db.yml up -d
```

## 進階用法

### 自訂 Jina 模型參數

在 `JinaEmbeddingGenerator` 類別中可以調整：
- `model`: 使用的模型名稱
- `dimensions`: 向量維度（需與資料庫一致）
- `task`: 任務類型（retrieval.passage, retrieval.query 等）

### 處理特定來源的文章

```python
from database.models import NewsArticle
from database.config import Session

db = Session()
articles = db.query(NewsArticle).filter_by(source_site="TVBS").all()

# 只為 TVBS 的文章生成嵌入
# 需要修改腳本來支持這個功能
```
