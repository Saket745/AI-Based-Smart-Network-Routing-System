## 2026-08-05 - [Visual Progress Clarity in live consoles]
**Learning:** Terminal visualizers (like Rich Live panels) can suffer from brief flickering or empty/blank layout placeholder flashes on startup if the initial view is not populated with informative loading/waiting states before tick data collection begins.
**Action:** Always initialize layouts with robust visual placeholders and friendly states (e.g. "Initializing... Waiting for simulation to start...") to guarantee immediate user feedback and high aesthetic polish from the first frame.

## 2026-08-06 - [Consistent visual status indicators in CLI output]
**Learning:** Raw numeric values (like utilization percentages) in CLI metrics tables are harder to parse quickly. Color-coding combined with intuitive visual indicator emojis (🟢, 🟡, 🔴) improves readability and maintains visual consistency across terminal interfaces (such as live consoles and route computation commands).
**Action:** Use a unified `_format_utilization` helper to present utilization metrics with clear threshold color coding and visual status indicators.
