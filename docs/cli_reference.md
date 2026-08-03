# ⌨️ CLI Reference Guide

The `nroute` CLI provides a unified, production-grade interface to manage, simulate, optimize, and diagnose network routing topologies using deterministic algorithms and machine learning models.

---

## 🚀 CLI Hierarchy & Subcommand Groups

The CLI is structured into several command groups, each focused on a specific subdomain:

```
nroute [global options]
├── topology
│   ├── generate         # Generate synthetic network topologies
│   └── show             # Display topology structure and stats
├── route
│   └── compute          # Compute optimal routes between nodes
├── simulate
│   ├── run              # Run discrete-event network routing simulations
│   └── compare          # Compare performance of multiple routing policies
├── train
│   ├── congestion       # Train congestion prediction models
│   ├── anomaly          # Train traffic anomaly detection models
│   └── gnn              # Train GNN baseline routing models
├── predict
│   ├── congestion       # Predict link congestion probabilities
│   └── gnn              # Predict congestion and latency with GNN
├── detect
│   └── anomalies        # Detect anomalies in live traffic features
├── twin
│   ├── health           # Display digital twin network health summary
│   ├── impact           # Simulate configuration changes and blast radius
│   ├── rca              # Run Root-Cause Analysis on network events
│   ├── reachability     # Compute pairwise reachability matrices
│   └── audit            # Read and export NDJSON audit trail records
├── api
│   └── start            # Launch the FastAPI REST server
├── config
│   └── init             # Generate a default configuration template
└── completion           # Generate shell completion setup scripts
```

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
| `NROUTE_CORS_ORIGINS` | Comma-separated list of origins | Hardens API CORS allowed origins (e.g., `http://localhost:3000,https://app.example.com`). Wildcards (`*`) and empty values are rejected for security. |
| `NROUTE_[SECTION]_[KEY]` | e.g. `NROUTE_GENERAL_LOG_LEVEL=DEBUG` | Overrides configuration options dynamically from the environment. |

---

## 🚪 Exit Codes Contract

The CLI conforms to standard POSIX exit status contracts for reliable automation in shell scripts and CI/CD pipelines:

| Exit Code | Classification | Meaning |
|---|---|---|
| **`0`** | `SUCCESS` | Command executed successfully and finished without errors. |
| **`1`** | `APPLICATION_ERROR` | An application-level exception occurred (e.g., `ConfigError`, `TopologyError`, `RoutingError`, `ModelError`, file missing, simulation convergence failure). |
| **`2`** | `USAGE_ERROR` | Click CLI validation failed (e.g., missing required options, unrecognized subcommands, or invalid parameter choices). |

---

## ⌨️ Shell Auto-Completion

Auto-completion is supported natively for `bash`, `zsh`, and `fish` shells.

### Quick Setup

Add the completion setup script directly to your shell profile configuration:

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
