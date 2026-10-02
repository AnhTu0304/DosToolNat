"""Command Line Interface for dos-tool using Typer and Rich."""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from app import __version__
from app.config import AppConfig, load_config
from app.engine.runner import ConnectivityRunner, ConnectivityResult
from app.safety.controller import SafetyController, SafetyValidationError

app = typer.Typer(
    name="dos-tool",
    help="Controlled HTTP/DoS Testing Tool for authorized resilience testing.",
    no_args_is_help=True,
)
console = Console()
logger = logging.getLogger("dos-tool")


def setup_logging(log_level: str) -> None:
    """Configure secure, clean console logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(levelname)s - %(message)s",
        force=True,
    )


@app.command(name="version", help="Show dos-tool version.")
def version() -> None:
    """Display application version and current phase."""
    console.print(f"[bold cyan]dos-tool[/bold cyan] version [bold green]{__version__}[/bold green] (Phase 1 - Foundation)")


@app.command(name="config", help="Display application configuration.")
def show_config(
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Path to custom config YAML file.")
    ] = None
) -> None:
    """Display active configuration and safety limits."""
    try:
        config_path = path or (Path("configs/config.yaml") if Path("configs/config.yaml").exists() else None)
        cfg: AppConfig = load_config(config_path)

        table = Table(title="dos-tool Configuration & Safety Limits", show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Description", style="dim")

        table.add_row("target_url", str(cfg.target_url), "Default target URL")
        table.add_row("request_timeout", f"{cfg.request_timeout}s", "Request timeout in seconds")
        table.add_row("max_test_duration", f"{cfg.max_test_duration}s", "Safety limit: maximum test duration")
        table.add_row("max_request_rate", f"{cfg.max_request_rate} req/s", "Safety limit: maximum requests/sec")
        table.add_row("max_concurrency", str(cfg.max_concurrency), "Safety limit: maximum concurrency")
        table.add_row("log_level", cfg.log_level, "Console log level")

        console.print(table)
    except Exception as exc:
        console.print(f"[bold red]Error loading configuration:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command(name="test", help="Perform a basic HTTP connectivity test (single request).")
def test(
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target URL (e.g., http://localhost:8000)")
    ],
    timeout: Annotated[
        Optional[float],
        typer.Option("--timeout", help="Custom request timeout in seconds.")
    ] = None,
    config_path: Annotated[
        Optional[Path],
        typer.Option("--config", "-c", help="Path to custom config YAML file.")
    ] = None,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug mode to show full tracebacks.")
    ] = False,
) -> None:
    """Execute a single safe HTTP GET request to verify connectivity."""
    try:
        cfg_file = config_path or (Path("configs/config.yaml") if Path("configs/config.yaml").exists() else None)
        cfg: AppConfig = load_config(cfg_file)
        setup_logging(cfg.log_level)

        effective_timeout = timeout if timeout is not None else cfg.request_timeout

        # Safety Controller Validation
        safety = SafetyController(cfg)
        validated_target = safety.validate_target_url(target)
        safety.validate_limits(timeout=effective_timeout)

        logger.info("Starting connectivity test")
        logger.info("Target: %s", validated_target)

        # Single HTTP GET request execution
        runner = ConnectivityRunner(timeout=effective_timeout)
        result: ConnectivityResult = runner.test_connectivity(validated_target)

        if result.status_code is not None:
            logger.info("Response status: %s", result.status_code)
            logger.info("Latency: %sms", int(result.latency_ms))

        # Format Terminal Output
        status_display = str(result.status_code) if result.status_code is not None else "N/A"
        latency_display = f"{result.latency_ms:.0f} ms"

        if result.success and (result.status_code is not None and result.status_code < 400):
            result_display = "[bold green]SUCCESS[/bold green]"
        elif result.success and (result.status_code is not None and result.status_code >= 400):
            result_display = f"[bold yellow]HTTP {result.status_code}[/bold yellow]"
        else:
            err_msg = result.error_message or "Unknown failure"
            result_display = f"[bold red]FAILED[/bold red] ({err_msg})"

        line = "-" * 30
        console.print("\nDOS TOOL")
        console.print(line)
        console.print(f"Target      : {result.target}")
        console.print(f"Method      : {result.method}")
        console.print(f"Status      : {status_display}")
        console.print(f"Latency     : {latency_display}")
        console.print(f"Result      : {result_display}")
        console.print(line)

        if not result.success:
            raise typer.Exit(code=1)

    except SafetyValidationError as exc:
        console.print(f"\n[bold red]Safety Error:[/bold red] {exc}")
        if debug:
            raise
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"\n[bold red]Unexpected Error:[/bold red] {exc}")
        if debug:
            raise
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
