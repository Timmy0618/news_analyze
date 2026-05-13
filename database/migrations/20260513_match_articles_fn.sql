-- PostgreSQL function for pgvector semantic search
-- Called by Supabase Edge Function via supabase.rpc('match_articles', {...})

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
      WHEN 'title'   THEN 1 - (title_embedding   <=> query_embedding)
      WHEN 'summary' THEN 1 - (summary_embedding <=> query_embedding)
      ELSE 1 - (
        ((title_embedding <=> query_embedding) + (summary_embedding <=> query_embedding)) / 2
      )
    END AS similarity
  FROM news_articles
  WHERE
    title_embedding   IS NOT NULL
    AND summary_embedding IS NOT NULL
    AND (filter_source    IS NULL OR source_site   = filter_source)
    AND (filter_date_from IS NULL OR publish_date >= filter_date_from)
    AND (filter_date_to   IS NULL OR publish_date <= filter_date_to)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;
