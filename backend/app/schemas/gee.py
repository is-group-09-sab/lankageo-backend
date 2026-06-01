from pydantic import BaseModel, Field
from typing import Optional

class PointROI(BaseModel):
    """
    Defines a circular Region of Interest (ROI) using a center point and a buffer.
    """
    lat: float = Field(..., description="Latitude of the center point")
    lon: float = Field(..., description="Longitude of the center point")
    buffer_meters: float = Field(default=1000, description="Buffer radius in meters around the point")

class Sentinel1Request(BaseModel):
    """
    The data required to search for Sentinel-1 radar imagery.
    """
    roi: PointROI
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    orbit_pass: Optional[str] = Field(default="DESCENDING", description="Orbit direction: ASCENDING or DESCENDING")
    preprocess: bool = Field(default=False, description="Whether to apply speckle filtering and dB conversion")
    compare_with_baseline: bool = Field(default=False, description="Whether to perform change detection against a baseline image")
    baseline_days: int = Field(default=30, description="How many days back to look for a baseline image")

class Sentinel2Request(BaseModel):
    """
    The data required to search for Sentinel-2 optical imagery.
    """
    roi: PointROI
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    cloud_percentage: Optional[int] = Field(default=20, description="Maximum allowed cloudy pixel percentage")
