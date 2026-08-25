## 2026-08-17 - RouteMetrics.from_path Optimization
**Learning:** In hot loops analyzing path metrics in network graphs, looking up dictionary values (e.g. `utilization`) on every edge hop when they are only needed when a bottleneck candidate (min bandwidth) changes creates unnecessary dict lookup overhead. Pre-allocating `float("inf")` outside loops and removing redundant `float()` conversions on already-typed numerical attributes significantly reduces loop overhead.
**Action:** Avoid querying dict attributes in graph traversal loops unless the conditional requirement for those attributes is met.

## 2026-08-18 - MetricsCollectionResult.to_dataframe Optimization
**Learning:** Calling Pydantic's `model_dump()` in a list comprehension across thousands of Pydantic model instances to build a pandas DataFrame creates significant serialization and validation overhead. Constructing the DataFrame column-wise using direct attribute list comprehensions into a dictionary (`{"col": [m.col for m in items]}`) avoids per-item dict creation and Pydantic field serialization overhead, yielding a ~3x performance speedup.
**Action:** Prefer column-wise dict-of-lists construction over list of `model_dump()` dicts when converting lists of Pydantic models to pandas DataFrames.
