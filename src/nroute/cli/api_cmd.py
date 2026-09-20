"""CLI commands for managing the Digital Twin API server."""

from __future__ import annotations

import click
import uvicorn
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group(name="api", help="Manage the Digital Twin API server.")
def api_cmd() -> None:
    """API Server Management Command Group."""
    pass


@api_cmd.command(name="start", help="Start the FastAPI API server.")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the server to.",
)
@click.option(
    "--port",
    default=8000,
    show_default=True,
    help="Port to bind the server to.",
)
def start_server(host: str, port: int) -> None:
    """Start the FastAPI API server using uvicorn."""
    from nroute.api.server import get_active_api_token

    token, is_fallback = get_active_api_token()
    console.print(
        f"[cyan]Starting Digital Twin API server on [bold]http://{host}:{port}[/bold]...[/cyan]\n"
    )
    if is_fallback:
        token_msg = (
            f"[bold yellow]INFO:[/bold yellow] No [bold]NROUTE_API_TOKEN[/bold] configured. "
            f"Generated local session token:\n\n"
            f"  [bold green]Bearer {token}[/bold green]\n\n"
            f"[dim]Include header 'Authorization: Bearer <token>' in API requests.[/dim]"
        )
        console.print(
            Panel(
                token_msg,
                title="[bold cyan]Digital Twin API Auth[/bold cyan]",
                border_style="cyan",
                expand=False,
            )
        )
    uvicorn.run("nroute.api.server:app", host=host, port=port, log_level="info")
