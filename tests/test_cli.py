"""Tests for Typer CLI interface."""

from unittest.mock import patch
from typer.testing import CliRunner
from app.cli import app
from app.engine.runner import ConnectivityResult
from app.metrics.models import LoadTestReport

runner = CliRunner()


def test_cli_help():
    """Verify dos-tool --help returns status 0 and displays commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dos-tool" in result.output.lower() or "usage" in result.output.lower()
    assert "test" in result.output
    assert "config" in result.output
    assert "version" in result.output


def test_cli_version():
    """Verify dos-tool version returns 0.5.0."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.5.0" in result.output


def test_cli_config_default():
    """Verify dos-tool config displays current configuration."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "target_url" in result.output
    assert "request_timeout" in result.output


def test_cli_test_invalid_url():
    """Verify dos-tool test with invalid URL exits with code 1 and clean error message."""
    result = runner.invoke(app, ["test", "--target", "invalid_url"])
    assert result.exit_code == 1
    assert "error" in result.output.lower() or "missing" in result.output.lower()
    assert "Traceback" not in result.output


def test_cli_test_success_mocked():
    """Verify dos-tool test with mocked successful connectivity."""
    mock_result = ConnectivityResult(
        target="http://localhost:8000",
        method="GET",
        status_code=200,
        latency_ms=42.0,
        success=True,
        error_message=None,
    )

    with patch("app.cli.ConnectivityRunner.test_connectivity", return_value=mock_result):
        result = runner.invoke(app, ["test", "--target", "http://localhost:8000"])
        assert result.exit_code == 0
        assert "DOS TOOL" in result.output
        assert "200" in result.output
        assert "SUCCESS" in result.output
        assert "42" in result.output


def test_cli_test_failure_mocked():
    """Verify dos-tool test with mocked failed connectivity."""
    mock_result = ConnectivityResult(
        target="http://localhost:8000",
        method="GET",
        status_code=None,
        latency_ms=15.0,
        success=False,
        error_message="Connection refused",
    )

    with patch("app.cli.ConnectivityRunner.test_connectivity", return_value=mock_result):
        result = runner.invoke(app, ["test", "--target", "http://localhost:8000"])
        assert result.exit_code == 1
        assert "DOS TOOL" in result.output
        assert "FAILED" in result.output
        assert "Connection refused" in result.output


def test_cli_load_help():
    """Verify dos-tool load --help displays arguments and exits 0."""
    result = runner.invoke(app, ["load", "--help"])
    assert result.exit_code == 0
    assert "--target" in result.output
    assert "--rate" in result.output
    assert "--concurrency" in result.output
    assert "--duration" in result.output
    assert "--timeout" in result.output


def test_cli_load_safety_rejection():
    """Verify dos-tool load rejects out-of-boundary parameters before execution."""
    result = runner.invoke(
        app,
        [
            "load",
            "--target", "http://localhost:3000",
            "--rate", "1000",
            "--concurrency", "100",
            "--duration", "120",
        ],
    )
    assert result.exit_code == 1
    assert "Safety validation failed" in result.output
    assert "Requested rate: 1000 req/s" in result.output
    assert "Maximum allowed: 100 req/s" in result.output
    assert "Traceback" not in result.output


def test_cli_load_success_mocked():
    """Verify dos-tool load runs and displays structured summary."""
    mock_report = LoadTestReport(
        target="http://localhost:3000",
        method="GET",
        requested_rate=10.0,
        actual_rate=10.0,
        concurrency=5,
        duration=20.0,
        total_requests=200,
        successful_requests=200,
        failed_requests=0,
        status_2xx=200,
        status_3xx=0,
        status_4xx=0,
        status_5xx=0,
        timeouts=0,
        connection_errors=0,
        min_latency=12.10,
        max_latency=95.42,
        average_latency=42.31,
        p50_latency=38.21,
        p95_latency=72.55,
        p99_latency=91.32,
        start_time=100.0,
        end_time=120.01,
        elapsed_time=20.01,
    )

    with patch("app.cli.LoadTestRunner.run", return_value=mock_report):
        result = runner.invoke(
            app,
            [
                "load",
                "--target", "http://localhost:3000",
                "--rate", "10",
                "--concurrency", "5",
                "--duration", "20",
            ],
        )
        assert result.exit_code == 0
        assert "DOS TOOL - CONTROLLED LOAD TEST" in result.output
        assert "LOAD TEST RESULT" in result.output
        assert "Total Requests : 200" in result.output
        assert "HTTP 2xx       : 200" in result.output
        assert "P50 Latency    : 38.21 ms" in result.output
        assert "P99 Latency    : 91.32 ms" in result.output


def test_cli_scenario_help():
    """Verify dos-tool scenario --help displays commands and exits 0."""
    result = runner.invoke(app, ["scenario", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "show" in result.output
    assert "run" in result.output


def test_cli_scenario_list():
    """Verify dos-tool scenario list displays discovered scenarios."""
    result = runner.invoke(app, ["scenario", "list"])
    assert result.exit_code == 0
    assert "ecommerce_product_ramp" in result.output
    assert "frontend_load" in result.output


def test_cli_scenario_show():
    """Verify dos-tool scenario show displays scenario details without running."""
    result = runner.invoke(app, ["scenario", "show", "ecommerce_product_ramp"])
    assert result.exit_code == 0
    assert "ecommerce_product_ramp" in result.output
    assert "http://localhost:5000/api/products" in result.output
    assert "Stages:" in result.output
    assert "Total Duration" in result.output


def test_cli_scenario_show_not_found():
    """Verify dos-tool scenario show displays error for non-existent scenario."""
    result = runner.invoke(app, ["scenario", "show", "non_existent_xyz"])
    assert result.exit_code == 1
    assert "Scenario not found" in result.output
    assert "Traceback" not in result.output


def test_cli_scenario_run_generates_reports(tmp_path):
    """Verify dos-tool scenario run executes and saves experiment reports."""
    from app.scenarios.models import ScenarioStage, StageResult, ScenarioResult
    from app.metrics.models import RequestResult

    req = RequestResult(timestamp=100.0, status_code=200, latency_ms=15.0, success=True)
    mock_stage_report = LoadTestReport(
        target="http://localhost:3000",
        method="GET",
        requested_rate=2.0,
        actual_rate=2.0,
        concurrency=1,
        duration=10.0,
        total_requests=1,
        successful_requests=1,
        failed_requests=0,
        status_2xx=1,
        min_latency=15.0,
        max_latency=15.0,
        average_latency=15.0,
        p50_latency=15.0,
        p95_latency=15.0,
        p99_latency=15.0,
        start_time=100.0,
        end_time=110.0,
        elapsed_time=10.0,
        results=[req],
    )
    stg = ScenarioStage(rate=2, concurrency=1, duration=10)
    stage_res = StageResult(stage_index=1, stage=stg, report=mock_stage_report)
    mock_scenario_result = ScenarioResult(
        scenario_name="frontend_load",
        target="http://localhost:3000",
        total_duration=10.0,
        stage_results=[stage_res],
        total_requests=1,
        total_successful=1,
        total_failed=0,
        total_timeouts=0,
        total_connection_errors=0,
    )

    with patch("app.cli.ScenarioRunner.run", return_value=mock_scenario_result):
        result = runner.invoke(
            app,
            ["scenario", "run", "frontend_load", "--output", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "EXPERIMENT REPORTS" in result.output
        assert "experiment.json" in result.output
        assert "report.html" in result.output

        # Verify files on disk
        scenario_output_dirs = list((tmp_path / "frontend_load").glob("*"))
        assert len(scenario_output_dirs) == 1
        exp_dir = scenario_output_dirs[0]
        assert (exp_dir / "experiment.json").is_file()
        assert (exp_dir / "stages.csv").is_file()
        assert (exp_dir / "latency.csv").is_file()
        assert (exp_dir / "report.html").is_file()


def test_cli_incident_help():
    """Verify dos-tool incident --help displays commands and exits 0."""
    result = runner.invoke(app, ["incident", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "show" in result.output
    assert "run" in result.output


def test_cli_incident_list():
    """Verify dos-tool incident list displays available incident scenarios."""
    result = runner.invoke(app, ["incident", "list"])
    assert result.exit_code == 0
    assert "incident_latency" in result.output
    assert "incident_http_5xx" in result.output
    assert "incident_combined" in result.output


def test_cli_incident_show():
    """Verify dos-tool incident show displays incident phases and criteria."""
    result = runner.invoke(app, ["incident", "show", "incident_latency"])
    assert result.exit_code == 0
    assert "incident_latency" in result.output
    assert "Baseline" in result.output
    assert "Fault" in result.output
    assert "Recovery" in result.output


def test_cli_incident_run_mocked(tmp_path):
    """Verify dos-tool incident run executes and saves all 6 reports."""
    from app.incidents.models import (
        IncidentResult,
        IncidentLifecycleState,
        PhaseMetricsSummary,
        FaultExecutionRecord,
        RecoveryExecutionRecord,
        TimelineEvent,
    )

    mock_res = IncidentResult(
        experiment_id="20261003_120000_incident_latency",
        scenario_name="incident_latency",
        target="http://localhost:3000",
        start_time="2026-10-03T12:00:00Z",
        end_time="2026-10-03T12:00:10Z",
        total_duration_seconds=10.0,
        lifecycle_state=IncidentLifecycleState.COMPLETED,
        before_metrics=PhaseMetricsSummary(total_requests=10, successful=10, average_rps=5.0),
        during_metrics=PhaseMetricsSummary(total_requests=20, successful=15, failed=5, average_rps=5.0),
        after_metrics=PhaseMetricsSummary(total_requests=10, successful=10, average_rps=5.0),
        fault=FaultExecutionRecord(fault_type="latency", duration_seconds=5.0, status="completed"),
        recovery=RecoveryExecutionRecord(status="recovered", recovery_duration_seconds=2.0),
        timeline=[
            TimelineEvent(timestamp="2026-10-03T12:00:00Z", event="experiment_started", phase="init"),
            TimelineEvent(timestamp="2026-10-03T12:00:10Z", event="experiment_completed", phase="completed"),
        ],
    )

    with patch("app.cli.IncidentRunner.run", return_value=mock_res):
        result = runner.invoke(
            app,
            ["incident", "run", "incident_latency", "--output", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "CONTROLLED INCIDENT INJECTION" in result.output
        assert "COMPARATIVE METRICS" in result.output
        assert "Faults CSV" in result.output
        assert "Timeline CSV" in result.output

        # Verify disk outputs
        inc_dirs = list((tmp_path / "incident_latency").glob("*"))
        assert len(inc_dirs) == 1
        exp_dir = inc_dirs[0]
        assert (exp_dir / "experiment.json").is_file()
        assert (exp_dir / "stages.csv").is_file()
        assert (exp_dir / "latency.csv").is_file()
        assert (exp_dir / "faults.csv").is_file()
        assert (exp_dir / "timeline.csv").is_file()
        assert (exp_dir / "report.html").is_file()



