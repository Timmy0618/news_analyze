-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 回傳所有不重複的新聞來源（給前端下拉選單用）。
-- 取代前端 `select('source_site')` 的全表掃描，把每次 ~220KB egress 降到 <1KB。
CREATE OR REPLACE FUNCTION get_distinct_sources()
RETURNS text[]
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(array_agg(source_site ORDER BY source_site), '{}')
  FROM (
    SELECT DISTINCT source_site
    FROM news_articles
    WHERE source_site IS NOT NULL
  ) t
$$;
