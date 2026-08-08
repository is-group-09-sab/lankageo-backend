import asyncio
from app.services.auth_service import get_supabase

async def main():
    supabase = get_supabase()
    response = supabase.table("flood_polygons").select("count", count="exact").execute()
    print(f"Total Polygons in database: {response.count}")
    
    if response.count > 0:
        latest = supabase.table("flood_polygons").select("*").limit(1).execute()
        print("Latest polygon sample:", latest.data)

if __name__ == "__main__":
    asyncio.run(main())
