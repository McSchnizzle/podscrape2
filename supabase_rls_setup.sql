-- Supabase Row Level Security (RLS) Setup
-- Run this SQL in your Supabase SQL Editor to enable RLS and create policies

-- Enable RLS on all tables
ALTER TABLE feeds ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE digests ENABLE ROW LEVEL SECURITY;

-- Create a service role policy that allows full access
-- This allows your application to read/write without restrictions
CREATE POLICY "Service role has full access on feeds" ON feeds
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access on episodes" ON episodes
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access on digests" ON digests
  FOR ALL USING (auth.role() = 'service_role');

-- Create authenticated user policies for read access
-- This allows your web UI (if using user authentication) to read data
CREATE POLICY "Authenticated users can read feeds" ON feeds
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read episodes" ON episodes
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read digests" ON digests
  FOR SELECT USING (auth.role() = 'authenticated');

-- If you want to allow public read access to feeds and digests (for RSS/public access)
-- Uncomment the following policies:

-- CREATE POLICY "Public can read active feeds" ON feeds
--   FOR SELECT USING (active = true);

-- CREATE POLICY "Public can read published digests" ON digests
--   FOR SELECT USING (published_at IS NOT NULL);

-- Note: For your pipeline scripts and web UI to work, ensure you're using
-- the service_role key in your DATABASE_URL, not the anon key.
-- The service_role key bypasses RLS, which is what you want for backend operations.