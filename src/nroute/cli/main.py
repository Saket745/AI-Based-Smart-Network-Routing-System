"""nroute CLI — root command group.

Re-exports the main CLI entrypoint for use by setuptools console_scripts
and `python -m nroute`.
"""

from __future__ import annotations

from nroute.cli import cli

__all__ = ["cli"]
