import ee
import logging
import os
import random
from typing import Dict, Any, List
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from app.core.config import settings
from app.schemas.analyze import TrendAnalysisResponse, YearData, ZoneSeverityCount

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
        1. Service Account File
        2. Service Account (Email + Private Key) from Env
        3. OAuth2 User Refresh Token
        4. Application Default Credentials (ADC)
        """
        if self._initialized:
            return

        logger.info("Attempting to initialize Google Earth Engine...")

        try:
            # 1. Service Account Authentication from File
            if settings.GEE_SERVICE_ACCOUNT_FILE:
                try:
                    if os.path.exists(settings.GEE_SERVICE_ACCOUNT_FILE):
                        logger.info(f"Initializing GEE with Service Account file: {settings.GEE_SERVICE_ACCOUNT_FILE}")
                        credentials = service_account.Credentials.from_service_account_file(
                            settings.GEE_SERVICE_ACCOUNT_FILE
                        )
                        ee.Initialize(credentials, project=settings.GEE_PROJECT)
                        logger.info("GEE initialized with Service Account file.")
                        self._initialized = True
                        return
                    else:
                        logger.warning(f"GEE_SERVICE_ACCOUNT_FILE specified but not found: {settings.GEE_SERVICE_ACCOUNT_FILE}")
                except Exception as e:
                    logger.warning(f"Service Account file auth failed: {e}")

            # 2. Service Account Authentication from Environment Variables
            if settings.GEE_SERVICE_ACCOUNT and settings.GEE_PRIVATE_KEY:
                # Check for placeholders
                is_placeholder = (
                    "your-gee-service-account" in settings.GEE_SERVICE_ACCOUNT or 
                    "your-project-id" in settings.GEE_SERVICE_ACCOUNT or
                    "..." in settings.GEE_PRIVATE_KEY or
                    "BEGIN PRIVATE KEY" not in settings.GEE_PRIVATE_KEY
                )
                
                if is_placeholder:
                    logger.warning("GEE Service Account credentials appear to be placeholders. Skipping...")
                else:
                    try:
                        logger.info("Initializing GEE with Service Account from environment...")
                        private_key = settings.GEE_PRIVATE_KEY.replace('\\n', '\n')
                        
                        # Construct credentials info dict for google-auth
                        info = {
                            "client_email": settings.GEE_SERVICE_ACCOUNT,
                            "private_key": private_key,
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "type": "service_account",
                        }
                        credentials = service_account.Credentials.from_service_account_info(info)
                        ee.Initialize(credentials, project=settings.GEE_PROJECT)
                        logger.info("GEE initialized with Service Account from environment.")
                        self._initialized = True
                        return
                    except Exception as e:
                        logger.warning(f"Service Account environment auth failed: {e}")

            # 3. OAuth2 Refresh Token Authentication
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

            # 4. Fallback to Application Default Credentials (ADC)
            try:
                logger.info("Initializing GEE with Application Default Credentials (ADC)...")
                ee.Initialize(project=settings.GEE_PROJECT)
                logger.info("GEE initialized with ADC.")
                self._initialized = True
                return
            except Exception as e:
                logger.warning(f"ADC initialization failed: {e}")

            # If all methods failed
            logger.error("All GEE initialization methods failed. GEE features will not be available.")
            # We don't raise RuntimeError here to allow the rest of the app to start.
            # GEE-dependent methods will fail later when they check self._initialized.

        except Exception as e:
            logger.error(f"Unexpected error during GEE initialization: {e}")

    def _ensure_initialized(self):
        """
        Ensures GEE is initialized before performing operations.
        Raises RuntimeError if initialization fails.
        """
        if not self._initialized:
            self.initialize()
            if not self._initialized:
                raise RuntimeError("GEE is not initialized. Please check your credentials.")

    def test_connection(self):
        """
        Verifies the GEE connection by querying the SRTM elevation dataset.
        """
        try:
            self._ensure_initialized()
            image = ee.Image("USGS/SRTMGL1_003")
            info = image.getInfo()
            return {"status": "success", "asset_id": info.get("id")}
        except Exception as e:
            logger.error(f"GEE test connection failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_sentinel1_collection(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str):
        """
        Filters the Sentinel-1 ImageCollection based on location and date.
        """
        self._ensure_initialized()
        
        # ... rest of the method unchanged ...

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

    def preprocess_sentinel1(self, image):
        """
        Applies speckle filtering and converts SAR backscatter to dB.
        
        Steps:
        1. Focal Mean (7x7) to smooth radar noise (speckle).
        2. Logarithmic conversion to Decibels (dB) for better contrast.
        """
        # 1. Select the VV band (vertical-vertical polarization)
        vv = image.select('VV')

        # 2. Apply Speckle Filter (Focal Mean 7x7)
        # We use a circle kernel to smooth out the grainy 'salt and pepper' noise
        smoothed = vv.focal_mean(7, 'circle', 'pixels')

        # 3. Convert to dB: 10 * log10(Linear_Backscatter)
        # This makes water appear very dark (low values) and land bright
        vv_db = smoothed.log10().multiply(10).rename('VV_db')

        # Add the new band back to the original image so it carries all metadata
        return image.addBands(vv_db)

    def get_sentinel2_collection(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str, cloud_percentage: int = 20):
        """
        Filters the Sentinel-2 (Optical) collection with cloud masking.
        """
        self._ensure_initialized()

        # Create ROI geometry
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_meters).bounds()

        # Filter the S2 Harmonized Surface Reflectance collection
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                      .filterBounds(roi)
                      .filterDate(start_date, end_date)
                      # Filter by CLOUDY_PIXEL_PERCENTAGE metadata
                      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_percentage)))
        
        return collection, roi

    def get_latest_s2_image(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str):
        """
        Retrieves the clearest and most recent Sentinel-2 image.
        """
        collection, roi = self.get_sentinel2_collection(lat, lon, buffer_meters, start_date, end_date)
        
        # Check if empty
        count = collection.size().getInfo()
        if count == 0:
            return None

        # Sort by Cloud Cover (lowest first) then by Date (newest first)
        best_image = collection.sort('CLOUDY_PIXEL_PERCENTAGE').sort('system:time_start', False).first()
        
        if not best_image:
            return None
            
        return best_image.clip(roi)

    async def run_historical_analysis(
        self, lat: float, lng: float, radius_km: float, years: int
    ) -> TrendAnalysisResponse:
        """
        Performs historical risk analysis using Google Earth Engine.
        This is currently a stub returning mock data for SCRUM-49.
        """
        logger.info(f"Running historical analysis for {lat}, {lng} with radius {radius_km}km for {years} years")
        
        # Mock data generation
        current_year = 2024
        years_list = list(range(current_year - years, current_year))
        
        years_data = [
            YearData(year=y, value=random.uniform(10.0, 80.0))
            for y in years_list
        ]
        
        # Determine peak and min years from mock data
        peak_year_data = max(years_data, key=lambda x: x.value)
        min_year_data = min(years_data, key=lambda x: x.value)
        avg_ffi = sum(d.value for d in years_data) / len(years_data)
        
        return TrendAnalysisResponse(
            years_data=years_data,
            composite_tile_url="https://earthengine.googleapis.com/v1/projects/lankageo/maps/mock-composite/tiles/{z}/{x}/{y}",
            avg_ffi=round(avg_ffi, 2),
            peak_year=peak_year_data.year,
            min_year=min_year_data.year,
            trend_heatmap_url="https://earthengine.googleapis.com/v1/projects/lankageo/maps/mock-heatmap/tiles/{z}/{x}/{y}",
            zone_count_by_severity=[
                ZoneSeverityCount(severity="High", count=random.randint(5, 15)),
                ZoneSeverityCount(severity="Medium", count=random.randint(15, 30)),
                ZoneSeverityCount(severity="Low", count=random.randint(30, 50)),
            ]
        )

# Singleton instance
gee_service = GEEService()
