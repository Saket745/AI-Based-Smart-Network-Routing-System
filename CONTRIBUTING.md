# Contributing Guidelines

Thank you for contributing to the AI-Based Smart Network Routing System! This document describes our development standards, branch governance, and setup procedures.

---

## 🌿 Branching Strategy

We follow a structured trunk-based development workflow:

* **`main`**: Production-ready, stable releases only. Direct commits are blocked; integration is strictly via approved Pull Requests.
* **`dev`**: Integration branch for active feature development. Must maintain passing tests at all times.
* **Supporting Branches**: Create short-lived branches off `dev` using these naming conventions:
  - `feature/*` — New functionality
  - `bugfix/*` — Defect resolution
  - `refactor/*` — Architectural improvements
  - `docs/*` — Documentation changes
  - `experiment/*` — Explanatory or prototype research
  - `test/*` — Adding or modifying tests

---

## 📝 Commit Standards

We enforce the **Conventional Commits** specification. Commit messages are checked automatically when committing locally and on CI pull requests.

### Commit Header Format
```text
<type>(<scope>)<optional !>: <description>
```

- **Allowed Types**:
  - `feat`: A new feature
  - `fix`: A bug fix
  - `docs`: Documentation changes
  - `style`: Changes that do not affect the meaning of the code (formatting)
  - `refactor`: A code change that neither fixes a bug nor adds a feature
  - `perf`: A code change that improves performance
  - `test`: Adding missing tests or correcting existing tests
  - `build`: Changes that affect the build system or external dependencies
  - `ci`: Changes to CI configuration files and scripts
  - `chore`: Other changes that don't modify src or test files
- **Scope**: (Optional) Indicates the specific module or file concerned (e.g. `routing`, `topology`, `simulation`).
- **Description**: Concise, lowercase description of the change.

### Examples
* `feat(routing): implement ECMP multipath distribution`
* `fix(simulation): resolve division by zero in packet transmission`
* `docs(readme): add docker deployment instructions`

---

## 🛠️ Local Development Setup

Follow these steps to set up your environment:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Saket745/AI-Based-Smart-Network-Routing-System.git
   cd AI-Based-Smart-Network-Routing-System
   ```

2. **Set Up a Virtual Environment & Install Dependencies:**
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Unix/macOS:
   source .venv/bin/activate

   pip install -e ".[dev]"
   ```

3. **Install Pre-Commit Hooks:**
   We use `pre-commit` to validate code formatting, types, repository structure, and commit messages before they are finalized.
   ```bash
   pre-commit install --hook-type pre-commit --hook-type commit-msg
   ```

4. **Verify Your Setup:**
   Run the test suite:
   ```bash
   pytest tests/ -v
   ```

---

## 🛡️ Pull Request Quality Gates

Before submitting a Pull Request (PR) from your feature branch to `dev` or `main`, ensure that:
* Code formatting complies with Ruff (`ruff check src/ tests/` and `ruff format --check src/ tests/`).
* MyPy static type check passes with no errors (`mypy src/nroute --strict`).
* All unit tests pass (`pytest tests/`).
* The repository placement validator (`python scripts/validate_repository.py`) reports no violations.
* Pull Requests require at least one code review approval and passing CI status checks.
