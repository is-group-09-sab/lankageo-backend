from pydantic import BaseModel
from typing import List, Literal

class GaugeReading(BaseModel):
    station_name: str
    current_level_m: float
    normal_level_m: float
    status: Literal["normal", "elevated", "critical"]

class GaugeLiveResponse(BaseModel):
    gauges: List[GaugeReading]
