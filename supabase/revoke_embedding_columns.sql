-- 在 Supabase Dashboard → SQL Editor 執行此檔案
-- 防護：撤銷 anon / authenticated 對 embedding 欄位的讀取權限，
-- 確保 1024 維向量永遠不會經由 PostgREST API 外流（egress 防呆）。
-- search 走 Edge Function 的 service_role 呼叫 match_articles，不受影響；
-- anon 直接呼叫 match_articles 會因欄位權限被拒（設計如此）。
--
-- 注意：新建的 Supabase 專案會對 public schema 的資料表自動套用
-- table-level 的 default privileges，直接把 anon / authenticated 授權到
-- 「整張表」（ALL：SELECT/INSERT/UPDATE/DELETE...）。這種 table-level 授權
-- 會蓋過針對單一欄位的 REVOKE（`REVOKE SELECT (col) ... FROM role` 只能撤銷
-- 「欄位層級」曾經單獨授予的權限，無法收窄早已存在、涵蓋全表全欄位的
-- table-level 授權），所以單純 REVOKE 欄位權限在這種情況下是無效的。
--
-- 因此改用「先收回整表權限，再用欄位白名單重新授權」的作法：
-- 先 REVOKE ALL（拿掉 table-level 授權），再用 GRANT SELECT (欄位列表)
-- 明確只把 embedding 以外的欄位授權回去，讓欄位層級限制真正生效。
REVOKE ALL ON news_articles FROM anon, authenticated;

GRANT SELECT (
  id,
  title,
  reporter,
  summary,
  publish_date,
  source_url,
  source_site,
  created_at,
  updated_at
) ON news_articles TO anon, authenticated;
