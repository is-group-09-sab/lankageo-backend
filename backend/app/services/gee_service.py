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

    def get_latest_s1_image(self, lat: float, lon: float, buffer_meters: float, start_date: str, end_date: str, orbit_pass: str = "DESCENDING"):
        """
        Retrieves the most recent Sentinel-1 image mosaic for the given parameters.
        """
        collection, roi = self.get_sentinel1_collection(lat, lon, buffer_meters, start_date, end_date)
        
        # Apply orbit pass filter if specified
        if orbit_pass:
            collection = collection.filter(ee.Filter.eq('orbitProperties_pass', orbit_pass))

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

    def get_baseline_s1_image(self, post_image, days_back: int = 30):
        """
        Finds a baseline Sentinel-1 image from the same relative orbit as the post-event image.
        
        Args:
            post_image: The ee.Image representing the post-event state.
            days_back: Number of days prior to look for a baseline.
        """
        # 1. Extract orbital metadata from the post-event image
        # This is critical for matching the geometry (incidence angle)
        relative_orbit = post_image.get('relativeOrbitNumber_start')
        orbit_pass = post_image.get('orbitProperties_pass')
        post_date = ee.Date(post_image.get('system:time_start'))
        roi = post_image.geometry()

        # 2. Define the baseline search window
        # We look for images ~30 days prior to the post-event image
        pre_date_start = post_date.advance(-days_back - 15, 'day')
        pre_date_end = post_date.advance(-days_back + 15, 'day')

        # 3. Filter the collection for the same orbital parameters
        baseline_collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                               .filterBounds(roi)
                               .filterDate(pre_date_start, pre_date_end)
                               .filter(ee.Filter.eq('relativeOrbitNumber_start', relative_orbit))
                               .filter(ee.Filter.eq('orbitProperties_pass', orbit_pass))
                               .filter(ee.Filter.eq('instrumentMode', 'IW')))

        # Check if we found anything
        count = baseline_collection.size().getInfo()
        if count == 0:
            return None

        # Sort by proximity to the target days_back (closest to post_date - days_back)
        target_date = post_date.advance(-days_back, 'day')
        
        def add_date_diff(img):
            diff = ee.Number(img.get('system:time_start')).subtract(target_date.millis()).abs()
            return img.set('date_diff', diff)

        baseline_image = baseline_collection.map(add_date_diff).sort('date_diff').first()

        return baseline_image.clip(roi)

    def compute_change_ratio(self, pre_image, post_image, threshold: float = 1.25, use_otsu: bool = False):
        """
        Computes the change ratio between pre and post images for flood detection.
        
        Formula: Pre_event / Post_event
        Logic: Water decreases backscatter, so Pre/Post > 1 indicates new water.
        """
        # 1. Pre-process both images (Speckle filtering is essential)
        # We work with the raw VV band here (linear scale) for the ratio
        pre_vv = pre_image.select('VV').focal_mean(7, 'circle', 'pixels')
        post_vv = post_image.select('VV').focal_mean(7, 'circle', 'pixels')

        # 2. Compute Ratio (Pre / Post)
        # We use linear backscatter, not dB, for the ratio calculation
        ratio = pre_vv.divide(post_vv).rename('change_ratio')

        # 3. Dynamic Thresholding (Otsu) if requested
        final_threshold = threshold
        if use_otsu:
            try:
                # Calculate histogram of the ratio image
                # We use a 0.05 bucket width to capture the split between land and water
                hist = ratio.reduceRegion(
                    reducer=ee.Reducer.histogram(255, 0.05),
                    geometry=post_image.geometry(),
                    scale=30,
                    maxPixels=1e9
                ).get('change_ratio').getInfo()
                
                if hist:
                    final_threshold = self._calculate_otsu_threshold(hist)
                    logger.info(f"Calculated dynamic Otsu threshold: {final_threshold}")
            except Exception as e:
                logger.warning(f"Otsu calculation failed, falling back to static threshold: {e}")

        # 4. Apply Threshold
        flood_mask = ratio.gt(final_threshold).rename('flood_mask')

        # Return the multi-band image containing the ratio and the binary mask
        # We also store the threshold used in the image properties for traceability
        return ee.Image.cat([ratio, flood_mask]).set('applied_threshold', final_threshold)

    def _calculate_otsu_threshold(self, hist_data):
        """
        Implementation of the Otsu algorithm to find the optimal threshold 
        by maximizing between-class variance.
        """
        import numpy as np
        
        counts = np.array(hist_data['histogram'])
        means = np.array(hist_data['bucketMeans'])
        
        # Total number of pixels
        total = counts.sum()
        if total == 0:
            return 1.25 # Fallback
            
        # Probability of each bucket
        probs = counts / total
        
        # Cumulative sums
        weight1 = np.cumsum(probs)
        weight2 = 1.0 - weight1
        
        # Cumulative means
        mean1 = np.cumsum(means * probs) / weight1
        mean2 = (mean1[-1] * weight1[-1] - np.cumsum(means * probs)) / weight2
        
        # Between-class variance
        # We ignore warnings for division by zero (handled by nan_to_num)
        with np.errstate(divide='ignore', invalid='ignore'):
            variance_between = weight1 * weight2 * (mean1 - mean2)**2
            variance_between = np.nan_to_num(variance_between)
        
        # Index of max variance
        idx = np.argmax(variance_between)
        
        return float(means[idx])

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
        if not self._initialized:
            self.initialize()

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

# Singleton instance
gee_service = GEEService()
