## 2026-08-05 - [Visual Progress Clarity in live consoles]
**Learning:** Terminal visualizers (like Rich Live panels) can suffer from brief flickering or empty/blank layout placeholder flashes on startup if the initial view is not populated with informative loading/waiting states before tick data collection begins.
**Action:** Always initialize layouts with robust visual placeholders and friendly states (e.g. "Initializing... Waiting for simulation to start...") to guarantee immediate user feedback and high aesthetic polish from the first frame.

## 2026-08-11 - [Rich text markup parsing in event logs]
**Learning:** Rendering logged events as plain `Text` in Rich terminal consoles displays formatting tags (like `[bold red]`, `[green]`) literally. To render proper colors and styles, they must be parsed via `Text.from_markup()`, while escaping non-markup brackets (like timestamps `[HH:MM:SS]`) as `\[HH:MM:SS\]` to prevent formatting or parsing errors.
**Action:** Convert log lines to `Text` using `Text.from_markup()` after cleanly escaping non-formatting brackets in the log prefix.

## 2026-08-18 - [Export CLI visual feedback consistency and summary metadata]
**Learning:** Plain `click.echo` messages for CLI file export commands lack visual feedback and leave users uncertain about the volume of data exported until they inspect the file.
**Action:** Use Rich console formatting (`Console().print`) with status indicators (`[green]+[/green]`) and append summary statistics (e.g., node/edge counts or record counts) to provide instant visual verification of output size and format.
