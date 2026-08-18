from fastapi import APIRouter, HTTPException, Depends, status
from typing import Any, List, Dict
from app.schemas.flood import FloodAnalysisRequest, FloodAnalysisResponse
from app.schemas.analyze import TrendAnalysisRequest, TrendAnalysisResponse
from app.services.flood_service import flood_service
from app.services.gee_service import gee_service
from app.services.report_service import report_service
from app.services.auth_service import get_supabase, get_current_user_optional, get_supabase_optional
from typing import Any, List, Dict, Optional
from supabase import Client
import asyncio
import time
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/live", response_model=List[Dict[str, Any]])
async def get_live_polygons():
    """
    Fetch all previously stored live flood polygons from the database.
    This is a public endpoint used by the dashboard to show current flood status.
    """
    try:
        return await flood_service.get_all_live_polygons()
    except Exception as e:
        logger.error(f"Error fetching live polygons: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching polygons: {str(e)}"
        )

@router.get("/polygons/year/{year}", response_model=List[Dict[str, Any]])
async def get_polygons_by_year(year: int):
    """
    Fetch all stored flood polygons for a specific year from the database.
    Used by the historical risk view to display year-specific polygons.
    """
    try:
        return await flood_service.get_polygons_by_year(year)
    except Exception as e:
        logger.error(f"Error fetching polygons for year {year}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching polygons for year {year}: {str(e)}"
        )

@router.post("/live", response_model=FloodAnalysisResponse)
async def analyze_live_flood(
    request: FloodAnalysisRequest,
    current_user: Any = Depends(get_current_user_optional)
):
    """
    Perform live flood analysis for a specific ROI in Sri Lanka.
    Orchestrates GEE processing, caching, and persistence.
    """
    try:
        # Increased timeout to 180 seconds for GEE processing
        return await asyncio.wait_for(
            flood_service.process_flood_analysis(request),
            timeout=180.0
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
    db: Optional[Client] = Depends(get_supabase_optional),
    current_user: Any = Depends(get_current_user_optional)
):
    """
    Performs historical trend analysis for a given location and radius.
    Results are persisted in the database if available.
    """
    start_time = time.time()
    
    try:
        # 1. Execute Historical Analysis via GEE Service
        # Enforcing 180-second timeout via asyncio.wait_for to ensure the endpoint 
        # has enough time to complete 5 years of GEE analysis.
        analysis_result = await asyncio.wait_for(
            gee_service.run_historical_analysis(
                lat=request_data.lat,
                lng=request_data.lng,
                radius_km=request_data.radius_km,
                years=request_data.years
            ),
            timeout=180.0
        )
        
        # 2. Persist to Database (Supabase) if DB client is available
        if db:
            try:
                request_record = {
                    "lat": request_data.lat,
                    "lng": request_data.lng,
                    "radius_km": request_data.radius_km,
                    "request_type": "historical_trend",
                    "status": "completed",
                    "user_id": current_user.id if current_user else None
                }
                
                request_response = db.table("requests").insert(request_record).execute()
                
                if request_response.data:
                    request_id = request_response.data[0]["id"]
                    profile_record = {
                        "request_id": request_id,
                        "avg_flood_probability": analysis_result.avg_flood_probability,
                        "peak_year": analysis_result.peak_year,
                        "min_year": analysis_result.min_year,
                        "data_payload": analysis_result.model_dump()
                    }
                    db.table("historical_risk_profiles").insert(profile_record).execute()
            except Exception as db_err:
                logger.warning(f"Failed to persist historical trend result to database: {db_err}")
            
        return analysis_result

    except asyncio.TimeoutError:
        logger.error(f"Trend analysis timed out for {request_data.lat}, {request_data.lng}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Historical trend analysis timed out. Please try with a smaller radius or fewer years."
        )
    except Exception as e:
        logger.error(f"Error during trend analysis: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during analysis: {str(e)}"
        )


@router.get("/result/{request_id}", response_model=Dict[str, Any])
async def get_analysis_result(
    request_id: str,
    db: Client = Depends(get_supabase),
    current_user: Any = Depends(get_current_user_optional)
):
    """
    Retrieve previously stored live flood or historical analysis result by request ID.
    """
    try:
        result = await report_service.get_report_data(request_id)
        if not result:
            # Check historical as well
            result = await report_service.get_historical_risk_profile(request_id)
            
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis result with ID {request_id} not found."
            )
        return result
    except Exception as e:
        logger.error(f"Error fetching analysis result {request_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the result: {str(e)}"
        )
