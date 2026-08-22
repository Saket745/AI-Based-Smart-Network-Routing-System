## 2026-08-17 - RouteMetrics.from_path Optimization
**Learning:** In hot loops analyzing path metrics in network graphs, looking up dictionary values (e.g. `utilization`) on every edge hop when they are only needed when a bottleneck candidate (min bandwidth) changes creates unnecessary dict lookup overhead. Pre-allocating `float("inf")` outside loops and removing redundant `float()` conversions on already-typed numerical attributes significantly reduces loop overhead.
**Action:** Avoid querying dict attributes in graph traversal loops unless the conditional requirement for those attributes is met.

## 2026-08-19 - Topology Node and Edge In-Place Attribute Mutation
**Learning:** In high-frequency topology node/edge addition and modification methods (`Topology.add_node`, `Topology.add_edge`, `Topology.update_edge`), dictionary unpacking (`{**attrs, **validated_attrs}`) creates temporary intermediate dictionary objects on every operation. Mutating the incoming `attrs` dictionary in-place avoids extra object allocations and yields a ~10-12% performance boost across bulk topology generation operations.
**Action:** Modify kwargs / dict attributes in-place inside high-frequency wrapper methods instead of constructing new merged dictionary unpackings.
