-- Enable Row Level Security on news_articles
-- Allows public read-only access via Supabase anon key
-- Blocks INSERT, UPDATE, DELETE for unauthenticated users

ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;

-- Allow anon (and authenticated) to SELECT all rows
CREATE POLICY "public read"
  ON news_articles
  FOR SELECT
  TO anon
  USING (true);
