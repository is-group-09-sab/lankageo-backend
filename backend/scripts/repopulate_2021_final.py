import asyncio
from datetime import datetime
import os
import sys

# Add the current directory to path
sys.path.append(os.getcwd())

from app.services.gee_service import gee_service
from app.services.auth_service import get_supabase
from app.services.flood_service import flood_service
from app.schemas.flood import FloodAnalysisRequest

async def repopulate_2021():
    print("--- Starting REFINED 2021 Flood Data Repopulation ---")
    
    # 1. Initialize Supabase
    sb = get_supabase()
    
    # 2. Delete existing live flood data
    print("Wiping previous results to ensure clean display...")
    try:
        live_requests = sb.table("requests").select("request_id").eq("analysis_type", "live").execute()
        request_ids = [r["request_id"] for r in live_requests.data]
        if request_ids:
            live_results = sb.table("live_flood_results").select("result_id").in_("request_id", request_ids).execute()
            result_ids = [r["result_id"] for r in live_results.data]
            if result_ids:
                sb.table("flood_polygons").delete().in_("result_id", result_ids).execute()
                sb.table("live_flood_results").delete().in_("result_id", result_ids).execute()
            sb.table("requests").delete().in_("request_id", request_ids).execute()
        print("Database cleared.")
    except Exception as e:
        print(f"Cleanup error: {e}")

    # 3. Run Analysis for June 2021 Kelani Flood
    lat, lng = 6.927, 79.861
    radius_km = 10
    override_date = "2021-06-03"
    
    print(f"Running REFINED analysis for {lat}, {lng} with 10km radius...")
    request = FloodAnalysisRequest(lat=lat, lng=lng, radius_km=radius_km, override_date=override_date)
    
    try:
        result = await flood_service.process_flood_analysis(request)
        print("\n--- Repopulation Successful ---")
        print(f"Status: {result.get('risk_level')}")
        print(f"Polygons Inserted: {len(result.get('geojson', {}).get('features', []))}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(repopulate_2021())
