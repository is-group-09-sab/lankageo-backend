import ee
from app.core.config import settings
import logging
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

class GEEService:
    """
    Service for interacting with Google Earth Engine (GEE).
    Handles authentication and provides high-level data processing methods.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GEEService, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """
        Initializes the GEE SDK with the best available credentials.
        Order of priority:
        1. Service Account (Email + Private Key)
        2. OAuth2 User Refresh Token
        3. Application Default Credentials (ADC)
        """
        if self._initialized:
            return

        try:
            # 1. Service Account Authentication
            if settings.GEE_SERVICE_ACCOUNT and settings.GEE_PRIVATE_KEY and "placeholder" not in settings.GEE_SERVICE_ACCOUNT:
                try:
                    logger.info("Initializing GEE with Service Account...")
                    private_key = settings.GEE_PRIVATE_KEY.replace('\\n', '\n')
                    credentials = ee.ServiceAccountCredentials(
                        settings.GEE_SERVICE_ACCOUNT,
                        key_data=private_key
                    )
                    ee.Initialize(credentials, project=settings.GEE_PROJECT)
                    logger.info("GEE initialized with Service Account.")
                    self._initialized = True
                    return
                except Exception as e:
                    logger.warning(f"Service Account auth failed: {e}")

            # 2. OAuth2 Refresh Token Authentication
            if settings.GEE_REFRESH_TOKEN and settings.GEE_CLIENT_ID:
                try:
                    logger.info("Initializing GEE with OAuth2 Refresh Token...")
                    credentials = Credentials(
                        token=None,
                        refresh_token=settings.GEE_REFRESH_TOKEN,
                        client_id=settings.GEE_CLIENT_ID,
                        client_secret=settings.GEE_CLIENT_SECRET,
                        token_uri="https://oauth2.googleapis.com/token"
                    )
                    ee.Initialize(credentials, project=settings.GEE_PROJECT)
                    logger.info("GEE initialized with User Refresh Token.")
                    self._initialized = True
                    return
                except Exception as e:
                    logger.warning(f"Refresh Token auth failed: {e}")

            # 3. Fallback to Application Default Credentials (ADC)
            logger.info("Initializing GEE with Application Default Credentials (ADC)...")
            ee.Initialize(project=settings.GEE_PROJECT)
            logger.info("GEE initialized with ADC.")
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize GEE: {e}")
            raise RuntimeError(f"GEE Initialization failed: {e}")

    def test_connection(self):
        """
        Verifies the GEE connection by querying the SRTM elevation dataset.
        """
        if not self._initialized:
            self.initialize()
        
        try:
            image = ee.Image("USGS/SRTMGL1_003")
            info = image.getInfo()
            return {"status": "success", "asset_id": info.get("id")}
        except Exception as e:
            logger.error(f"GEE test connection failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_sentinel1_collection(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str):
        """
        Filters the Sentinel-1 ImageCollection based on location and date.
        
        Args:
            lat, lon: Coordinates for the center of the ROI.
            buffer_meters: Radius to create a geometry.
            start_date, end_date: Time range for filtering.
        """
        if not self._initialized:
            self.initialize()

        # Create the ROI geometry (GEE uses [longitude, latitude])
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_meters).bounds()

        # Filter the S1 Ground Range Detected (GRD) collection
        collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                      .filterBounds(roi)
                      .filterDate(start_date, end_date)
                      # Filter for IW mode (Standard for land)
                      .filter(ee.Filter.eq('instrumentMode', 'IW'))
                      # Use a flexible filter for polarization (S vs Z spelling)
                      .filter(ee.Filter.Or(
                          ee.Filter.listContains('transmitterReceiverPolarization', 'VV'),
                          ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')
                      )))
        
        return collection, roi

    def get_latest_s1_image(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str):
        """
        Retrieves the most recent Sentinel-1 image mosaic for the given parameters.
        """
        collection, roi = self.get_sentinel1_collection(lat, lon, buffer_meters, start_date, end_date)
        
        # Check if the collection is empty before proceeding
        count = collection.size().getInfo()
        if count == 0:
            return None
            
        # Sort by system:time_start (date) in descending order and take the first one
        latest_image = collection.sort('system:time_start', False).first()
        
        if not latest_image:
            return None
        
        # Clip the image to our exact ROI so we don't process unnecessary data
        return latest_image.clip(roi)

# Singleton instance
gee_service = GEEService()
