from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.services.gee_service import gee_service
from app.services.auth_service import get_supabase
from app.schemas.flood import FloodAnalysisRequest
import json

class FloodService:
    @property
    def supabase(self):
        return get_supabase()

    async def get_cached_result(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Check for existing records within ±0.01° of the requested coordinates.
        SAR Results: Valid for 6 hours.
        Optical Results: Valid for 3 hours.
        """
        # Define bounds for spatial search (±0.01°)
        lat_min, lat_max = lat - 0.01, lat + 0.01
        lng_min, lng_max = lng - 0.01, lng + 0.01

        try:
            # Query recent results within spatial bounds
            # Note: In a production PostGIS environment, we'd use ST_DWithin
            # Here we use simple range filters as a proxy for the caching logic
            response = self.supabase.table("Live_Flood_Result") \
                .select("*") \
                .gte("lat", lat_min) \
                .lte("lat", lat_max) \
                .gte("lng", lng_min) \
                .lte("lng", lng_max) \
                .order("analysis_timestamp", desc=True) \
                .limit(1) \
                .execute()

            if not response.data:
                return None

            latest_result = response.data[0]
            timestamp = datetime.fromisoformat(latest_result["analysis_timestamp"].replace('Z', '+00:00'))
            source = latest_result["satellite_source"]

            # Validation timeframe logic
            valid_duration = timedelta(hours=6) if "SAR" in source else timedelta(hours=3)
            
            if datetime.now(timestamp.tzinfo) - timestamp < valid_duration:
                # Need to fetch associated polygons as well
                polygon_response = self.supabase.table("Flood_Polygon") \
                    .select("geojson") \
                    .eq("result_id", latest_result["id"]) \
                    .execute()
                
                # Reconstruct GeoJSON FeatureCollection
                features = [p["geojson"] for p in polygon_response.data]
                latest_result["geojson"] = {
                    "type": "FeatureCollection",
                    "features": features
                }
                latest_result["cache_hit"] = True
                return latest_result

        except Exception as e:
            print(f"Cache check error: {e}")
            
        return None

    async def process_flood_analysis(self, request: FloodAnalysisRequest) -> Dict[str, Any]:
        # 1. Check Cache
        cached = await self.get_cached_result(request.lat, request.lng)
        if cached and not request.override_date:
            return cached

        # 2. Run GEE Analysis
        analysis_data = gee_service.run_live_analysis(
            request.lat, request.lng, request.radius_km, request.override_date
        )

        # 3. Prepare Persistence Data
        analysis_timestamp = datetime.now().isoformat()
        
        # Save to Live_Flood_Result
        result_payload = {
            "lat": request.lat,
            "lng": request.lng,
            "radius_km": request.radius_km,
            "tile_url": analysis_data["tile_url"],
            "affected_area_km2": analysis_data["affected_area_km2"],
            "confidence_score": analysis_data["confidence_score"],
            "satellite_source": analysis_data["satellite_source"],
            "cloud_cover_pct": analysis_data["cloud_cover_pct"],
            "risk_level": analysis_data["risk_level"],
            "analysis_timestamp": analysis_timestamp,
            "gee_asset_id": analysis_data["gee_asset_id"],
            "estimated_population": analysis_data["estimated_population"],
            "buildings_exposed": analysis_data["buildings_exposed"],
            "road_length_km": analysis_data["road_length_km"],
            "cropland_area_km2": analysis_data["cropland_area_km2"]
        }

        try:
            # Insert Result
            res_response = self.supabase.table("Live_Flood_Result").insert(result_payload).execute()
            result_id = res_response.data[0]["id"]

            # Insert Polygons
            # For each feature in GeoJSON, insert into Flood_Polygon
            geojson = analysis_data["geojson"]
            features = geojson.get("features", [])
            
            polygon_inserts = []
            for feature in features:
                polygon_inserts.append({
                    "result_id": result_id,
                    "geojson": feature,
                    "severity": feature.get("properties", {}).get("severity", "Moderate")
                })
            
            if polygon_inserts:
                self.supabase.table("Flood_Polygon").insert(polygon_inserts).execute()

        except Exception as e:
            print(f"Persistence error: {e}")
            # Even if persistence fails, we return the data to the user

        return {
            **analysis_data,
            "analysis_timestamp": analysis_timestamp,
            "cache_hit": False
        }

flood_service = FloodService()
