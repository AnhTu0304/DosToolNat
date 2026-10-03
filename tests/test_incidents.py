"""Comprehensive unit tests for Phase 5 Controlled Fault & Incident Injection."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import httpx
import pytest

from app.incidents.models import (
    FaultType,
    FaultConfig,
    RecoveryCriteria,
    RecoveryConfig,
    IncidentLifecycleState,
    TimelineEvent,
    IncidentScenario,
    IncidentResult,
)
from app.incidents.fault_controller import HeaderFaultController
from app.incidents.recovery_detector import RecoveryDetector
from app.incidents.runner import IncidentRunner
from app.scenarios.models import ScenarioStage


# 1. Model & Validation Tests
def test_valid_fault_configs():
    """Verify valid latency, http_5xx, and combined configurations."""
    cfg_lat = FaultConfig(type=FaultType.LATENCY, delay_ms=300.0, duration=10.0)
    assert cfg_lat.delay_ms == 300.0
    assert cfg_lat.duration == 10.0

    cfg_5xx = FaultConfig(type=FaultType.HTTP_5XX, error_rate=0.25, duration=15.0)
    assert cfg_5xx.error_rate == 0.25

    cfg_comb = FaultConfig(
        type=FaultType.COMBINED,
        delay_ms=200.0,
        error_rate=0.10,
        duration=20.0,
    )
    assert cfg_comb.delay_ms == 200.0
    assert cfg_comb.error_rate == 0.10


def test_invalid_fault_configs():
    """Verify safety validations reject negative delays, out-of-bounds error rates, and zero duration."""
    with pytest.raises(ValueError):
        FaultConfig(type=FaultType.LATENCY, delay_ms=-50.0, duration=10.0)

    with pytest.raises(ValueError):
        FaultConfig(type=FaultType.LATENCY, delay_ms=100.0, duration=0.0)

    with pytest.raises(ValueError):
        FaultConfig(type=FaultType.HTTP_5XX, error_rate=-0.1, duration=10.0)

    with pytest.raises(ValueError):
        FaultConfig(type=FaultType.HTTP_5XX, error_rate=1.5, duration=10.0)

    with pytest.raises(ValueError):
        # Latency fault without delay_ms
        FaultConfig(type=FaultType.LATENCY, duration=10.0)

    with pytest.raises(ValueError):
        # 5xx fault without error_rate
        FaultConfig(type=FaultType.HTTP_5XX, duration=10.0)


def test_recovery_criteria_validation():
    """Verify recovery criteria constraints."""
    crit = RecoveryCriteria(max_p95_ms=50.0, max_error_rate=0.01, consecutive_healthy_samples=3)
    rec_cfg = RecoveryConfig(enabled=True, criteria=crit, timeout=15.0)
    assert rec_cfg.timeout == 15.0
    assert rec_cfg.criteria.consecutive_healthy_samples == 3

    with pytest.raises(ValueError):
        RecoveryCriteria(max_p95_ms=-10.0)

    with pytest.raises(ValueError):
        RecoveryCriteria(max_error_rate=1.5)

    with pytest.raises(ValueError):
        RecoveryCriteria(consecutive_healthy_samples=0)

    with pytest.raises(ValueError):
        RecoveryConfig(timeout=-5.0)


def test_incident_scenario_total_duration_safety():
    """Verify IncidentScenario enforces total test duration <= 60 seconds."""
    baseline = ScenarioStage(rate=5, concurrency=2, duration=20)
    fault = FaultConfig(type=FaultType.LATENCY, delay_ms=300, duration=30)
    recovery = RecoveryConfig(timeout=20)  # 20 + 30 + 20 = 70s > 60s max

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        IncidentScenario(
            name="too_long_incident",
            target="http://localhost:3000",
            baseline=baseline,
            fault=fault,
            recovery=recovery,
        )


# 2. Recovery Detector Tests
def test_recovery_detector_success():
    """Verify RecoveryDetector signals recovered after consecutive healthy evaluations."""
    crit = RecoveryCriteria(max_p95_ms=50.0, max_error_rate=0.05, consecutive_healthy_samples=3)
    detector = RecoveryDetector(crit, timeout=10.0)

    # 1st healthy evaluation
    assert detector.evaluate(p95_ms=40.0, error_rate=0.0) is False
    assert detector.status == "monitoring"

    # 2nd healthy evaluation
    assert detector.evaluate(p95_ms=45.0, error_rate=0.02) is False

    # 3rd healthy evaluation -> triggers RECOVERED
    assert detector.evaluate(p95_ms=30.0, error_rate=0.0) is True
    assert detector.status == "recovered"


def test_recovery_detector_resets_on_unhealthy_sample():
    """Verify consecutive healthy counter resets if an unhealthy evaluation occurs."""
    crit = RecoveryCriteria(max_p95_ms=50.0, max_error_rate=0.05, consecutive_healthy_samples=2)
    detector = RecoveryDetector(crit, timeout=10.0)

    assert detector.evaluate(p95_ms=40.0, error_rate=0.0) is False
    # Spike breaks the streak
    assert detector.evaluate(p95_ms=120.0, error_rate=0.0) is False
    # Start streak again
    assert detector.evaluate(p95_ms=35.0, error_rate=0.0) is False
    # 2nd consecutive
    assert detector.evaluate(p95_ms=30.0, error_rate=0.0) is True
    assert detector.status == "recovered"


def test_recovery_detector_timeout():
    """Verify detector records timeout if criteria are not met within timeout."""
    crit = RecoveryCriteria(max_p95_ms=50.0, max_error_rate=0.05, consecutive_healthy_samples=3)
    detector = RecoveryDetector(crit, timeout=5.0)

    detector.record_timeout()
    assert detector.status == "recovery_timeout"


# 3. Fault Controller Tests
@pytest.mark.anyio
async def test_header_fault_controller_lifecycle():
    """Verify FaultController activate, status, headers, and deactivate lifecycle."""
    cfg = FaultConfig(type=FaultType.LATENCY, delay_ms=300.0, duration=10.0)
    controller = HeaderFaultController(cfg)

    assert controller.is_active is False
    headers_before = controller.get_request_headers()
    assert "X-Test-Fault-Type" not in headers_before

    await controller.activate()
    assert controller.is_active is True
    headers_active = controller.get_request_headers()
    assert headers_active.get("X-Test-Fault-Type") == "latency"
    assert headers_active.get("X-Test-Fault-Delay-Ms") == "300.0"

    await controller.deactivate()
    assert controller.is_active is False
    headers_after = controller.get_request_headers()
    assert "X-Test-Fault-Type" not in headers_after


# 4. Incident Runner Execution & Orchestration
@pytest.mark.anyio
async def test_incident_runner_full_lifecycle():
    """Verify IncidentRunner completes baseline, fault injection, recovery, and builds IncidentResult."""
    scenario = IncidentScenario(
        name="test_quick_incident",
        description="Quick test incident for unit testing",
        target="http://localhost:3000",
        baseline=ScenarioStage(rate=2, concurrency=1, duration=1),
        fault=FaultConfig(type=FaultType.LATENCY, delay_ms=100, duration=1),
        recovery=RecoveryConfig(
            enabled=True,
            criteria=RecoveryCriteria(max_p95_ms=100.0, max_error_rate=0.05, consecutive_healthy_samples=1),
            timeout=2,
        ),
    )

    # Mock HTTP transport
    def mock_handler(request: httpx.Request):
        # Emulate fault delay if header present
        is_fault = "x-test-fault-type" in request.headers
        lat = 120.0 if is_fault else 10.0
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(mock_handler)
    runner = IncidentRunner(scenario=scenario, transport=transport)

    result: IncidentResult = await runner.run()

    assert result.scenario_name == "test_quick_incident"
    assert result.target == "http://localhost:3000"
    assert result.lifecycle_state == IncidentLifecycleState.COMPLETED
    assert result.fault.status == "completed"
    assert result.recovery.status == "recovered"

    # Verify Before / During / After Metrics
    assert result.before_metrics.total_requests > 0
    assert result.during_metrics.total_requests > 0
    assert result.after_metrics.total_requests > 0

    # Verify Timeline Events
    event_names = [e.event for e in result.timeline]
    assert "experiment_started" in event_names
    assert "baseline_started" in event_names
    assert "fault_started" in event_names
    assert "fault_ended" in event_names
    assert "recovery_started" in event_names
    assert "recovered" in event_names
    assert "experiment_completed" in event_names


def test_incident_recorder_full_export(tmp_path):
    """Verify IncidentRecorder generates all 6 required files."""
    from app.reporting.incident_reporter import IncidentRecorder
    from app.incidents.models import (
        PhaseMetricsSummary,
        FaultExecutionRecord,
        RecoveryExecutionRecord,
        IncidentResult,
        IncidentLifecycleState,
    )

    incident = IncidentResult(
        experiment_id="20261003_120000_test_incident",
        scenario_name="test_incident",
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

    recorder = IncidentRecorder(output_base_dir=tmp_path)
    out_dir = recorder.record(incident)

    assert out_dir.is_dir()
    assert (out_dir / "experiment.json").is_file()
    assert (out_dir / "stages.csv").is_file()
    assert (out_dir / "latency.csv").is_file()
    assert (out_dir / "faults.csv").is_file()
    assert (out_dir / "timeline.csv").is_file()
    assert (out_dir / "report.html").is_file()

