-- 補齊 20260513_rls_read_only.sql 之後新增的三張表。
-- anon 唯讀;寫入走 postgres role(後端 DATABASE_URL)與 service_role(edge functions),不受 RLS 限制。
-- get_distinct_sources / get_article_stats / get_bias_stats 皆非 SECURITY DEFINER,
-- 以呼叫者(anon)身分讀表,故 RLS 政策必須涵蓋這些表。

ALTER TABLE news_topic_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_bias ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read" ON news_topic_statistics FOR SELECT TO anon USING (true);
CREATE POLICY "public read" ON topic_clusters FOR SELECT TO anon USING (true);
CREATE POLICY "public read" ON article_bias FOR SELECT TO anon USING (true);
