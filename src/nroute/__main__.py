"""Entry point for `python -m nroute`."""

from __future__ import annotations


def main() -> None:
    """Main entry point — delegates to CLI."""
    from nroute.cli.main import cli

    cli()


if __name__ == "__main__":
    main()
