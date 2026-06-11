from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/maps-config")
async def get_maps_config():
    """
    Returns the Google Maps API keys required by the frontend.
    Only the keys intended for client-side use are exposed.
    """
    return {
        "google_maps_js_api_key": settings.GOOGLE_MAPS_JS_API_KEY,
        "google_places_api_key": settings.GOOGLE_PLACES_API_KEY,
        # Note: Static API key is usually used server-side, but included if needed
        "google_maps_static_api_key": settings.GOOGLE_MAPS_STATIC_API_KEY
    }
