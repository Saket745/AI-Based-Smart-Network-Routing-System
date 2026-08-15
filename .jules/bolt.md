# Bolt's Performance Journal

## 2026-08-15 - Python `.tolist()` vs NumPy `.to_numpy()` for Pydantic Model Ingestion
**Learning:** Converting Pandas DataFrame columns using `.to_numpy()` before `zip()` iteration is significantly slower (~2x) than using standard Python lists (`.tolist()`) when instantiating Pydantic models. NumPy scalar types (e.g., `np.int64`, `np.float64`) incur extra coercion overhead inside Pydantic constructors compared to native Python `int`, `float`, and `str`.
**Action:** Use `.tolist()` on DataFrame columns when iterating over row values to instantiate Pydantic model instances.
