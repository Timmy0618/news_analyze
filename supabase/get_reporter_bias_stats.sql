-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 記者層級的「中立率」：該記者在期間內被判為中立的文章比例。低 = 立場鮮明。
-- 伺服器端聚合，不受 client 端 1000 列上限影響。
--
-- 四個刻意的設計：
-- 1. 不 join topic_clusters —— 這裡不管主題，只問「這個人發過偏頗文章的比例」。
--    期間因此用 na.publish_date（文章何時發），不是 tc.run_date（何時被分析）。
-- 2. 先 per-article 收斂再聚合：一篇文章可能落在多個 cluster
--    （article_bias 的 unique 是 (cluster_id, article_id)），直接 count 會重複計。
--    只要任一 cluster 判為非中立，這篇就算偏頗（bool_or）。
-- 3. 以 (reporter, source_site) 為單位，不是只看 reporter：記者只有名字沒有
--    identity，中時的「王小明」和三立的「王小明」不見得是同一人，只 GROUP BY
--    名字會把兩個人的比例攪在一起。前端也照這個組合顯示成「中時 王小明」。
-- 4. reporter 欄位用「、」分隔雙掛名（如「張聰秋、張瑞楨」），unnest 後每個人
--    各自計一次——同一篇文章兩個人都算數。沒有 article_reporters 關聯表，
--    因為一個 unnest 就夠了，多一張表要 migration、要回填、要維護。
CREATE OR REPLACE FUNCTION get_reporter_bias_stats(
  date_from date,
  date_to date,
  min_articles int DEFAULT 3
)
RETURNS json
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.neutral_rate ASC, t.total DESC), '[]')
  FROM (
    SELECT
      a.reporter                                    AS reporter,
      a.source_site                                 AS source_site,
      COUNT(*)                                      AS total,
      COUNT(*) FILTER (WHERE NOT a.is_partisan)     AS neutral,
      ROUND(
        COUNT(*) FILTER (WHERE NOT a.is_partisan)::numeric / NULLIF(COUNT(*), 0),
        3
      )                                             AS neutral_rate
    FROM (
      SELECT
        btrim(r.name)                               AS reporter,
        na.source_site,
        bool_or(ab.verdict IN ('side_a', 'side_b')) AS is_partisan
      FROM article_bias ab
      JOIN news_articles na ON na.id = ab.article_id
      CROSS JOIN LATERAL unnest(string_to_array(na.reporter, '、')) AS r(name)
      WHERE na.publish_date >= date_from
        AND na.publish_date <= date_to
        AND na.reporter IS NOT NULL
        AND na.reporter <> '未提及'
        AND na.source_site IS NOT NULL
        AND btrim(r.name) <> ''
      GROUP BY ab.article_id, btrim(r.name), na.source_site
    ) a
    GROUP BY a.reporter, a.source_site
    HAVING COUNT(*) >= min_articles
    ORDER BY neutral_rate ASC, total DESC
    LIMIT 50
  ) t
$$;
