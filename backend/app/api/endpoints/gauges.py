from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.gauge import GaugeReading
from app.services.gauge_service import gauge_service

router = APIRouter()

@router.get("/live", response_model=List[GaugeReading])
async def get_live_gauges():
    """
    Retrieves live water level readings for key Kelani River gauge stations.
    Data is cached for 30 minutes to reduce external API load.
    """
    try:
        readings = await gauge_service.get_live_readings()
        return readings
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
