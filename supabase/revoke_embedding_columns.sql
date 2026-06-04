-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 防護：撤銷 anon / authenticated 對 embedding 欄位的讀取權限，
-- 確保 1024 維向量永遠不會經由 PostgREST API 外流（egress 防呆）。
-- match_articles / graph 等 RPC 與 Edge Function 用 service_role 或 SECURITY DEFINER，不受影響。
REVOKE SELECT (title_embedding, summary_embedding) ON news_articles FROM anon;
REVOKE SELECT (title_embedding, summary_embedding) ON news_articles FROM authenticated;
