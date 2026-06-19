# EVALUATION_SPEC.md

## 1. Evaluation Objectives
The GNN evaluation framework measures the accuracy of predicting link-level congestion and path-level routing latencies.

---

## 2. Target Metrics

### 2.1 Link Congestion Prediction (Binary Classification)
Evaluated on the test split:
* **Accuracy**: Fraction of correct link predictions.
* **Precision / Recall / F1-Score**: Measures how well the model predicts congested links vs normal links (especially under class imbalance, as congestion is relatively rare).

### 2.2 Path Latency Prediction (Regression)
Evaluated by summing predicted link latencies along calculated routing paths:
* **Mean Squared Error (MSE)** & **Mean Absolute Error (MAE)**: Absolute latency prediction error.
* **Pearson Correlation Coefficient**: Measures the linear correlation between predicted and actual path latencies.

---

## 3. Generalization to Unseen Topologies
The evaluation pipeline includes a validation test set of topologies that were **not** seen during training:
1. GNN is trained on Scale-Free and Small-World topologies.
2. Evaluated on Fat-Tree topologies to verify topological generalization.
3. Outperforms simple degree/utilization heuristics by >= 15%.
