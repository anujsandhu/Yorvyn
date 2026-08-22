import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ml_model import recommender

recommender.initialize()
print(f"Recommender data: {recommender.data is not None}")
if recommender.data is not None:
    print(f"Dataset size: {len(recommender.data)}")
else:
    print("Data is None - checking why...")
    print(f"Project root: {recommender.project_root}")
    print(f"Data dir exists: {recommender.data_dir.exists()}")
    print(f"Models dir exists: {recommender.models_dir.exists()}")
    
    # Try to list files
    if recommender.data_dir.exists():
        print(f"Data dir contents: {list(recommender.data_dir.glob('*.csv'))[:5]}")
    if recommender.models_dir.exists():
        print(f"Models dir contents: {list(recommender.models_dir.glob('*.pkl'))[:5]}")
