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
    Finds the latest Sentinel-1 radar image and optionally applies preprocessing or change detection.
    """
    try:
        # 1. Search for the primary (post-event) image
        image = gee_service.get_latest_s1_image(
            request.roi.lat,
            request.roi.lon,
            request.roi.buffer_meters,
            request.start_date,
            request.end_date,
            request.orbit_pass
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
            "relative_orbit": image.get('relativeOrbitNumber_start').getInfo(),
        }

        # 2. Apply Preprocessing if requested (LG-104)
        if request.preprocess and not request.compare_with_baseline:
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

        # 3. Apply Change Detection if requested (LG-105)
        if request.compare_with_baseline:
            baseline_image = gee_service.get_baseline_s1_image(
                image, 
                days_back=request.baseline_days
            )
            
            if not baseline_image:
                response["baseline_status"] = "not_found"
                response["message"] = "Post-image found, but no matching baseline image exists for this orbit."
            else:
                # Run the ratio calculation
                change_image = gee_service.compute_change_ratio(
                    baseline_image, 
                    image, 
                    use_otsu=request.use_otsu
                )
                
                # Calculate statistics
                stats = change_image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=image.geometry(),
                    scale=30,
                    maxPixels=1e9
                ).getInfo()
                
                # Extract the threshold used
                applied_threshold = change_image.get('applied_threshold').getInfo()
                
                response["baseline_image_id"] = baseline_image.get('system:index').getInfo()
                response["baseline_date"] = baseline_image.get('system:time_start').getInfo()
                response["change_ratio_mean"] = stats.get('change_ratio')
                response["otsu_threshold"] = applied_threshold
                response["flood_detected"] = stats.get('flood_mask') > 0.05 # Simple heuristic: if >5% of area is flooded
                response["processed"] = True
                response["method"] = "change_detection_ratio_otsu" if request.use_otsu else "change_detection_ratio_static"

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
            
        response = {
            "status": "success",
            "image_id": image.get('system:index').getInfo(),
            "date": image.get('system:time_start').getInfo(),
            "cloud_cover": image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
        }

        # 2. Apply NDWI if requested (LG-107)
        if request.calculate_ndwi:
            ndwi_image = gee_service.compute_ndwi(image)
            
            # Get the mean NDWI value and water percentage for the ROI
            stats = ndwi_image.select(['NDWI', 'ndwi_water_mask']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=image.geometry(),
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            response["ndwi_mean"] = stats.get('NDWI')
            response["water_percentage"] = (stats.get('ndwi_water_mask') or 0) * 100
            response["processed"] = True
            response["method"] = "ndwi_optical"

        return response
    except Exception as e:
        logger.error(f"Error in Sentinel-2 search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feature-stack")
async def get_feature_stack(request: FeatureStackRequest):
    """
    Generates a 6-band multi-sensor feature stack for the given ROI.
    Bands: VV_db, VH_VV_ratio, NDWI, NDVI, Elevation, HAND
    """
    try:
        stack, metadata = gee_service.create_rf_feature_stack(
            request.roi.lat,
            request.roi.lon,
            request.roi.buffer_meters,
            request.s1_start_date,
            request.s1_end_date,
            request.s2_start_date,
            request.s2_end_date,
            request.orbit_pass
        )
        
        # Calculate mean values for the ROI to verify the stack is valid
        stats = stack.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=stack.geometry(),
            scale=30,
            maxPixels=1e9
        ).getInfo()
        
        return {
            "status": "success",
            "metadata": metadata,
            "feature_means": stats,
            "bands": stack.bandNames().getInfo()
        }
    except Exception as e:
        logger.error(f"Error generating feature stack: {e}")
        raise HTTPException(status_code=500, detail=str(e))
