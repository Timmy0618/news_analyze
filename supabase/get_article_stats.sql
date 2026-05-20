-- 在 Supabase Dashboard → SQL Editor 執行此檔案
CREATE OR REPLACE FUNCTION get_article_stats(since_date date)
RETURNS json
LANGUAGE sql
STABLE
AS $$
  SELECT json_build_object(
    'total', (
      SELECT COUNT(*) FROM news_articles WHERE publish_date >= since_date
    ),
    'daily', (
      SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.publish_date), '[]')
      FROM (
        SELECT publish_date, COUNT(*) AS count
        FROM news_articles
        WHERE publish_date >= since_date
        GROUP BY publish_date
        ORDER BY publish_date
      ) t
    ),
    'by_site', (
      SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.count DESC), '[]')
      FROM (
        SELECT source_site, COUNT(*) AS count
        FROM news_articles
        WHERE publish_date >= since_date
        GROUP BY source_site
        ORDER BY count DESC
      ) t
    )
  )
$$;
