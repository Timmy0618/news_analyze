-- PostgreSQL function for pgvector semantic search
-- Called by Supabase Edge Function via supabase.rpc('match_articles', {...})
--
-- 注意：大綱 (summary) 目前刻意留空 (見 CLAUDE.md 爬蟲架構說明)，
-- 因此 summary_embedding 對所有文章都可能是 NULL。本函式只要求
-- title_embedding 存在即可回傳該筆資料；當 summary_embedding 缺漏時，
-- 'summary' 與 'both' 的相似度計算會退回使用 title_embedding，
-- 讓文章仍能依標題相似度被排序，而不是整筆被過濾掉。

CREATE OR REPLACE FUNCTION match_articles(
  query_embedding  vector(1024),
  match_count      int     DEFAULT 10,
  search_field     text    DEFAULT 'both',
  filter_source    text    DEFAULT NULL,
  filter_date_from date    DEFAULT NULL,
  filter_date_to   date    DEFAULT NULL
)
RETURNS TABLE (
  id           int,
  title        text,
  summary      text,
  source_url   text,
  source_site  text,
  publish_date date,
  reporter     text,
  similarity   float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    title,
    summary,
    source_url,
    source_site,
    publish_date,
    reporter,
    CASE search_field
      WHEN 'title'   THEN 1 - (title_embedding <=> query_embedding)
      WHEN 'summary' THEN 1 - COALESCE(summary_embedding <=> query_embedding, title_embedding <=> query_embedding)
      ELSE 1 - (
        (
          (title_embedding <=> query_embedding)
          + COALESCE(summary_embedding <=> query_embedding, title_embedding <=> query_embedding)
        ) / 2
      )
    END AS similarity
  FROM news_articles
  WHERE
    title_embedding IS NOT NULL
    AND (filter_source    IS NULL OR source_site   = filter_source)
    AND (filter_date_from IS NULL OR publish_date >= filter_date_from)
    AND (filter_date_to   IS NULL OR publish_date <= filter_date_to)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;
