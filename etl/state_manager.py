from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("SUPABASE_DB_URL not loaded")

import psycopg2

class StateManager:
    """Database-backed ETL state (replaces state.json)"""

    def __init__(self):
        self.conn = psycopg2.connect(DB_URL)

    def get(self, key):
        """Get state value"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM public.etl_state WHERE key = %s", (key,))
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None

    def set(self, key, value):
        """Set state value (upsert)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO public.etl_state (key, value, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = now()
        """, (key, str(value)))
        self.conn.commit()
        cursor.close()

    def close(self):
        self.conn.close()


# Test
if __name__ == "__main__":
    sm = StateManager()
    last_fetch = sm.get('last_recall_fetch')
    print(f"✅ Last recall fetch: {last_fetch}")

    # Test write
    sm.set('last_recall_fetch', '2025-01-01')
    updated = sm.get('last_recall_fetch')
    print(f"✅ Updated to: {updated}")

    sm.close()
