import ee
import sys
import os

# Add the project path to sys.path to import our app
sys.path.append(os.path.abspath('lankageo-backend/backend'))

from app.services.gee_service import gee_service
from app.core.config import settings

def seed_training_data():
    """
    Verifies the existence of Sen1Floods11 training labels in GEE assets.
    If not found, provides instructions for manual upload or common public paths.
    """
    print("--- Sen1Floods11 Data Seeder ---")
    
    try:
        gee_service.initialize()
        print("GEE Initialized.")
    except Exception as e:
        print(f"Failed to initialize GEE: {e}")
        return

    # Check for asset path in environment or use a default placeholder
    asset_path = getattr(settings, "GEE_TRAINING_LABELS_PATH", None)
    
    # Common community paths for Sen1Floods11 (if public)
    # Note: Users often upload this to their own project assets.
    potential_paths = [
        asset_path,
        f"projects/{settings.GEE_PROJECT}/assets/sen1floods11_labels",
        "projects/sat-io/open-datasets/sen1floods11/v1_1/labels" # Example community path
    ]
    
    found_path = None
    for path in potential_paths:
        if not path:
            continue
        try:
            print(f"Checking asset: {path}...")
            fc = ee.FeatureCollection(path)
            # Try to get the size to confirm access
            count = fc.size().getInfo()
            print(f"SUCCESS: Found {count} features at {path}")
            found_path = path
            break
        except Exception:
            print(f"Not found or no access: {path}")

    if found_path:
        print(f"\nTraining data is ready at: {found_path}")
        print("You can now proceed to run the training script.")
    else:
        print("\n--- ACTION REQUIRED ---")
        print("The Sen1Floods11 training labels were not found in your GEE assets.")
        print("Please follow these steps:")
        print("1. Download 'v1.1/data/flood_events/HandLabeled/S1Variant/' from gs://sen1floods11/")
        print("2. Upload the ground truth labels (FeatureCollection/Table) to your GEE project.")
        print(f"3. Recommended Path: projects/{settings.GEE_PROJECT}/assets/sen1floods11_labels")
        print("4. Update your .env with GEE_TRAINING_LABELS_PATH=your/asset/path")

if __name__ == "__main__":
    seed_training_data()
