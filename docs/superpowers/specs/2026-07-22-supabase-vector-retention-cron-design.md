# Supabase 向量保留排程 (Vector-Retention Cron) — 設計

**日期:** 2026-07-22
**狀態:** 已核准設計，待寫實作計畫
**目標:** 讓 Supabase 資料庫穩定維持在 500 MB 免費額度以下，同時保留所有文章的可瀏覽 metadata。

---

## 1. 問題與量測

Supabase 免費方案上限 500 MB。實際量測（2026-07-22，經 `DATABASE_URL` 直查）：

| 項目 | 大小 | 佔比 |
|------|------|------|
| 整個 DB | 32 MB | — |
| `news_articles` 總計 | 21 MB | 66% |
| ├ 主表 metadata | 432 kB | 極小 |
| ├ TOAST（兩個 embedding） | ~8.6 MB | — |
| └ 兩個 HNSW 向量索引 | 12 MB | — |
| `article_bias` | 280 kB（reasoning 僅 111 kB） | 忽略 |
| 其餘（auth / storage / stats） | ~1 MB | 忽略 |

**結論：成本幾乎全在向量。** 1024 維 `title_embedding` + `summary_embedding`（~8 KB/列）加上兩個 HNSW 索引 ≈ `news_articles` 的 20/21 MB。純文字 metadata 微不足道。

**成長率：** 783 列橫跨 3 天（2026-07-20 → 07-22）≈ **7 MB/天**（含向量與索引）。照此速度約 60–70 天到 500 MB。

**環境事實：**
- `pg_cron` **未安裝**，但可用（1.6.4）。需一次性 `create extension pg_cron;`。
- `pgvector` 0.8.2。HNSW 刪除有支援，但索引不會自動縮小，需定期重建。
- HNSW 索引名稱：`idx_title_embedding_hnsw`、`idx_summary_embedding_hnsw`。
- pg_cron 在 `postgres` 資料庫執行（即目前所在 DB）。

> 註：`ARCHITECTURE.md` 宣稱 `summary_embedding` 幾乎全為 NULL——**已過時**。實測 759/783 列有值，兩個向量都在填。

---

## 2. 策略

依年齡 `N` 天將文章分區（採用選定策略「只刪向量、文章全留」，`N = 45`）：

- **≤ N 天：** 有 embedding、可語意搜尋（維持現狀）。
- **\> N 天：** 兩個 embedding 欄位設為 `NULL`，**保留該列**。title/summary/date/url 仍可透過 BrowsePage 與關鍵字搜尋瀏覽。

**穩態大小 ≈ 7 MB × N。** N=45 → **~315 MB**，距 500 MB 有舒適緩衝。

---

## 3. 三個組成部分

### 3.1 Python 修改（唯一的程式碼變更，且為必要）

`scripts/generate_embeddings.py` 的 `run_embeddings` 查詢會重新選取任何 `title_embedding IS NULL` 且 `title != ""` 的列（`generate_embeddings.py:79-84`）。因為 `title` 一定存在，只要把舊文章向量設 NULL，下一輪嵌入排程（約每 60 分）就會重新產生，形成無限迴圈並浪費 Jina API 呼叫。

**修正：** 在該查詢加入年齡上限過濾：

```
publish_date >= current_date - (EMBED_MAX_AGE_DAYS 天)
```

- 新增環境變數 `EMBED_MAX_AGE_DAYS`，預設 = `N`（45）。
- purge 門檻與 embed 門檻使用**同一個 N**，形成無縫分區，無重嵌迴圈、無空窗。
- 新文章 `publish_date` 恆為近期，此過濾永不阻擋正常嵌入。

### 3.2 pg_cron — 每日 purge（03:00 GMT）

`UPDATE` 與 `VACUUM` 不能共用交易，因此拆成兩個 job：

```sql
-- job: purge-old-vectors  (03:00)
select cron.schedule(
  'purge-old-vectors', '0 3 * * *',
  $$ update news_articles
       set title_embedding = null, summary_embedding = null
     where publish_date < current_date - interval '45 days'
       and title_embedding is not null $$   -- 守衛：只碰仍有向量的列，便宜且冪等
);

-- job: vacuum-articles  (03:10)
select cron.schedule(
  'vacuum-articles', '10 3 * * *',
  'VACUUM (ANALYZE) news_articles'
);
```

`VACUUM`（非 FULL）把釋放出的向量空間標記為可重用，使 DB **趨於穩態而非持續成長**。pg_cron 可直接執行單一 `VACUUM`（Supabase 官方範例）。

### 3.3 pg_cron — 每週 HNSW 重建（週日 03:30 GMT）

HNSW 索引本身不會縮小。**採用 `DROP INDEX` + `CREATE INDEX`（非 `REINDEX CONCURRENTLY`）** 來回收：

- 原因：`REINDEX CONCURRENTLY` / `VACUUM FULL` 會暫時需要約 2× 物件大小的空閒磁碟（Supabase 官方警告）。在 500 MB 上限下，重建大型 HNSW 索引可能反而衝破上限。`DROP` 先釋放舊索引，再建較小的新索引，峰值磁碟只需新索引大小。
- 代價：3:30 AM 有短暫寫鎖，且重建期間（數秒）無向量索引（搜尋退回精確掃描，在 N 天資料量下可接受）。
- `DROP INDEX` + 非 concurrent `CREATE INDEX` 可在交易內執行，pg_cron 無交易問題。

```sql
-- job: reindex-hnsw  (週日 03:30)
select cron.schedule(
  'reindex-hnsw', '30 3 * * 0',
  $$
  drop index if exists idx_title_embedding_hnsw;
  create index idx_title_embedding_hnsw on news_articles
    using hnsw (title_embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
  drop index if exists idx_summary_embedding_hnsw;
  create index idx_summary_embedding_hnsw on news_articles
    using hnsw (summary_embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
  $$
);
```

> 索引參數對齊 `database/models.py`（m=16, ef_construction=64, vector_cosine_ops）。

---

## 4. 一次性設定

```sql
create extension if not exists pg_cron;
```
（或 Dashboard → Database → Extensions 啟用。）

---

## 5. 接受的取捨與影響範圍

- **語意搜尋 / Graph 視圖** 對 > N 天的文章回傳空結果（那些列已無向量）。這正是選定的「只刪向量、文章全留」。
- **不受影響：** BrowsePage（`.from('news_articles').select`）、關鍵字搜尋、`get_distinct_sources` / `get_article_stats` / `get_bias_stats`（皆為 metadata 聚合）。
- **bias / obsidian 排程** 只處理近期文章（`days_back=3`、當日），不受影響。
- `N` 線性驅動穩態大小（~7 MB/天）。日後只需調 purge 的 interval 與 `EMBED_MAX_AGE_DAYS`，兩者需一致。

---

## 6. 驗證方式

1. **重嵌迴圈已封死：** purge 後手動跑一次 `run_embeddings`，確認舊文章不再被選中（查 `title_embedding IS NULL` 且 `publish_date < now()-45d` 的列數在跑完後不變）。
2. **purge 有效：** 執行 purge job，確認 > 45 天文章的兩個向量欄位為 NULL、列仍存在。
3. **空間趨穩：** 連續數日後 `pg_database_size` 不再單調成長。
4. **HNSW 重建：** 執行 reindex job 後，`pg_indexes_size` 回落到「近 N 天向量」的量級；搜尋仍正常回傳近期文章。
5. **前端未回歸：** SearchPage 對近期查詢正常；BrowsePage 可翻到舊文章。

---

## 7. 範圍外（YAGNI）

- 不做容量觸發式刪除（超門檻才刪）——時間分區已足夠且更簡單。
- 不刪整列文章、不動 `article_bias` / `topic_clusters`（FK cascade 已處理，且它們很小）。
- 不用 pg_repack / VACUUM FULL（DROP+CREATE 已回收索引，且更省磁碟）。
- 不改 Edge Functions / RPCs。
