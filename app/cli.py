"""Command Line Interface for dos-tool using Typer and Rich."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from app import __version__
from app.config import AppConfig, load_config
from app.engine.runner import ConnectivityRunner, ConnectivityResult, LoadTestRunner
from app.metrics.models import LoadTestReport
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
    console.print(f"[bold cyan]dos-tool[/bold cyan] version [bold green]{__version__}[/bold green] (Phase 2 - Controlled HTTP Load Engine)")


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

        safety = SafetyController(cfg)
        validated_target = safety.validate_target_url(target)
        safety.validate_limits(timeout=effective_timeout)

        logger.info("Starting connectivity test")
        logger.info("Target: %s", validated_target)

        runner = ConnectivityRunner(timeout=effective_timeout)
        result: ConnectivityResult = runner.test_connectivity(validated_target)

        if result.status_code is not None:
            logger.info("Response status: %s", result.status_code)
            logger.info("Latency: %sms", int(result.latency_ms))

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


@app.command(name="load", help="Execute a controlled HTTP load test against an authorized target.")
def load(
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="Target URL (e.g., http://localhost:3000)")
    ],
    rate: Annotated[
        float,
        typer.Option("--rate", "-r", help="Target request rate (requests per second).")
    ] = 10.0,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", "-c", help="Maximum concurrent requests.")
    ] = 5,
    duration: Annotated[
        float,
        typer.Option("--duration", "-d", help="Test duration in seconds.")
    ] = 10.0,
    timeout: Annotated[
        Optional[float],
        typer.Option("--timeout", help="Request timeout in seconds.")
    ] = None,
    config_path: Annotated[
        Optional[Path],
        typer.Option("--config", help="Path to custom config YAML file.")
    ] = None,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug mode to show full tracebacks.")
    ] = False,
) -> None:
    """Execute a controlled async HTTP GET load test with real-time telemetry."""
    try:
        cfg_file = config_path or (Path("configs/config.yaml") if Path("configs/config.yaml").exists() else None)
        cfg: AppConfig = load_config(cfg_file)
        setup_logging(cfg.log_level)
        # Suppress individual request logs from httpx during high-volume load test
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        effective_timeout = timeout if timeout is not None else cfg.request_timeout

        # Safety Controller Validation
        safety = SafetyController(cfg)
        validated_target = safety.validate_target_url(target)
        safety.validate_load_parameters(
            rate=rate,
            concurrency=concurrency,
            duration=duration,
            timeout=effective_timeout,
        )

        logger.info("Load test started for target: %s", validated_target)
        logger.info("Configuration: rate=%.1f req/s, concurrency=%d, duration=%.1fs, timeout=%.1fs", rate, concurrency, duration, effective_timeout)

        header_line = "-" * 40
        console.print("\nDOS TOOL - CONTROLLED LOAD TEST")
        console.print(header_line)
        console.print(f"Target       : {validated_target}")
        console.print("Method       : GET")
        duration_disp = int(duration) if float(duration).is_integer() else duration
        rate_disp = int(rate) if float(rate).is_integer() else rate
        console.print(f"Duration     : {duration_disp} s")
        console.print(f"Target Rate  : {rate_disp} req/s")
        console.print(f"Concurrency  : {concurrency}")
        console.print(header_line)
        console.print("\nRunning...\n")

        latest_progress = {"text": "Initializing..."}

        def on_progress(stats: dict, elapsed: float) -> None:
            latest_progress["text"] = (
                f"Progress:\n"
                f"Requests     : {stats['total']}\n"
                f"Successful   : {stats['success']}\n"
                f"Failed       : {stats['failed']}\n"
                f"Current RPS  : {stats['rps']}\n"
                f"Elapsed      : {elapsed:.1f} s"
            )

        runner = LoadTestRunner(
            target_url=validated_target,
            rate=rate,
            concurrency=concurrency,
            duration=duration,
            timeout=effective_timeout,
            on_progress=on_progress,
        )

        async def execute_load():
            return await runner.run()

        try:
            report: LoadTestReport = asyncio.run(execute_load())
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Test interrupted by user. Finalizing report...[/bold yellow]")
            runner.stop()
            report = asyncio.run(execute_load())

        # Display Final Summary
        console.print("\n" + header_line)
        console.print("LOAD TEST RESULT")
        console.print(header_line)
        console.print(f"Total Requests : {report.total_requests}")
        console.print(f"Successful     : {report.successful_requests}")
        console.print(f"Failed         : {report.failed_requests}\n")

        console.print(f"HTTP 2xx       : {report.status_2xx}")
        console.print(f"HTTP 3xx       : {report.status_3xx}")
        console.print(f"HTTP 4xx       : {report.status_4xx}")
        console.print(f"HTTP 5xx       : {report.status_5xx}\n")

        console.print(f"Timeouts       : {report.timeouts}")
        console.print(f"Connection Err : {report.connection_errors}\n")

        console.print(f"Average Latency: {report.average_latency:.2f} ms")
        console.print(f"Min Latency    : {report.min_latency:.2f} ms")
        console.print(f"Max Latency    : {report.max_latency:.2f} ms")
        console.print(f"P50 Latency    : {report.p50_latency:.2f} ms")
        console.print(f"P95 Latency    : {report.p95_latency:.2f} ms")
        console.print(f"P99 Latency    : {report.p99_latency:.2f} ms\n")

        console.print(f"Average RPS    : {report.actual_rate:.2f}")
        console.print(f"Target RPS     : {report.requested_rate:.2f}\n")

        console.print(f"Test Duration  : {report.elapsed_time:.2f} s")
        console.print(header_line)

        raise typer.Exit(code=0)

    except SafetyValidationError as exc:
        console.print(f"\n[bold red]{exc}[/bold red]")
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
