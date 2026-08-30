## 2026-08-17 - RouteMetrics.from_path Optimization
**Learning:** In hot loops analyzing path metrics in network graphs, looking up dictionary values (e.g. `utilization`) on every edge hop when they are only needed when a bottleneck candidate (min bandwidth) changes creates unnecessary dict lookup overhead. Pre-allocating `float("inf")` outside loops and removing redundant `float()` conversions on already-typed numerical attributes significantly reduces loop overhead.
**Action:** Avoid querying dict attributes in graph traversal loops unless the conditional requirement for those attributes is met.

## 2026-08-30 - BaseRouter.validate_path Graph Lookup Optimization
**Learning:** `Topology.nodes` and `Topology.edges` return freshly allocated lists (`list(self._graph.nodes)` / `list(self._graph.edges)`). Calling `node in topology.nodes` or `(u, v) in topology.edges` in graph traversal/validation loops converts $O(1)$ graph lookups into $O(V)$ and $O(E)$ list allocations and linear scans per hop, while `get_node`/`get_edge` create temporary dictionary copies.
**Action:** In graph validation and traversal hot paths, query the underlying `topology.graph` directly (`node in graph.nodes`, `graph.has_edge(u, v)`, `graph.nodes[n]`, `graph.edges[u, v]`) to maintain $O(1)$ time complexity and zero memory allocations.
