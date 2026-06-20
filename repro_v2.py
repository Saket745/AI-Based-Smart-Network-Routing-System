
import torch
import numpy as np
import pandas as pd
from nroute.ml.anomaly import AnomalyDetector
import os
import tempfile
import shutil

def run_repro():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy data
        df = pd.DataFrame(np.random.rand(100, 5), columns=[f"f{i}" for i in range(5)])

        # 1. Test Autoencoder
        print("Testing Autoencoder secure load...")
        detector = AnomalyDetector(model_type="autoencoder")
        detector.fit(df, epochs=1)

        ae_model_path = os.path.join(tmpdir, "test_ae_model.pt")
        detector.save(ae_model_path)

        try:
            new_detector = AnomalyDetector(model_type="autoencoder")
            new_detector.load(ae_model_path, allow_unsafe=False)
            print("SUCCESS: Autoencoder loaded securely!")
        except Exception as e:
            print(f"FAILURE: Autoencoder failed to load securely: {e}")

        # 2. Test Isolation Forest (New Zip Format)
        print("\nTesting Isolation Forest (New Format) load...")
        detector_if = AnomalyDetector(model_type="isolation_forest")
        detector_if.fit(df)

        if_model_path = os.path.join(tmpdir, "test_if_model.joblib")
        detector_if.save(if_model_path)

        # Should FAIL with allow_unsafe=False
        print("Testing with allow_unsafe=False (should fail)...")
        try:
            new_detector_if = AnomalyDetector(model_type="isolation_forest")
            new_detector_if.load(if_model_path, allow_unsafe=False)
            print("FAILURE: Isolation Forest loaded with allow_unsafe=False!")
        except Exception as e:
            print(f"SUCCESS: Isolation Forest failed to load as expected: {e}")

        # Should SUCCEED with allow_unsafe=True
        print("Testing with allow_unsafe=True (should succeed)...")
        try:
            new_detector_if = AnomalyDetector(model_type="isolation_forest")
            new_detector_if.load(if_model_path, allow_unsafe=True)
            print("SUCCESS: Isolation Forest loaded with allow_unsafe=True!")
        except Exception as e:
            print(f"FAILURE: Isolation Forest failed to load with allow_unsafe=True: {e}")

if __name__ == "__main__":
    run_repro()
