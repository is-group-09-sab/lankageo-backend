import asyncio
import os
from app.services.auth_service import get_supabase

async def test_insert():
    supabase = get_supabase()
    
    # Try to find a valid result_id
    results = supabase.table("live_flood_results").select("result_id").limit(1).execute()
    if not results.data:
        print("No live flood results found. Run an analysis first.")
        return
        
    result_id = results.data[0]["result_id"]
    print(f"Testing insertion for result_id: {result_id}")
    
    dummy_polygon = {
        "result_id": result_id,
        "severity_level": "moderate",
        "area_km2": 0.5,
        "water_type": "new_flood",
        "geom": {
            "type": "Polygon",
            "coordinates": [[[80.0, 6.0], [80.1, 6.0], [80.1, 6.1], [80.0, 6.1], [80.0, 6.0]]]
        }
    }
    
    try:
        response = supabase.table("flood_polygons").insert(dummy_polygon).execute()
        print("Insertion response:", response.data)
    except Exception as e:
        print(f"Insertion failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_insert())
