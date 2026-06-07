import ee
import sys
import os
import time

# Add the project path to sys.path to import our app
sys.path.append(os.path.abspath('lankageo-backend/backend'))

from app.services.gee_service import gee_service
from app.core.config import settings

def train_rf():
    print("--- LG-109: Random Forest Model Training ---")
    
    try:
        gee_service.initialize()
        print("GEE Initialized.")
    except Exception as e:
        print(f"Failed to initialize GEE: {e}")
        return

    # 1. Load Training Labels
    asset_path = getattr(settings, "GEE_TRAINING_LABELS_PATH", None)
    if not asset_path or "placeholder" in asset_path:
        asset_path = f"projects/{settings.GEE_PROJECT}/assets/sen1floods11_labels"
        
    try:
        labels_fc = ee.FeatureCollection(asset_path)
        print(f"Loaded training labels from: {asset_path}")
    except Exception as e:
        print(f"ERROR: Could not load training labels from {asset_path}.")
        return

    # 2. Features Configuration
    required_features = ['VV_db', 'NDWI', 'NDVI', 'elevation', 'HAND']
    label_col = 'label'
    
    print("Sampling features point-by-point from localized satellite context...")
    
    elevation = ee.Image("USGS/SRTMGL1_003").select('elevation').rename('elevation')
    hand = ee.Image("MERIT/Hydro/v1_0_1").select('hnd').rename('HAND')

    def sample_single_polygon(feat):
        geom = feat.geometry()
        
        # Parse dates
        s1_date = ee.Date.parse('YYYY/MM/dd HH:mm:ss', feat.get('s1_date'))
        s2_date = ee.Date.parse('YYYY/MM/dd HH:mm:ss', feat.get('s2_date'))
        
        # S1 Collection
        s1_col = ee.ImageCollection('COPERNICUS/S1_GRD')\
            .filterBounds(geom)\
            .filterDate(s1_date.advance(-15, 'day'), s1_date.advance(15, 'day'))\
            .filter(ee.Filter.eq('instrumentMode', 'IW'))\
            .filter(ee.Filter.Or(
                ee.Filter.listContains('transmitterReceiverPolarization', 'VV'),
                ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')
            ))\
            .select(['VV'])
            
        # S2 Collection
        s2_col = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')\
            .filterBounds(geom)\
            .filterDate(s2_date.advance(-15, 'day'), s2_date.advance(15, 'day'))\
            .select(['B3', 'B4', 'B8'])

        has_s1 = s1_col.size().gt(0)
        has_s2 = s2_col.size().gt(0)
        
        def get_sampled_data():
            s1 = s1_col.median()
            s2 = s2_col.median()
            vv_db = s1.select('VV').rename('VV_db')
            ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI')
            ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI')
            stack = ee.Image.cat([vv_db, ndwi, ndvi, elevation, hand])
            # Sample points from the polygon - 300 for robustness
            sampled = stack.sample(region=geom, scale=30, numPixels=300)
            return sampled.map(lambda f: f.set('label', ee.Number(f.get('NDWI')).gt(0)))

        return ee.FeatureCollection(ee.Algorithms.If(
            has_s1.And(has_s2),
            get_sampled_data(),
            ee.FeatureCollection([])
        ))

    # Create the training dataset
    all_points = labels_fc.filter(ee.Filter.notNull(['.geo']))\
        .map(sample_single_polygon)\
        .flatten()\
        .filter(ee.Filter.notNull(required_features))
    
    total_size = all_points.size().getInfo()
    print(f"Total valid training points extracted: {total_size}")
    
    if total_size == 0:
        print("FAILURE: No valid training data found.")
        return

    # 3. Split into Train/Test
    all_points = all_points.randomColumn('random')
    train_set = all_points.filter(ee.Filter.lt('random', 0.7))
    test_set = all_points.filter(ee.Filter.gte('random', 0.7))
    
    print(f"Split data: Train={train_set.size().getInfo()}, Test={test_set.size().getInfo()}")

    # 4. Train Classifier
    print(f"Training smileRandomForest(100) on {required_features}...")
    classifier = gee_service.train_rf_classifier(train_set, required_features, label_property=label_col)
    
    # 5. Validate
    print("Validating model...")
    metrics = gee_service.validate_classifier(classifier, test_set, label_property=label_col)
    
    print("\n--- Model Performance ---")
    print(f"Overall Accuracy: {metrics['accuracy']:.4f}")
    print(f"Kappa Statistic:  {metrics['kappa']:.4f}")
    
    if metrics['accuracy'] >= 0.87 and metrics['kappa'] >= 0.75:
        print("\nSUCCESS: Model meets performance requirements!")
        model_name = f"flood_rf_model_{int(time.time())}"
        asset_id = f"projects/{settings.GEE_PROJECT}/assets/{model_name}"
        
        print(f"Exporting model to: {asset_id}...")
        # Use dummy point geometry and attach classifier properties directly
        dummy_geom = ee.Geometry.Point([0, 0])
        # Extract model configuration as a dictionary
        model_props = classifier.explain()
        # Export as a FeatureCollection where the first feature contains the classifier model
        task = ee.batch.Export.table.toAsset(
            collection=ee.FeatureCollection([ee.Feature(dummy_geom, model_props)]),
            description=f"Export_{model_name}",
            assetId=asset_id
        )
        task.start()
        print(f"Export task started (ID: {task.id}). Please wait a few minutes for the asset to appear in GEE.")
    else:
        print("\nWARNING: Model performance is below targets.")

if __name__ == "__main__":
    train_rf()
