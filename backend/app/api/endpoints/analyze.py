from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.flood import FloodAnalysisRequest, FloodAnalysisResponse
from app.services.flood_service import flood_service
from app.services.auth_service import get_current_user
import asyncio

router = APIRouter()

@router.post("/live", response_model=FloodAnalysisResponse)
async def analyze_live_flood(
    request: FloodAnalysisRequest,
    current_user: any = Depends(get_current_user)
):
    """
    Perform live flood analysis for a specific ROI in Sri Lanka.
    Orchestrates GEE processing, caching, and persistence.
    """
    try:
        # Implement 75-second timeout for GEE processing
        return await asyncio.wait_for(
            flood_service.process_flood_analysis(request),
            timeout=75.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Earth Engine processing timed out. Please try again with a smaller radius."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )
