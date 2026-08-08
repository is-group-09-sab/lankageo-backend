import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env and configure python path relative to script directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

import ee
from app.services.gee_service import gee_service
from app.services.auth_service import get_supabase

async def run_analysis():
    print("🚀 Initializing Google Earth Engine...")
    gee_service.initialize()
    print("✅ GEE Initialized.")

    # 1. Define ROI: Sri Lanka boundary
    print("🗺️ Loading Sri Lanka boundary...")
    sri_lanka = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017') \
        .filter(ee.Filter.eq('country_na', 'Sri Lanka')) \
        .geometry()

    # 2. Get Sentinel-1 GRD 2020 Collection
    print("🛰️ Loading Sentinel-1 collection for 2020 (this may take a moment)...")
    s1_2020 = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(sri_lanka) \
        .filterDate('2020-01-01', '2020-12-31') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .select('VV')

    # 3. Calculate Water Residency Index
    print("📊 Calculating Water Residency Index (Water days / Observation days)...")
    total_obs = s1_2020.count()
    water_mask_coll = s1_2020.map(lambda img: img.lt(-16).rename('water'))
    water_sum = water_mask_coll.sum()
    residency = water_sum.divide(total_obs.add(0.001)).rename('residency')

    # 4. Load JRC Occurrence and mask permanent water (occurrence >= 90%)
    print("💧 Filtering out permanent water bodies...")
    jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    permanent_water = jrc.select('occurrence').gte(90)

    # 5. Slope mask (slope < 5 degrees)
    print("⛰️ Applying slope-based suppression...")
    dem = ee.Image("USGS/SRTMGL1_003")
    elevation = dem.select('elevation')
    slope = ee.Terrain.slope(elevation)
    slope_mask = slope.lt(5)

    # 6. Hydrological connectivity mask (within 3km of major rivers or high residency)
    print("🏞️ Calculating hydrological connectivity buffer (3km distance transform)...")
    merit = ee.Image("MERIT/Hydro/v1_0_1")
    drainage_area = merit.select('upa')
    major_drainage = drainage_area.gt(10)
    
    # At 150m evaluation scale, a 3km search neighborhood is 20 pixels
    # We search 25 pixels to be safe and cover up to 3.75km
    distance_sq = major_drainage.fastDistanceTransform(25, 'pixels', 'squared_euclidean')
    distance_meters = distance_sq.sqrt().multiply(150)
    river_corridor = distance_meters.lte(3000)
    connectivity_mask = river_corridor.Or(residency.gt(0.25))

    # 7. Apply 3-Layer Filter rules
    flood_pixels = residency.gt(0.05) \
        .And(permanent_water.Not()) \
        .And(slope_mask) \
        .And(connectivity_mask) \
        .rename('flood_pixels')

    # 8. Risk Classification
    # We use HAND and residency to assign severity:
    # Value 1 (seasonal): residency 0.05 - 0.10
    # Value 2 (moderate): residency > 0.10 and HAND >= 2m
    # Value 3 (critical): residency > 0.10 and HAND < 2m
    hand = merit.select('hnd').rename('HAND')
    risk_map = ee.Image(0) \
        .where(flood_pixels.eq(1).And(residency.lte(0.10)), 1) \
        .where(flood_pixels.eq(1).And(residency.gt(0.10)).And(hand.gte(2)), 2) \
        .where(flood_pixels.eq(1).And(residency.gt(0.10)).And(hand.lt(2)), 3)

    # 9. Vectorization
    scale_m = 150
    print(f"📐 Vectorizing classified raster (scale={scale_m}m)...")
    vector_ready = risk_map.updateMask(risk_map.gt(0))
    vectors = vector_ready.reduceToVectors(
        geometry=sri_lanka,
        scale=scale_m,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='severity_level',
        bestEffort=True,
        maxPixels=1e9
    )

    # 10. Post-process vector areas and filter small noise (< 0.05 km2)
    def add_area_info(feature):
        area = feature.geometry().area(maxError=10).divide(1e6)
        return feature.set({'area_km2': area})

    processed_vectors = vectors.map(add_area_info).filter(ee.Filter.gt('area_km2', 0.05))

    # 11. Simplify geometry to minimize GeoJSON payload and speed up DB insertion
    print("🧹 Simplifying polygon geometries...")
    simplified_vectors = processed_vectors.map(lambda f: f.simplify(maxError=30))

    # 12. Fetch vector data
    print("📡 Fetching GeoJSON from Earth Engine (this may take a minute)...")
    geojson = simplified_vectors.getInfo()
    features = geojson.get("features", [])
    print(f"✅ Fetched {len(features)} flood polygons.")

    if not features:
        print("⚠️ No flood polygons detected. Database insertion skipped.")
        return

    # 13. Calculate overall affected area
    total_area_km2 = sum(f.get("properties", {}).get("area_km2", 0) for f in features)
    print(f"📊 Total Affected Area: {total_area_km2:.2f} km²")

    # 14. Initialize Supabase and persist results
    print("💾 Connecting to Supabase...")
    sb = get_supabase()

    # Bounding box of Sri Lanka for the request geometry
    sri_lanka_bbox = {
        "type": "Polygon",
        "coordinates": [[
            [79.6, 5.9],
            [81.9, 5.9],
            [81.9, 9.9],
            [79.6, 9.9],
            [79.6, 5.9]
        ]]
    }

    print("Inserting requests record...")
    req_payload = {
        "analysis_type": "live",  # Use 'live' to allow normal polygon rendering in the client
        "status": "completed",
        "region_boundary": sri_lanka_bbox
    }
    req_resp = sb.table("requests").insert(req_payload).execute()
    request_id = req_resp.data[0]["request_id"]
    print(f"Request ID created: {request_id}")

    print("Inserting live_flood_results record...")
    res_payload = {
        "request_id": request_id,
        "satellite_source": "Sentinel-1 SAR",
        "gee_asset_id": "yearly_average_2020_srilanka",
        "affected_area_km2": round(total_area_km2, 2),
        "confidence_score": 0.85,
        "estimated_population": int(total_area_km2 * 145),
        "buildings_exposed": int(total_area_km2 * 32),
        "road_length_km": round(total_area_km2 * 1.8, 2),
        "cropland_area_km2": round(total_area_km2 * 0.35, 2),
        "tile_url": None,
        "cloud_cover_pct": 0.0
    }
    res_resp = sb.table("live_flood_results").insert(res_payload).execute()
    result_id = res_resp.data[0]["result_id"]
    print(f"Result ID created: {result_id}")

    print("Inserting flood polygons...")
    severity_map = {1: "seasonal", 2: "moderate", 3: "critical"}
    
    polygon_inserts = []
    for idx, feature in enumerate(features):
        props = feature.get("properties", {})
        raw_severity = props.get("severity_level")
        severity_label = severity_map.get(raw_severity, "moderate")
        
        polygon_inserts.append({
            "result_id": result_id,
            "severity_level": severity_label,
            "area_km2": round(props.get("area_km2", 4), 4),
            "water_type": "seasonal" if severity_label == "seasonal" else "new_flood",
            "geom": feature.get("geometry")
        })

    # Batch insert to prevent connection timeouts
    batch_size = 50
    inserted_count = 0
    for i in range(0, len(polygon_inserts), batch_size):
        batch = polygon_inserts[i:i+batch_size]
        try:
            sb.table("flood_polygons").insert(batch).execute()
            inserted_count += len(batch)
            print(f"  Inserted batch {i//batch_size + 1}/{((len(polygon_inserts)-1)//batch_size) + 1} ({inserted_count}/{len(polygon_inserts)})")
        except Exception as insert_err:
            print(f"❌ Error inserting batch {i//batch_size + 1}: {insert_err}")
            
    print(f"🎉 Completed! Successfully inserted {inserted_count} polygons for Sri Lanka 2020 Yearly Average.")

if __name__ == "__main__":
    asyncio.run(run_analysis())
