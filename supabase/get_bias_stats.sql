-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 跨時間窗彙總各媒體的「黨派率」：被判為非中立（side_a/side_b）的文章比例。
-- 伺服器端聚合，不受 client 端 1000 列上限影響。
CREATE OR REPLACE FUNCTION get_bias_stats(date_from date, date_to date)
RETURNS json
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.partisan_rate DESC, t.total DESC), '[]')
  FROM (
    SELECT
      na.source_site                                              AS source_site,
      COUNT(*)                                                    AS total,
      COUNT(*) FILTER (WHERE ab.verdict = 'neutral')              AS neutral,
      COUNT(*) FILTER (WHERE ab.verdict IN ('side_a', 'side_b'))  AS partisan,
      ROUND(
        COUNT(*) FILTER (WHERE ab.verdict IN ('side_a', 'side_b'))::numeric
        / NULLIF(COUNT(*), 0),
        3
      )                                                           AS partisan_rate
    FROM article_bias ab
    JOIN topic_clusters tc ON tc.id = ab.cluster_id
    JOIN news_articles na ON na.id = ab.article_id
    WHERE tc.run_date >= date_from
      AND tc.run_date <= date_to
      AND na.source_site IS NOT NULL
    GROUP BY na.source_site
  ) t
$$;
