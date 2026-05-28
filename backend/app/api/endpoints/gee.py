from fastapi import APIRouter, HTTPException
from app.services.gee_service import gee_service
from app.schemas.gee import Sentinel1Request, Sentinel2Request
import logging
import ee

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
async def get_gee_status():
    """
    Check the connection status to Google Earth Engine.
    """
    result = gee_service.test_connection()
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@router.post("/sentinel1")
async def get_sentinel1_metadata(request: Sentinel1Request):
    """
    Finds the latest Sentinel-1 radar image and optionally applies preprocessing.
    """
    try:
        # 1. Search for the image
        image = gee_service.get_latest_s1_image(
            request.roi.lat,
            request.roi.lon,
            request.roi.buffer_meters,
            request.start_date,
            request.end_date
        )
        
        if not image:
            return {
                "status": "not_found", 
                "message": "No Sentinel-1 radar images found."
            }
            
        response = {
            "status": "success",
            "image_id": image.get('system:index').getInfo(),
            "date": image.get('system:time_start').getInfo(),
            "orbit": image.get('orbitProperties_pass').getInfo(),
        }

        # 2. Apply Preprocessing if requested (LG-104)
        if request.preprocess:
            processed_image = gee_service.preprocess_sentinel1(image)
            
            # Get the mean dB value for the ROI to verify processing
            stats = processed_image.select('VV_db').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=image.geometry(),
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            response["vv_db_mean"] = stats.get('VV_db')
            response["processed"] = True

        return response
    except Exception as e:
        logger.error(f"Error in Sentinel-1 processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sentinel2")
async def get_sentinel2_metadata(request: Sentinel2Request):
    """
    Finds the clearest and most recent Sentinel-2 optical image.
    """
    try:
        image = gee_service.get_latest_s2_image(
            request.roi.lat,
            request.roi.lon,
            request.roi.buffer_meters,
            request.start_date,
            request.end_date
        )
        
        if not image:
            return {
                "status": "not_found", 
                "message": "No clear Sentinel-2 images found for this criteria."
            }
            
        return {
            "status": "success",
            "image_id": image.get('system:index').getInfo(),
            "date": image.get('system:time_start').getInfo(),
            "cloud_cover": image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        }
    except Exception as e:
        logger.error(f"Error in Sentinel-2 search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
