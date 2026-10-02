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
    """Verify dos-tool version returns 0.2.0."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


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
