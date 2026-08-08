import asyncio
import os
import sys
from app.services.auth_service import get_supabase

async def check():
    supabase = get_supabase()
    try:
        # Fetch the latest 5 live flood results
        results_resp = supabase.table("live_flood_results").select("*").order("created_at", desc=True).limit(5).execute()
        print("=== Latest Live Flood Results ===")
        if not results_resp.data:
            print("No live flood results found.")
        for row in results_resp.data:
            print(f"ID: {row.get('result_id')}, Request ID: {row.get('request_id')}, Created At: {row.get('created_at')}")
            print(f"  Affected Area: {row.get('affected_area_km2')} km2, Confidence: {row.get('confidence_score')}")
            print(f"  Tile URL: {row.get('tile_url')}")
            print("-" * 40)
        
        # Fetch latest flood polygons associated with these results
        if results_resp.data:
            print("=== Polygons Per Live Flood Result ===")
            for row in results_resp.data:
                rid = row.get('result_id')
                poly_count_resp = supabase.table("flood_polygons").select("count", count="exact").eq("result_id", rid).execute()
                print(f"Result ID: {rid}")
                print(f"  Created At: {row.get('created_at')}")
                print(f"  Polygon Count: {poly_count_resp.count}")
                print("-" * 40)
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    asyncio.run(check())
