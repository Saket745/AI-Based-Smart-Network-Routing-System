## 2026-08-13 - O(1) Set Lookup for Dynamic Subgraph Filters

**Learning:** When using NetworkX `subgraph_view` callbacks (`filter_node` and `filter_edge`), invoking dictionary lookups, type casting (`str(...)`), and `.lower()` inside node/edge filtering callbacks introduces significant function-call and object allocation micro-overhead during graph traversals. Utilizing fast $O(1)$ set membership lookups against cached local references to `topology._down_nodes` and `topology._down_edges` dramatically reduces per-node/edge traversal cost.

**Action:** Prefer direct set membership checks (`node not in down_nodes`) on local set references inside NetworkX subgraph view callbacks rather than querying node/edge attribute dictionaries directly.
=======
# Bolt's Performance Journal

## 2026-08-15 - Python `.tolist()` vs NumPy `.to_numpy()` for Pydantic Model Ingestion
**Learning:** Converting Pandas DataFrame columns using `.to_numpy()` before `zip()` iteration is significantly slower (~2x) than using standard Python lists (`.tolist()`) when instantiating Pydantic models. NumPy scalar types (e.g., `np.int64`, `np.float64`) incur extra coercion overhead inside Pydantic constructors compared to native Python `int`, `float`, and `str`.
**Action:** Use `.tolist()` on DataFrame columns when iterating over row values to instantiate Pydantic model instances.
