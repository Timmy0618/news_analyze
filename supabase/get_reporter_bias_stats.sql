-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 記者層級的「黨派率」：該記者在期間內被判為非中立的文章比例。
-- 伺服器端聚合，不受 client 端 1000 列上限影響。
--
-- 兩個刻意的設計：
-- 1. 不 join topic_clusters —— 這裡不管主題，只問「這個人發過偏頗文章的比例」。
--    期間因此用 na.publish_date（文章何時發），不是 tc.run_date（何時被分析）。
-- 2. 先 per-article 收斂再聚合：一篇文章可能落在多個 cluster
--    （article_bias 的 unique 是 (cluster_id, article_id)），直接 count 會重複計。
--    只要任一 cluster 判為非中立，這篇就算偏頗（bool_or）。
-- 3. 以 (reporter, source_site) 為單位，不是只看 reporter：記者只有名字沒有
--    identity，中時的「王小明」和三立的「王小明」不見得是同一人，只 GROUP BY
--    名字會把兩個人的比例攪在一起。前端也照這個組合顯示成「中時 王小明」。
CREATE OR REPLACE FUNCTION get_reporter_bias_stats(
  date_from date,
  date_to date,
  min_articles int DEFAULT 3
)
RETURNS json
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.partisan_rate DESC, t.total DESC), '[]')
  FROM (
    SELECT
      a.reporter                                    AS reporter,
      a.source_site                                 AS source_site,
      COUNT(*)                                      AS total,
      COUNT(*) FILTER (WHERE a.is_partisan)         AS partisan,
      ROUND(
        COUNT(*) FILTER (WHERE a.is_partisan)::numeric / NULLIF(COUNT(*), 0),
        3
      )                                             AS partisan_rate
    FROM (
      SELECT
        na.reporter,
        na.source_site,
        bool_or(ab.verdict IN ('side_a', 'side_b')) AS is_partisan
      FROM article_bias ab
      JOIN news_articles na ON na.id = ab.article_id
      WHERE na.publish_date >= date_from
        AND na.publish_date <= date_to
        AND na.reporter IS NOT NULL
        AND na.reporter <> '未提及'
        AND na.source_site IS NOT NULL
      GROUP BY ab.article_id, na.reporter, na.source_site
    ) a
    GROUP BY a.reporter, a.source_site
    HAVING COUNT(*) >= min_articles
    ORDER BY partisan_rate DESC, total DESC
    LIMIT 50
  ) t
$$;
