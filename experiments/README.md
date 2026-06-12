# Experiments and Research Isolation

This directory is designated for experimental algorithms, exploratory notebooks, benchmark scripts, and prototype models.

## Isolation Rules
1. **No Production Impact:** Code in this directory must never be imported by production code under `src/`.
2. **Experimental Dependencies:** If an experiment requires external libraries not present in `pyproject.toml`, document them in a local `requirements.txt` or a markdown file within the experiment's folder.
3. **No Direct Commits of Large Models/Datasets:** All large dataset files (.csv, .json) or model checkpoints (.pt, .onnx, .joblib) must be added to `.gitignore` or kept under the 5MB size limit.
4. **Clean Integration:** Once an experiment is proven and approved, refactor the code to adhere to system interfaces and move it to `src/`.

## Structure
Create subdirectories for each research prototype, e.g.:
```text
experiments/
├── 202606_lstm_congestion_prediction/
├── 202606_ppo_routing_agent/
└── README.md
```
