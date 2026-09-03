# ⌨️ CLI Reference Guide

The `nroute` CLI provides a unified, production-grade interface to manage, simulate, diagnose, and validate network routing topologies using deterministic algorithms and automated pre-flight safety policies.

---

## 🚀 CLI Hierarchy & Subcommand Groups

The CLI is structured into several command groups, each focused on a specific subdomain:

```
nroute [global options]
├── twin
│   ├── validate         # Validate proposed change against safety policy (PASS/WARN/BLOCK)
│   ├── health           # Display digital twin network health summary
│   ├── impact           # Simulate configuration changes and blast radius
│   ├── rca              # Run Root-Cause Analysis on network events
│   ├── reachability     # Compute pairwise reachability matrices
│   └── audit            # Read and export NDJSON audit trail records
├── topology
│   ├── generate         # Generate synthetic network topologies
│   └── show             # Display topology structure and stats
├── route
│   └── compute          # Compute optimal routes between nodes (Dijkstra/ECMP)
├── simulate
│   ├── run              # Run discrete-event network routing simulations
│   └── compare          # Compare performance of multiple routing policies
├── api
│   └── start            # Launch the FastAPI REST server
├── config
│   └── init             # Generate a default configuration template
├── completion           # Generate shell completion setup scripts
├── train                # [Research] Train baseline ML/RL routing models
├── predict              # [Research] Predict congestion using trained models
└── detect               # [Research] Detect anomalies in network telemetry
```

---

## 🛡️ Pre-Flight Validation: `nroute twin validate`

The flagship pre-flight validation command performs deterministic what-if analysis and checks declarative safety gates before deploying network changes.

```bash
nroute twin validate [OPTIONS]
```

### Options:
| Flag | Short | Type | Description |
|---|---|---|---|
| `--topology` | `-t` | Path | **[Required]** Path to baseline topology JSON file. |
| `--change` | `-ch` | Path | **[Required]** Path to proposed change YAML/JSON file. |
| `--policy` | `-p` | Path | Path to safety policy YAML/JSON file. |
| `--config` | `-c` | Path | Optional device config to ingest before validation. |
| `--weight` | `-w` | Text | Edge weight attribute for path computation (`latency`, `weight`, `cost`). |
| `--output` | `-o` | Path | Write full validation report to JSON file. |
| `--json` | `-j` | Flag | Emit machine-readable JSON to stdout. |
| `--strict-warnings`| `-s` | Flag | Exit with code `2` on WARN verdicts in CI/CD pipelines. |

### Exit Codes:
- **`0`**: Validation **PASS** (or **WARN** when `--strict-warnings` is omitted).
- **`1`**: Validation **BLOCK** (one or more blocking safety rules violated).
- **`2`**: Validation **WARN** (when `--strict-warnings` is enabled) or CLI argument syntax error.
- **`64`**: CLI Parameter Error (invalid arguments or types).
- **`65`**: Input / Policy Ingestion Error (file not found or unparseable).
- **`70`**: Validation Execution Error (internal simulation convergence fault).

---

## ⚙️ Global Options

These options are applied at the root command level (before the subcommand group):

| Option | Flag | Type | Description |
|---|---|---|---|
| `--verbose` | `-v` | Flag | Enable debug level logging (`DEBUG`). |
| `--quiet` | `-q` | Flag | Suppress all logs except error logs (`ERROR`). |
| `--no-color` | | Flag | Disable ANSI colors in console outputs. |
| `--output-format` | `-f` | `text` \| `json` | Set output format (`text` is default, `json` formats command outputs as clean JSON). |
| `--config` | | Path | Explicit path to `nroute.yaml` configuration file. |
| `--seed` | | Integer | Set a global random seed for simulation/generation reproducibility. |

---

## 📡 Digital Twin API & Config subcommands

### `nroute api start`
Starts the FastAPI Digital Twin REST server.

Options:
- `--host TEXT` (Default: `127.0.0.1`): Bind IP address.
- `--port INTEGER` (Default: `8000`): Bind port.

### `nroute config init`
Initializes a default config file (`nroute.yaml`) in the current directory or specified path.

Options:
- `--output`, `-o PATH` (Default: `./nroute.yaml`): Target output path.

---

## 🛠️ Environment Variables

The CLI and underlying libraries respect the following environment variables:

| Variable | Value | Description |
|---|---|---|
| `NO_COLOR` | any (e.g. `1`) | Disables all color output (follows https://no-color.org). |
| `NROUTE_API_TOKEN` | string | Secret Bearer authentication token for securing REST API endpoints. |
| `NROUTE_CORS_ORIGINS` | Comma-separated list of origins | Hardens API CORS allowed origins (e.g., `http://localhost:3000,https://app.example.com`). Wildcards (`*`) and empty values are rejected for security. |
| `NROUTE_[SECTION]_[KEY]` | e.g. `NROUTE_GENERAL_LOG_LEVEL=DEBUG` | Overrides configuration options dynamically from the environment. |

---

## 🚪 Exit Codes Contract

The CLI conforms to standard POSIX exit status contracts for reliable automation in shell scripts and CI/CD pipelines:

| Exit Code | Classification | Meaning |
|---|---|---|
| **`0`** | `SUCCESS / PASS` | Command executed successfully or pre-flight change cleared all gates. |
| **`1`** | `APPLICATION_ERROR / BLOCK` | Application exception or pre-flight change violated blocking safety rules. |
| **`2`** | `USAGE_ERROR / WARN_STRICT` | Click CLI validation failed, or `--strict-warnings` tripped on a WARN verdict. |
| **`64`** | `PARAMETER_ERROR` | Malformed CLI arguments or parameter types. |
| **`65`** | `DATA_FORMAT_ERROR` | Unparseable topology, malformed change patch, or unreadable policy file. |
| **`70`** | `SOFTWARE_ERROR` | Internal simulation or validation execution failure. |

---

## ⌨️ Shell Auto-Completion

Auto-completion is supported natively for `bash`, `zsh`, and `fish` shells:

**Bash (`~/.bashrc`):**
```bash
eval "$(nroute completion bash)"
```

**Zsh (`~/.zshrc`):**
```zsh
eval "$(nroute completion zsh)"
```

**Fish (`~/.config/fish/config.fish`):**
```fish
nroute completion fish | source
```
