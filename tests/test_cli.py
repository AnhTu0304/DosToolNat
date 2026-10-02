"""Tests for Typer CLI interface."""

from unittest.mock import patch
from typer.testing import CliRunner
from app.cli import app
from app.engine.runner import ConnectivityResult

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
    """Verify dos-tool version returns 0.1.0."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


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
