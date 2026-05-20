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
