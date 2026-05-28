from fastapi import APIRouter, HTTPException, Depends, status
from typing import Any
from app.schemas.flood import FloodAnalysisRequest, FloodAnalysisResponse
from app.schemas.analyze import TrendAnalysisRequest, TrendAnalysisResponse
from app.services.flood_service import flood_service
from app.services.gee_service import gee_service
from app.services.auth_service import get_supabase, get_current_user
from supabase import Client
import asyncio
import time
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/live", response_model=FloodAnalysisResponse)
async def analyze_live_flood(
    request: FloodAnalysisRequest,
    current_user: Any = Depends(get_current_user)
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
        logger.error(f"Error during live flood analysis: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )

@router.post("/trend", response_model=TrendAnalysisResponse)
async def analyze_trend(
    request_data: TrendAnalysisRequest,
    db: Client = Depends(get_supabase),
    current_user: Any = Depends(get_current_user)
):
    """
    Performs historical trend analysis for a given location and radius.
    Results are persisted in the database.
    """
    start_time = time.time()
    
    try:
        # 1. Execute Historical Analysis via GEE Service
        analysis_result = await gee_service.run_historical_analysis(
            lat=request_data.lat,
            lng=request_data.lng,
            radius_km=request_data.radius_km,
            years=request_data.years
        )
        
        # 2. Persist to Database (Supabase)
        # Create parent Request record
        request_record = {
            "lat": request_data.lat,
            "lng": request_data.lng,
            "radius_km": request_data.radius_km,
            "request_type": "historical_trend",
            "status": "completed",
            "user_id": current_user.id
        }
        
        request_response = db.table("requests").insert(request_record).execute()
        
        if not request_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create request record in database"
            )
            
        request_id = request_response.data[0]["id"]
        
        # Create child Historical_Risk_Profile record
        profile_record = {
            "request_id": request_id,
            "avg_ffi": analysis_result.avg_ffi,
            "peak_year": analysis_result.peak_year,
            "min_year": analysis_result.min_year,
            "data_payload": analysis_result.model_dump()
        }
        
        profile_response = db.table("historical_risk_profiles").insert(profile_record).execute()
        
        if not profile_response.data:
            logger.error(f"Failed to persist risk profile for request {request_id}")
            # We don't necessarily want to fail the whole request if only the profile persistence fails,
            # but for this task, we'll treat it as a failure.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist risk profile in database"
            )
            
        # 3. Performance Benchmarking
        duration = time.time() - start_time
        logger.info(f"Trend analysis completed in {duration:.2f} seconds")
        
        if duration > 15.0:
            logger.warning(f"Trend analysis exceeded 15s target: {duration:.2f}s")
            
        return analysis_result

    except Exception as e:
        logger.error(f"Error during trend analysis: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )
