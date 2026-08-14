## 2026-08-13 - O(1) Set Lookup for Dynamic Subgraph Filters

**Learning:** When using NetworkX `subgraph_view` callbacks (`filter_node` and `filter_edge`), invoking dictionary lookups, type casting (`str(...)`), and `.lower()` inside node/edge filtering callbacks introduces significant function-call and object allocation micro-overhead during graph traversals. Utilizing fast $O(1)$ set membership lookups against cached local references to `topology._down_nodes` and `topology._down_edges` dramatically reduces per-node/edge traversal cost.

**Action:** Prefer direct set membership checks (`node not in down_nodes`) on local set references inside NetworkX subgraph view callbacks rather than querying node/edge attribute dictionaries directly.
