## 2026-08-17 - RouteMetrics.from_path Optimization
**Learning:** In hot loops analyzing path metrics in network graphs, looking up dictionary values (e.g. `utilization`) on every edge hop when they are only needed when a bottleneck candidate (min bandwidth) changes creates unnecessary dict lookup overhead. Pre-allocating `float("inf")` outside loops and removing redundant `float()` conversions on already-typed numerical attributes significantly reduces loop overhead.
**Action:** Avoid querying dict attributes in graph traversal loops unless the conditional requirement for those attributes is met.

## 2026-08-18 - ECMP Router Weight Function Optimization
**Learning:** When invoking NetworkX shortest path routines (such as `nx.all_shortest_paths` or `nx.shortest_simple_paths`), passing string attribute keys directly instead of Python callable wrappers enables NetworkX internal routines to execute fast dictionary lookups (`d.get(weight, 1)`) without incurring Python function call stack frame allocations for every edge traversal.
**Action:** Always return string attribute names directly rather than wrapping attribute lookups in Python lambda/functions when configuring NetworkX algorithm parameters.
