# Custom Extensions API — nroute

The `nroute` library provides open APIs to dynamically extend its routing capabilities and integrate custom machine learning or neural network models.

---

## 1. Custom Routing Strategies

You can add custom routing algorithms by inheriting from `BaseRouter` and registering them using the `@register_router` decorator. Once registered, your router can be resolved by name in `get_router()` and executed seamlessly via the CLI or the simulation engine.

### Example: A Random Walk Router

```python
import random
from typing import Any
from nroute import BaseRouter, register_router, Topology

@register_router("random-walk")
class RandomWalkRouter(BaseRouter):
    """A custom router that selects a random path from source to destination."""

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
    ) -> list[str]:
        # Filter active graph view
        subgraph = self._get_active_subgraph(topology)
        
        if source not in subgraph or destination not in subgraph:
            raise RoutingError("Source or destination node is down/missing.")
            
        path = [source]
        current = source
        visited = {source}
        max_hops = len(subgraph.nodes) * 2

        while current != destination:
            if len(path) > max_hops:
                raise RoutingError("Random walk exceeded max hop limit.")
            
            neighbors = list(subgraph.neighbors(current))
            if not neighbors:
                raise RoutingError(f"Dead end reached at node '{current}'.")
                
            # Prefer unvisited neighbors to prevent trivial loops
            unvisited = [n for n in neighbors if n not in visited]
            next_node = random.choice(unvisited if unvisited else neighbors)
            
            path.append(next_node)
            visited.add(next_node)
            current = next_node

        self.validate_path(topology, path, source, destination)
        return path
```

### Usage
```python
from nroute import get_router, Topology

# Automatically resolves to your custom registered router!
router = get_router("random-walk")

topo = Topology.load("data/sample_topology.json")
path = router.compute_path(topo, "A", "D")
print("Computed Path:", path)
```

---

## 2. Custom Neural Networks & Congestion Predictors

To use a custom machine learning model (such as a Graph Neural Network (GNN) or a custom scikit-learn classifier) for link congestion forecasting, initialize `CongestionPredictor` with `model_type="custom"` and pass your instantiated model.

### Requirements for Custom Congestion Predictor Models
Your custom model must implement either:
1. `train(self, features: pd.DataFrame, labels: np.ndarray) -> dict` or `fit(self, features: pd.DataFrame, labels: np.ndarray) -> None`.
2. `predict(self, features: pd.DataFrame) -> np.ndarray` (returning binary labels or probabilities) or `predict_proba(self, features: pd.DataFrame) -> np.ndarray` (returning probability matrix).

### Example: Custom Random Forest Congestion Predictor

```python
from sklearn.ensemble import RandomForestClassifier
from nroute.ml import CongestionPredictor

# 1. Instantiate the custom underlying model
rf_model = RandomForestClassifier(n_estimators=50, random_state=42)

# 2. Wrap it in the CongestionPredictor
predictor = CongestionPredictor(model_type="custom", custom_model=rf_model)

# 3. Train using standard nroute data structures
predictor.train(training_features, training_labels)

# 4. Predict
predictions_df = predictor.predict(test_features)
print(predictions_df.head())
```

---

## 3. Custom Anomaly Detection Models

Similarly, you can supply custom models for traffic anomaly detection (e.g. DDoS and black hole detection) using `AnomalyDetector(model_type="custom", custom_model=my_model)`.

### Requirements for Custom Anomaly Detectors
Your custom model must implement either:
1. `fit(self, features: pd.DataFrame) -> None` or `train(self, features: pd.DataFrame) -> None`.
2. `detect(self, features: pd.DataFrame) -> pd.DataFrame` returning `anomaly_score` and `is_anomaly` columns, or implement standard scikit-learn methods like `decision_function` or `predict`.

### Example: Custom One-Class SVM Anomaly Detector

```python
from sklearn.svm import OneClassSVM
from nroute.ml import AnomalyDetector

# 1. Instantiate the custom SVM
svm_model = OneClassSVM(nu=0.1, kernel="rbf", gamma=0.1)

# 2. Wrap it in AnomalyDetector
detector = AnomalyDetector(model_type="custom", custom_model=svm_model)

# 3. Train on normal traffic data
detector.fit(normal_traffic_features)

# 4. Detect anomalies
results_df = detector.detect(live_traffic_features)
print(results_df.head())
```
