# PyPI Packaging & Publishing Guidelines — nroute

This document provides step-by-step instructions on how to build, validate, and publish the `nroute` package to the Python Package Index (PyPI).

---

## 1. Prerequisites

First, ensure you have the latest versions of Python's official packaging tools installed in your virtual environment:

```bash
pip install --upgrade build twine
```

---

## 2. Local Build Process

The `nroute` packaging configuration is defined in `pyproject.toml` utilizing `setuptools` as the build backend and featuring a `src/` layout.

To build the source distribution (`.tar.gz`) and binary wheel (`.whl`), execute Python's standard `build` compiler from the repository root:

```bash
python -m build
```

This command will output compiled packages into a newly created `dist/` directory:
```text
dist/
├── nroute-0.1.0-py3-none-any.whl
└── nroute-0.1.0.tar.gz
```

---

## 3. Package Validation & Verification

Before uploading packages to public repositories, verify that the package description renders correctly and the metadata conforms to PyPI specifications using `twine`:

```bash
twine check dist/*
```

Ensure the output displays:
```text
Checking dist/nroute-0.1.0-py3-none-any.whl: Passed
Checking dist/nroute-0.1.0.tar.gz: Passed
```

---

## 4. Publishing to TestPyPI

To ensure the package displays and installs correctly on a mock index without affecting the official index, upload to TestPyPI first:

```bash
twine upload --repository testpypi dist/*
```
*Note: This will prompt for your TestPyPI credentials (username `__token__` and your TestPyPI API token as the password).*

### Verify TestPyPI Installation
Test the package installation in a clean, separate environment:
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps nroute
```

---

## 5. Publishing to Official PyPI

Once local builds and TestPyPI distributions are fully verified, upload the release to official PyPI:

```bash
twine upload dist/*
```
*Note: This will prompt for your official PyPI API token credentials.*

---

## 6. CLI Verification

After publishing, install `nroute` and run:

```bash
pip install nroute
nroute --help
```
Ensure the ASCII banner and subcommands show up as expected.
