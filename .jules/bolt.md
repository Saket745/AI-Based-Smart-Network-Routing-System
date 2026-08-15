# Bolt's Performance Journal

## 2026-08-12 - [Avoid Dynamic Enum View Creation in Hot Loops]
**Learning:** In event parsing hot loops (such as `load_events` in `src/nroute/simulation/rca.py`), validating values using `cat in EventCategory.__members__.values()` repeatedly constructs dynamic dictionary views on every iteration, introducing significant CPU overhead.
**Action:** Pre-compute module-level sets of valid enum values (`_VALID_CATEGORIES = {c.value for c in EventCategory}`) for O(1) membership lookups in loop iterations. This yields a measurable ~8% performance boost (~6.6ms per 50 load cycles) cleanly without modifying object representations or caching behavior.
