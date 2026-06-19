# MODEL_REGISTRY_SPEC.md

## 1. Overview
The `ModelStore` registry is updated to support serialization and integrity validation for PyTorch GNN checkpoints.

---

## 2. Serialization Payload for GNNs
When saving a trained GNN model (GCN or GraphSAGE), the saved dictionary contains:
1. **`model_type`**: `"gcn"` or `"graphsage"`.
2. **`state_dict`**: The trained PyTorch parameters dictionary.
3. **`feature_metadata`**: List of node and edge feature keys used during training.
4. **`hyperparameters`**: Hidden dimension sizes, learning rates, dropouts, etc.
5. **`is_trained`**: `True` flag.

---

## 3. Storage and Integrity Checks
* Files are saved with the `.pt` extension under `models/` (e.g., `models/gnn_gcn_v1.pt`).
* Upon saving, the `ModelStore` generates a metadata file containing a SHA-256 checksum of the `.pt` binary.
* Upon loading, the checksum of the model file is recalculated and matched against the metadata checksum to prevent loading corrupt or altered model files.
