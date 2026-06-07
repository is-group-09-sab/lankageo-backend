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
    use_otsu: bool = Field(default=False, description="Whether to use Otsu thresholding for change detection")

class Sentinel2Request(BaseModel):
    """
    The data required to search for Sentinel-2 optical imagery.
    """
    roi: PointROI
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    cloud_percentage: Optional[int] = Field(default=20, description="Maximum allowed cloudy pixel percentage")
    calculate_ndwi: bool = Field(default=False, description="Whether to calculate the Normalized Difference Water Index (NDWI)")

class FeatureStackRequest(BaseModel):
    """
    Request for multi-sensor feature stack.
    """
    roi: PointROI
    s1_start_date: str = Field(..., description="S1 start date")
    s1_end_date: str = Field(..., description="S1 end date")
    s2_start_date: str = Field(..., description="S2 start date")
    s2_end_date: str = Field(..., description="S2 end date")
    orbit_pass: Optional[str] = Field(default="DESCENDING")

class EnsembleRequest(BaseModel):
    """
    Request for 3-signal weighted ensemble flood detection.
    """
    roi: PointROI
    pre_start_date: str = Field(..., description="Baseline start date")
    pre_end_date: str = Field(..., description="Baseline end date")
    post_start_date: str = Field(..., description="Post-event start date")
    post_end_date: str = Field(..., description="Post-event end date")
    weights: Optional[dict] = Field(default={"rf": 0.5, "change": 0.3, "otsu": 0.2})

