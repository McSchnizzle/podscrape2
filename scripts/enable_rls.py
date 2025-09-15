#!/usr/bin/env python3
"""
Enable Row Level Security (RLS) on Supabase tables.

This script applies RLS policies to the feeds, episodes, and digests tables.
Run this after your Supabase database is set up with the schema.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def enable_rls():
    """Apply RLS policies to Supabase tables."""

    rls_sql = """
    -- Enable RLS on all tables
    ALTER TABLE feeds ENABLE ROW LEVEL SECURITY;
    ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
    ALTER TABLE digests ENABLE ROW LEVEL SECURITY;

    -- Create a service role policy that allows full access
    CREATE POLICY "Service role has full access on feeds" ON feeds
      FOR ALL USING (auth.role() = 'service_role');

    CREATE POLICY "Service role has full access on episodes" ON episodes
      FOR ALL USING (auth.role() = 'service_role');

    CREATE POLICY "Service role has full access on digests" ON digests
      FOR ALL USING (auth.role() = 'service_role');

    -- Create authenticated user policies for read access
    CREATE POLICY "Authenticated users can read feeds" ON feeds
      FOR SELECT USING (auth.role() = 'authenticated');

    CREATE POLICY "Authenticated users can read episodes" ON episodes
      FOR SELECT USING (auth.role() = 'authenticated');

    CREATE POLICY "Authenticated users can read digests" ON digests
      FOR SELECT USING (auth.role() = 'authenticated');
    """

    try:
        load_dotenv()
        db_url = require_database_url()
        engine = create_engine(db_url)

        print("🔒 Enabling Row Level Security (RLS) on Supabase tables...")

        # Execute RLS setup
        with engine.connect() as conn:
            conn.execute(text(rls_sql))
            conn.commit()

        print("✅ RLS enabled successfully!")
        print("\nRLS Policies Applied:")
        print("- Service role: Full access to all tables")
        print("- Authenticated users: Read access to all tables")
        print("\nNote: Your pipeline uses service_role credentials, so it will bypass RLS.")

    except Exception as e:
        print(f"❌ Error enabling RLS: {e}")
        print("\nYou can also run the SQL manually in Supabase:")
        print("1. Go to your Supabase project SQL editor")
        print("2. Copy and paste the contents of supabase_rls_setup.sql")
        print("3. Execute the SQL")
        return False

    return True


if __name__ == "__main__":
    enable_rls()