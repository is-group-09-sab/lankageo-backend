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

# Singleton instance
gee_service = GEEService()
