from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from datetime import datetime

class FloodAnalysisRequest(BaseModel):
    lat: float = Field(..., ge=5.72, le=9.85, description="Latitude of the center of the ROI (Sri Lanka bounds)")
    lng: float = Field(..., ge=79.52, le=81.88, description="Longitude of the center of the ROI (Sri Lanka bounds)")
    radius_km: int = Field(..., ge=1, le=50, description="Radius for the analysis buffer (1km - 50km)")
    override_date: Optional[str] = Field(None, description="ISO date string to simulate historical analysis (YYYY-MM-DD)")

class FloodAnalysisResponse(BaseModel):
    tile_url: str
    geojson: Any
    affected_area_km2: float
    confidence_score: float
    satellite_source: str
    cloud_cover_pct: float
    risk_level: str
    analysis_timestamp: datetime
    gee_asset_id: Optional[str]
    estimated_population: int
    buildings_exposed: int
    road_length_km: float
    cropland_area_km2: float
    cache_hit: bool
