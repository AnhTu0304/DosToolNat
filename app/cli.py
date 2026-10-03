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
from app.scenarios.loader import list_scenarios, load_scenario
from app.scenarios.models import Scenario, ScenarioResult, ScenarioStage, StageResult
from app.scenarios.runner import ScenarioRunner
from app.reporting.recorder import build_experiment_result, ExperimentRecorder

app = typer.Typer(
    name="dos-tool",
    help="Controlled HTTP/DoS Testing Tool for authorized resilience testing.",
    no_args_is_help=True,
)
scenario_app = typer.Typer(
    name="scenario",
    help="Manage and execute multi-stage load testing scenarios.",
    no_args_is_help=True,
)
app.add_typer(scenario_app, name="scenario")

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
    console.print(f"[bold cyan]dos-tool[/bold cyan] version [bold green]{__version__}[/bold green] (Phase 4 - Metrics & Experiment Reporting)")


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
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        effective_timeout = timeout if timeout is not None else cfg.request_timeout

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


# ============================================================================
# Scenario Subcommands
# ============================================================================

@scenario_app.command(name="list", help="List available load test scenarios.")
def list_scenarios_cmd(
    scenarios_dir: Annotated[
        Path,
        typer.Option("--dir", help="Scenarios directory path.")
    ] = Path("scenarios"),
) -> None:
    """Discover and list all valid load testing scenarios."""
    scenarios = list_scenarios(scenarios_dir)
    if not scenarios:
        console.print("[yellow]No scenarios found in scenarios directory.[/yellow]")
        return

    console.print("\nAvailable Scenarios")
    console.print("-" * 32)
    for sc in scenarios:
        console.print(f"[bold cyan]{sc['name']}[/bold cyan]")
    console.print("")


@scenario_app.command(name="show", help="Display details of a specific scenario.")
def show_scenario_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Scenario name or YAML file path.")
    ],
    scenarios_dir: Annotated[
        Path,
        typer.Option("--dir", help="Scenarios directory path.")
    ] = Path("scenarios"),
) -> None:
    """Display the configuration, stages, and total duration of a scenario."""
    try:
        scenario = load_scenario(name, scenarios_dir=scenarios_dir)
        console.print("\nScenario")
        console.print("-" * 32)
        console.print(f"Name        : {scenario.name}")
        console.print(f"Description : {scenario.description}")
        console.print(f"Target      : {scenario.target}")
        console.print(f"Method      : {scenario.method}\n")
        console.print("Stages:\n")
        for idx, stg in enumerate(scenario.stages, start=1):
            rate_d = int(stg.rate) if float(stg.rate).is_integer() else stg.rate
            dur_d = int(stg.duration) if float(stg.duration).is_integer() else stg.duration
            console.print(f"{idx}. Rate={rate_d} req/s, Concurrency={stg.concurrency}, Duration={dur_d}s")

        total_d = int(scenario.total_duration) if float(scenario.total_duration).is_integer() else scenario.total_duration
        console.print(f"\nTotal Duration: {total_d}s\n")
    except FileNotFoundError as exc:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"\n[bold red]Error loading scenario:[/bold red] {exc}")
        raise typer.Exit(code=1)


@scenario_app.command(name="run", help="Execute a multi-stage scenario.")
def run_scenario_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Scenario name or YAML file path.")
    ],
    config_path: Annotated[
        Optional[Path],
        typer.Option("--config", help="Path to custom config YAML file.")
    ] = None,
    scenarios_dir: Annotated[
        Path,
        typer.Option("--dir", help="Scenarios directory path.")
    ] = Path("scenarios"),
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Base directory for experiment reports.")
    ] = Path("reports"),
    timeout: Annotated[
        Optional[float],
        typer.Option("--timeout", help="Custom request timeout in seconds.")
    ] = None,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug mode to show full tracebacks.")
    ] = False,
) -> None:
    """Execute all stages of a scenario sequentially with live progress and final summary."""
    try:
        cfg_file = config_path or (Path("configs/config.yaml") if Path("configs/config.yaml").exists() else None)
        cfg: AppConfig = load_config(cfg_file)
        setup_logging(cfg.log_level)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        effective_timeout = timeout if timeout is not None else cfg.request_timeout

        scenario = load_scenario(name, scenarios_dir=scenarios_dir)

        # Safety validation
        safety = SafetyController(cfg)
        safety.validate_scenario(scenario)

        header_line = "=" * 48
        stage_line = "-" * 48
        console.print("\nDOS TOOL - SCENARIO TEST")
        console.print(header_line + "\n")
        console.print(f"Scenario      : {scenario.name}")
        console.print(f"Description   : {scenario.description}")
        console.print(f"Target        : {scenario.target}")
        console.print(f"Method        : {scenario.method}\n")

        total_stages = len(scenario.stages)

        def on_stage_start(stage_idx: int, stage: ScenarioStage) -> None:
            console.print(header_line)
            console.print(f"Stage {stage_idx}/{total_stages}")
            console.print(stage_line)
            rate_disp = int(stage.rate) if float(stage.rate).is_integer() else stage.rate
            dur_disp = int(stage.duration) if float(stage.duration).is_integer() else stage.duration
            console.print(f"Rate          : {rate_disp} req/s")
            console.print(f"Concurrency   : {stage.concurrency}")
            console.print(f"Duration      : {dur_disp}s\n")

        def on_stage_complete(stage_idx: int, stage_res: StageResult) -> None:
            rep = stage_res.report
            console.print(f"Total Requests: {rep.total_requests}")
            console.print(f"Successful    : {rep.successful_requests}")
            console.print(f"Failed        : {rep.failed_requests}")
            console.print(f"P95           : {rep.p95_latency:.1f} ms")
            console.print(f"P99           : {rep.p99_latency:.1f} ms")
            console.print(f"Actual RPS    : {rep.actual_rate:.2f}\n")

        runner = ScenarioRunner(
            scenario=scenario,
            timeout=effective_timeout,
            on_stage_start=on_stage_start,
            on_stage_complete=on_stage_complete,
        )

        try:
            scenario_result: ScenarioResult = asyncio.run(runner.run())
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Scenario interrupted by user. Finalizing report...[/bold yellow]")
            runner.stop()
            scenario_result = asyncio.run(runner.run())

        # Display Final Scenario Summary
        console.print(header_line)
        console.print("SCENARIO RESULT")
        console.print(header_line + "\n")
        console.print(f"Scenario          : {scenario_result.scenario_name}")
        console.print(f"Target            : {scenario_result.target}")
        console.print(f"Total Duration    : {scenario_result.total_duration:.1f} s\n")
        console.print(f"Total Requests    : {scenario_result.total_requests}")
        console.print(f"Successful        : {scenario_result.total_successful}")
        console.print(f"Failed            : {scenario_result.total_failed}")
        console.print(f"Timeouts          : {scenario_result.total_timeouts}")
        console.print(f"Connection Errors : {scenario_result.total_connection_errors}\n")

        console.print(stage_line)
        console.print("STAGE SUMMARY")
        console.print(stage_line + "\n")

        summary_table = Table(show_header=True, header_style="bold magenta", box=None)
        summary_table.add_column("Stage", justify="right", style="cyan")
        summary_table.add_column("Rate", justify="right")
        summary_table.add_column("Concurrency", justify="right")
        summary_table.add_column("Requests", justify="right")
        summary_table.add_column("Success", justify="right", style="green")
        summary_table.add_column("Failed", justify="right", style="red")
        summary_table.add_column("P95", justify="right", style="yellow")
        summary_table.add_column("P99", justify="right", style="yellow")

        for s_res in scenario_result.stage_results:
            rep = s_res.report
            stg = s_res.stage
            rate_s = str(int(stg.rate) if float(stg.rate).is_integer() else stg.rate)
            summary_table.add_row(
                str(s_res.stage_index),
                rate_s,
                str(stg.concurrency),
                str(rep.total_requests),
                str(rep.successful_requests),
                str(rep.failed_requests),
                f"{rep.p95_latency:.1f} ms",
                f"{rep.p99_latency:.1f} ms",
            )

        console.print(summary_table)
        console.print("\n" + stage_line)
        console.print("EXPERIMENT REPORTS")
        console.print(stage_line + "\n")

        # Phase 4 - Save Experiment Reports
        recorder = ExperimentRecorder(output_base_dir=output_dir)
        cfg_dict = {
            "timeout": effective_timeout,
            "max_rate": cfg.max_request_rate,
            "max_concurrency": cfg.max_concurrency,
            "max_duration": cfg.max_test_duration,
        }
        exp_result = build_experiment_result(
            scenario=scenario,
            scenario_result=scenario_result,
            config=cfg_dict,
        )
        saved_dir = recorder.record(exp_result)

        console.print(f"Reports Directory : [cyan]{saved_dir}[/cyan]")
        console.print(f"JSON Report       : {saved_dir / 'experiment.json'}")
        console.print(f"Stages CSV        : {saved_dir / 'stages.csv'}")
        console.print(f"Latency CSV       : {saved_dir / 'latency.csv'}")
        console.print(f"HTML Report       : [bold green]{saved_dir / 'report.html'}[/bold green]\n")
        console.print(header_line + "\n")

        raise typer.Exit(code=0)

    except FileNotFoundError as exc:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
        if debug:
            raise
        raise typer.Exit(code=1)
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
