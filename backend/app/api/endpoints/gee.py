from fastapi import APIRouter, HTTPException
from app.services.gee_service import gee_service

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
