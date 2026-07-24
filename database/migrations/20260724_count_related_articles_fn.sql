-- PostgreSQL function: 計算某日與 query 向量「相關」的文章數（平均相似度 > threshold）
-- 供 analyze_news_topics.count_related_articles_by_vector 呼叫。
--
-- 與 match_articles（見 20260513_match_articles_fn.sql）同一套 NULL 規則：
-- 大綱 (summary) 目前刻意留空，因此 summary_embedding 對多數文章為 NULL。
-- 本函式只要求 title_embedding 存在；summary 相似度在缺漏時以 COALESCE 退回
-- title_embedding，讓文章仍能被計入。先前 Python 端的
-- `AND summary_embedding IS NOT NULL` 會把幾乎所有文章濾掉，使計數恆為 0——
-- 這個 RPC 是修正後的單一真實來源。
--
-- 相似度採「標題與摘要相似度的平均」，等同 match_articles 的 'both' 分支。

CREATE OR REPLACE FUNCTION count_related_articles(
  query_embedding vector(1024),
  target_date     date,
  threshold       float DEFAULT 0.3
)
RETURNS int
LANGUAGE sql STABLE
AS $$
  SELECT count(*)::int
  FROM news_articles
  WHERE title_embedding IS NOT NULL
    AND publish_date = target_date
    AND (
      (
        (1 - (title_embedding <=> query_embedding))
        + (1 - COALESCE(summary_embedding <=> query_embedding, title_embedding <=> query_embedding))
      ) / 2
    ) > threshold;
$$;
