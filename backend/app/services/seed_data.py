import asyncio
from supabase import create_client
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from app.core.config import settings
async def seed():
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    data = [{'id': 'test', 'title': 'Test Case'}]
    supabase.table('case_studies').upsert(data).execute()
if __name__ == '__main__':
    asyncio.run(seed())
