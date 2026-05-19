import ee
from app.core.config import settings
from typing import Dict, Any
import datetime
import json

class GEEService:
    def __init__(self):
        self.initialized = False

    def _initialize(self):
        if not self.initialized:
            if settings.GEE_SERVICE_ACCOUNT and settings.GEE_PRIVATE_KEY:
                # Assuming private key is a JSON string or a path
                # For this implementation, we assume it's the JSON key content
                try:
                    credentials = ee.ServiceAccountCredentials(
                        settings.GEE_SERVICE_ACCOUNT, 
                        settings.GEE_PRIVATE_KEY
                    )
                    ee.Initialize(credentials)
                    self.initialized = True
                except Exception as e:
                    print(f"Error initializing GEE: {e}")
            else:
                # Fallback to default initialization if possible
                try:
                    ee.Initialize()
                    self.initialized = True
                except:
                    print("GEE credentials not configured.")

    def run_live_analysis(self, lat: float, lng: float, radius_km: int) -> Dict[str, Any]:
        self._initialize()
        
        # 1. Define ROI
        point = ee.Geometry.Point([lng, lat])
        roi = point.buffer(radius_km * 1000)
        
        # 2. Check Cloud Cover (Sentinel-2)
        s2_col = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
                  .filterBounds(roi)
                  .filterDate(
                      datetime.datetime.now() - datetime.timedelta(days=5),
                      datetime.datetime.now()
                  )
                  .sort('CLOUDY_PIXEL_PERCENTAGE'))
        
        latest_s2 = s2_col.first()
        
        # Compute cloud cover over ROI
        # Using QA60 band for cloud check as per spec
        cloud_pct = 100 # Default if no image
        source = "Sentinel-2 Optical"
        
        if latest_s2:
            # Simplification: Use the image metadata if it covers the ROI
            # In a real scenario, we'd clip and compute the percentage of QA60 cloud pixels
            cloud_pct = latest_s2.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        
        # 3. Satellite Source Selection Logic
        if cloud_pct > 20:
            source = "Sentinel-1 SAR"
            # SAR Processing (Simplified)
            # In reality, this would involve Sentinel-1 GRD collection, filtering, 
            # and flood detection algorithms like thresholding
            analysis_img = ee.Image(0) # Placeholder for SAR result
        else:
            source = "Sentinel-2 Optical"
            # Optical Processing (Simplified)
            # Using MNDWI or similar for water detection
            analysis_img = ee.Image(0) # Placeholder for Optical result

        # 4. Impact Layer Lookups (Placeholders)
        # In a real implementation, these would be intersections with:
        # - WorldPop (Population)
        # - OSM (Roads/Buildings)
        # - ESA WorldCover (Cropland)
        
        impact_metrics = {
            "affected_area_km2": 12.5,  # Mock
            "estimated_population": 450, # Mock
            "buildings_exposed": 85,     # Mock
            "road_length_km": 3.2,       # Mock
            "cropland_area_km2": 5.4,    # Mock
            "confidence_score": 0.85,    # Mock
            "risk_level": "Moderate",    # Mock
            "gee_asset_id": f"projects/lankageo/assets/flood_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }

        # 5. Generate Tile URL and GeoJSON
        # Dummy tile URL for example
        map_id = analysis_img.getMapId({'palette': ['white', 'blue'], 'min': 0, 'max': 1})
        tile_url = map_id['tile_fetcher'].url_format

        # Dummy GeoJSON (Simplified)
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[lng, lat], [lng+0.01, lat], [lng+0.01, lat+0.01], [lng, lat]]]
                    },
                    "properties": {"severity": "Moderate"}
                }
            ]
        }

        return {
            "tile_url": tile_url,
            "geojson": geojson,
            "satellite_source": source,
            "cloud_cover_pct": cloud_pct,
            **impact_metrics
        }

gee_service = GEEService()
