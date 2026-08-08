from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class TrendAnalysisRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the center point")
    lng: float = Field(..., description="Longitude of the center point")
    radius_km: float = Field(default=10.0, description="Analysis radius in kilometers")
    years: int = Field(default=5, ge=1, le=20, description="Number of years for historical analysis")

class YearData(BaseModel):
    year: int
    value: float
    details: Optional[Dict[str, Any]] = None

class ZoneSeverityCount(BaseModel):
    severity: str
    count: int

class TrendAnalysisResponse(BaseModel):
    years_data: List[YearData] = Field(..., description="Historical data trend over the specified years")
    composite_tile_url: str = Field(..., description="URL for the composite risk tile layer")
    avg_flood_probability: float = Field(..., description="Average flood probability over the period (%)")
    peak_year: int = Field(..., description="Year with the highest recorded flood extent")
    min_year: int = Field(..., description="Year with the lowest recorded flood extent")
    trend_heatmap_url: str = Field(..., description="URL for the historical trend heatmap")
    zone_count_by_severity: List[ZoneSeverityCount] = Field(..., description="Count of zones categorized by risk severity")

class AnalysisRequestRecord(BaseModel):
    """Schema for persisting the parent Request record"""
    id: Optional[str] = None
    lat: float
    lng: float
    radius_km: float
    request_type: str = "historical_trend"
    status: str = "completed"

class HistoricalRiskProfileRecord(BaseModel):
    """Schema for persisting the Historical_Risk_Profile record"""
    id: Optional[str] = None
    request_id: str
    avg_flood_probability: float
    peak_year: int
    min_year: int
    data_payload: Dict[str, Any]
