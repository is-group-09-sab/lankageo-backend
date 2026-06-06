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
        latest_image = ee.Image(collection.sort('system:time_start', False).first())
        
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

        baseline_image = ee.Image(baseline_collection.map(add_date_diff).sort('date_diff').first())

        return baseline_image.clip(roi)

    def compute_change_ratio(self, pre_image, post_image, threshold: float = 1.25, use_otsu: bool = False):
        """
        Computes the change ratio between pre and post images for flood detection.
        
        Formula: Pre_event / Post_event (in linear scale)
        Logic: Water decreases backscatter, so Pre/Post > 1 indicates new water.
        """
        # 1. Pre-process both images (Speckle filtering is essential)
        # We MUST convert from dB to linear before calculating ratios
        pre_vv_linear = ee.Image(10.0).pow(pre_image.select('VV').divide(10.0)).focal_mean(7, 'circle', 'pixels')
        post_vv_linear = ee.Image(10.0).pow(post_image.select('VV').divide(10.0)).focal_mean(7, 'circle', 'pixels')

        # 2. Compute Ratio (Pre / Post)
        ratio = pre_vv_linear.divide(post_vv_linear).rename('change_ratio')

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
        Applies speckle filtering and ensures the image has a VV_db band.
        
        Steps:
        1. Convert to linear scale if necessary (S1_GRD is in dB).
        2. Focal Mean (7x7) to smooth radar noise (speckle).
        3. Convert back to dB for the feature stack.
        """
        # 1. Select the VV band
        vv = image.select('VV')

        # 2. Convert from dB to linear: 10^(dB/10)
        # S1_GRD is log-scaled, so we MUST linearize before smoothing
        vv_linear = ee.Image(10.0).pow(vv.divide(10.0))

        # 3. Apply Speckle Filter (Focal Mean 7x7)
        smoothed_linear = vv_linear.focal_mean(7, 'circle', 'pixels')

        # 4. Convert back to dB: 10 * log10(Linear)
        vv_db = smoothed_linear.log10().multiply(10).rename('VV_db')

        # Add the new band back to the original image
        return image.addBands(vv_db)

    def compute_ndwi(self, image, threshold: float = 0.3):
        """
        Computes the Normalized Difference Water Index (NDWI) for Sentinel-2.
        
        Formula: (Green - NIR) / (Green + NIR) => (B3 - B8) / (B3 + B8)
        """
        # 1. Calculate NDWI
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')

        # 2. Create binary water mask
        water_mask = ndwi.gt(threshold).rename('ndwi_water_mask')

        # Return concatenated image
        return image.addBands([ndwi, water_mask])

    def compute_ndvi(self, image):
        """
        Computes the Normalized Difference Vegetation Index (NDVI) for Sentinel-2.
        
        Formula: (NIR - Red) / (NIR + Red) => (B8 - B4) / (B8 + B4)
        """
        return image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def compute_radar_ratio(self, image):
        """
        Computes the VH/VV ratio for Sentinel-1 in linear scale.
        Useful for distinguishing between urban areas and open water.
        """
        # Convert both bands to linear before calculating ratio
        vh_linear = ee.Image(10.0).pow(image.select('VH').divide(10.0))
        vv_linear = ee.Image(10.0).pow(image.select('VV').divide(10.0))
        
        return vh_linear.divide(vv_linear).rename('VH_VV_ratio')

    def get_terrain_data(self, roi):
        """
        Loads SRTM Elevation and HAND (Height Above Nearest Drainage) data.
        Resamples to 10m resolution to match Sentinel data.
        """
        # 1. Load SRTM Elevation (30m)
        elevation = ee.Image("USGS/SRTMGL1_003").select('elevation').rename('elevation')
        
        # 2. Load Global HAND (Height Above Nearest Drainage)
        # We use MERIT Hydro as it is a high-quality, accessible global dataset
        hand = ee.Image("MERIT/Hydro/v1_0_1").select('hnd').rename('HAND')
        
        # Combine and clip
        terrain = ee.Image.cat([elevation, hand]).clip(roi)
        
        # 3. Resample to 10m using bilinear interpolation
        # This ensures the terrain features align with the 10m satellite pixels
        return terrain.resample('bilinear')

    def create_rf_feature_stack(self, lat, lon, buffer, s1_start, s1_end, s2_start, s2_end, orbit_pass="DESCENDING"):
        """
        Orchestrates the creation of a 6-band feature stack for RF classification.
        Bands: [VV_db, VH_VV_ratio, NDWI, NDVI, elevation, HAND]
        """
        if not self._initialized:
            self.initialize()

        # 1. Get Sentinel-1 (Radar)
        s1_image = self.get_latest_s1_image(lat, lon, buffer, s1_start, s1_end, orbit_pass)
        if not s1_image:
            raise ValueError("No Sentinel-1 imagery found for the specified period.")
        
        # Preprocess S1 (Speckle + dB)
        s1_processed = self.preprocess_sentinel1(s1_image)
        vv_db = s1_processed.select('VV_db')
        vh_vv = self.compute_radar_ratio(s1_image)
        
        # 2. Get Sentinel-2 (Optical)
        s2_image = self.get_latest_s2_image(lat, lon, buffer, s2_start, s2_end)
        if not s2_image:
            raise ValueError("No Sentinel-2 imagery found for the specified period.")
            
        ndwi = self.compute_ndwi(s2_image).select('NDWI')
        ndvi = self.compute_ndvi(s2_image)
        
        # 3. Get Terrain Data
        terrain = self.get_terrain_data(s1_image.geometry())
        
        # 4. Final Stack (Concatenate all bands)
        # We use s1_image.geometry() as the master projection template
        stack = ee.Image.cat([
            vv_db,
            vh_vv,
            ndwi,
            ndvi,
            terrain.select('elevation'),
            terrain.select('HAND')
        ]).clip(s1_image.geometry())
        
        return stack, {
            "s1_id": s1_image.get('system:index').getInfo(),
            "s2_id": s2_image.get('system:index').getInfo()
        }

    def train_rf_classifier(self, training_data, features, label_property='label', num_trees=100):
        """
        Trains a Random Forest classifier in GEE.
        
        Args:
            training_data: ee.FeatureCollection containing sampled features and labels.
            features: List of band names to use as input features.
            label_property: The property name for the ground truth label.
            num_trees: Number of decision trees.
        """
        if not self._initialized:
            self.initialize()
            
        classifier = ee.Classifier.smileRandomForest(num_trees).train(
            features=training_data,
            classProperty=label_property,
            inputProperties=features
        )
        
        return classifier

    def validate_classifier(self, classifier, test_data, label_property='label'):
        """
        Validates a classifier using a test FeatureCollection.
        Returns accuracy metrics.
        """
        validated = test_data.classify(classifier)
        error_matrix = validated.errorMatrix(label_property, 'classification')
        
        return {
            "accuracy": error_matrix.accuracy().getInfo(),
            "kappa": error_matrix.kappa().getInfo(),
            "consumers_accuracy": error_matrix.consumersAccuracy().getInfo(),
            "producers_accuracy": error_matrix.producersAccuracy().getInfo()
        }

    def sample_features(self, feature_stack, points_fc, scale=10):
        """
        Samples values from a feature stack at the given point locations.
        """
        return feature_stack.sampleRegions(
            collection=points_fc,
            properties=[],
            scale=scale,
            geometries=True
        )

    def compute_otsu_mask(self, image, band='VV'):
        """
        Calculates the Otsu threshold directly on a single image band
        and returns a binary water mask.
        """
        if not self._initialized:
            self.initialize()
            
        try:
            # Calculate histogram
            hist = image.reduceRegion(
                reducer=ee.Reducer.histogram(255, 0.5), # 0.5 dB buckets for SAR
                geometry=image.geometry(),
                scale=30,
                maxPixels=1e9
            ).get(band).getInfo()
            
            if not hist:
                return image.select(band).lt(-18).rename('otsu_water_mask') # Static fallback
                
            threshold = self._calculate_otsu_threshold(hist)
            return image.select(band).lt(threshold).rename('otsu_water_mask')
        except Exception as e:
            logger.warning(f"Otsu mask calculation failed, using static fallback: {e}")
            return image.select(band).lt(-18).rename('otsu_water_mask')

    def detect_floods_ensemble(self, lat, lon, buffer, pre_start, pre_end, post_start, post_end, weights=None):
        """
        Ensemble flood detection using a weighted 3-signal approach.
        
        Signals:
        1. SAR Change Detection (Ratio)
        2. SAR Post-Event Otsu Thresholding
        3. Random Forest Multi-sensor Classification
        """
        if not self._initialized:
            self.initialize()

        if weights is None:
            weights = {"rf": 0.5, "change": 0.3, "otsu": 0.2}

        # 1. Get Base Images
        s1_pre = self.get_latest_s1_image(lat, lon, buffer, pre_start, pre_end)
        s1_post = self.get_latest_s1_image(lat, lon, buffer, post_start, post_end)
        
        if not s1_pre or not s1_post:
            raise ValueError("Required Sentinel-1 imagery missing for ensemble.")

        # 2. Signal 1: Change Detection (Ratio + Otsu)
        change_img = self.compute_change_ratio(s1_pre, s1_post, use_otsu=True)
        s1_change_mask = change_img.select('flood_mask')

        # 3. Signal 2: Direct Post-Otsu
        s1_post_otsu_mask = self.compute_otsu_mask(s1_post, 'VV')

        # 4. Signal 3: Random Forest Classification
        # We need S2 for the feature stack
        s2_post = self.get_latest_s2_image(lat, lon, buffer, post_start, post_end)
        if not s2_post:
            # Fallback if S2 is missing: Use SAR signals only
            logger.warning("Sentinel-2 missing for ensemble. Scaling SAR weights.")
            weights = {"change": 0.6, "otsu": 0.4, "rf": 0.0}
            rf_mask = ee.Image.constant(0)
        else:
            feature_stack, _ = self.create_rf_feature_stack(
                lat, lon, buffer, post_start, post_end, post_start, post_end
            )
            
            # Load the persisted model (using the latest version or a settings-defined ID)
            model_id = getattr(settings, "GEE_RF_MODEL_PATH", f"projects/{settings.GEE_PROJECT}/assets/flood_rf_model_1780752620")
            
            try:
                # To use the classifier, we must parse it from the saved asset
                model_asset = ee.FeatureCollection(model_id).first()
                # Newer GEE Python API handles serialized classifiers
                classifier = ee.Classifier.decisionTreeEnsemble(model_asset.get('classifier'))
                rf_mask = feature_stack.classify(classifier).rename('rf_mask')
            except Exception as e:
                logger.error(f"Failed to load RF model for ensemble at {model_id}: {e}")
                # Fallback to SAR signals only
                weights = {"change": 0.6, "otsu": 0.4, "rf": 0.0}
                rf_mask = ee.Image.constant(0)

        # 5. Weighted Ensemble Calculation
        # Final Score = (W1 * S1) + (W2 * S2) + (W3 * S3)
        ensemble_score = s1_change_mask.multiply(weights["change"])\
            .add(s1_post_otsu_mask.multiply(weights["otsu"]))\
            .add(rf_mask.multiply(weights["rf"]))\
            .rename('ensemble_score')

        # 6. Apply Consensus Threshold (0.5)
        final_flood_mask = ensemble_score.gte(0.5).rename('final_flood_mask')

        return ee.Image.cat([
            ensemble_score, 
            final_flood_mask, 
            s1_change_mask.rename('signal_change'),
            s1_post_otsu_mask.rename('signal_otsu'),
            rf_mask.rename('signal_rf')
        ]).clip(s1_post.geometry()) # Ensure the result is bounded for reduceRegion

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
        Normalized to 0-1 range by dividing by 10000.
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
            
        # Divide by 10000 for reflectance normalization (LG-103)
        # We copy properties to ensure metadata like 'system:index' is preserved
        return ee.Image(best_image.divide(10000).copyProperties(best_image, best_image.propertyNames())).clip(roi)

# Singleton instance
gee_service = GEEService()
