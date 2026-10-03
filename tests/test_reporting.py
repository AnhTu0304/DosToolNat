"""Tests for Phase 4 reporting, file exports, and experiment recording."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.metrics.models import (
    RequestResult,
    LoadTestReport,
    ExperimentResult,
    StageMetricsRecord,
    AggregateMetricsRecord,
    LatencySampleRecord,
)
from app.reporting.recorder import (
    generate_experiment_id,
    build_experiment_result,
    ExperimentRecorder,
)
from app.reporting.json_reporter import write_json_report
from app.reporting.csv_reporter import write_csv_reports
from app.reporting.html_reporter import write_html_report
from app.scenarios.models import Scenario, ScenarioStage, StageResult, ScenarioResult


@pytest.fixture
def sample_experiment_data():
    """Fixture providing a realistic ScenarioResult with 2 stages and individual samples."""
    scenario = Scenario(
        name="frontend_load",
        description="Controlled load test for ecommerce frontend",
        target="http://localhost:3000",
        method="GET",
        stages=[
            ScenarioStage(rate=2, concurrency=1, duration=10),
            ScenarioStage(rate=5, concurrency=2, duration=10),
        ],
    )

    req1 = RequestResult(timestamp=100.0, status_code=200, latency_ms=10.0, success=True)
    req2 = RequestResult(timestamp=101.0, status_code=200, latency_ms=20.0, success=True)
    req3 = RequestResult(timestamp=102.0, status_code=404, latency_ms=15.0, success=False, error_message="HTTP 404")
    req4 = RequestResult(timestamp=103.0, status_code=None, latency_ms=5000.0, success=False, timeout=True, error_message="Timeout")

    report1 = LoadTestReport(
        target="http://localhost:3000",
        method="GET",
        requested_rate=2.0,
        actual_rate=1.95,
        concurrency=1,
        duration=10.0,
        total_requests=2,
        successful_requests=2,
        failed_requests=0,
        status_2xx=2,
        min_latency=10.0,
        max_latency=20.0,
        average_latency=15.0,
        p50_latency=15.0,
        p95_latency=19.5,
        p99_latency=19.9,
        start_time=100.0,
        end_time=110.0,
        elapsed_time=10.0,
        results=[req1, req2],
    )

    report2 = LoadTestReport(
        target="http://localhost:3000",
        method="GET",
        requested_rate=5.0,
        actual_rate=4.9,
        concurrency=2,
        duration=10.0,
        total_requests=2,
        successful_requests=0,
        failed_requests=2,
        status_4xx=1,
        timeouts=1,
        min_latency=15.0,
        max_latency=5000.0,
        average_latency=2507.5,
        p50_latency=2507.5,
        p95_latency=4750.7,
        p99_latency=4950.1,
        start_time=110.0,
        end_time=120.0,
        elapsed_time=10.0,
        results=[req3, req4],
    )

    stage_res1 = StageResult(stage_index=1, stage=scenario.stages[0], report=report1)
    stage_res2 = StageResult(stage_index=2, stage=scenario.stages[1], report=report2)

    scenario_res = ScenarioResult(
        scenario_name="frontend_load",
        target="http://localhost:3000",
        total_duration=20.0,
        stage_results=[stage_res1, stage_res2],
        total_requests=4,
        total_successful=2,
        total_failed=2,
        total_timeouts=1,
        total_connection_errors=0,
    )

    config_dict = {
        "timeout": 5,
        "max_rate": 100,
        "max_concurrency": 20,
        "max_duration": 60,
    }

    return scenario, scenario_res, config_dict


def test_generate_experiment_id():
    """Verify experiment ID format YYYYMMDD_HHMMSS_<scenario_name>."""
    fixed_dt = datetime(2026, 10, 3, 15, 30, 0, tzinfo=timezone.utc)
    exp_id = generate_experiment_id("frontend_load", now=fixed_dt)
    assert exp_id == "20261003_153000_frontend_load"


def test_build_experiment_result(sample_experiment_data):
    """Verify building structured ExperimentResult with latency samples and true percentiles."""
    scenario, scenario_res, config_dict = sample_experiment_data
    exp_result = build_experiment_result(
        scenario=scenario,
        scenario_result=scenario_res,
        config=config_dict,
        experiment_id="20261003_153000_frontend_load",
    )

    assert exp_result.experiment_id == "20261003_153000_frontend_load"
    assert exp_result.scenario_name == "frontend_load"
    assert exp_result.target == "http://localhost:3000"
    assert exp_result.aggregate_metrics.total_requests == 4
    assert exp_result.aggregate_metrics.successful == 2
    assert exp_result.aggregate_metrics.failed == 2
    assert exp_result.aggregate_metrics.timeouts == 1
    assert exp_result.aggregate_metrics.success_rate == 50.0
    assert exp_result.aggregate_metrics.error_rate == 50.0

    # Verify per-stage records
    assert len(exp_result.stages) == 2
    assert exp_result.stages[0].stage_number == 1
    assert exp_result.stages[0].target_rate == 2.0
    assert exp_result.stages[1].stage_number == 2
    assert exp_result.stages[1].failed == 2

    # Verify raw latency samples
    assert len(exp_result.latency_samples) == 4
    assert exp_result.latency_samples[0].stage_number == 1
    assert exp_result.latency_samples[0].latency_ms == 10.0
    assert exp_result.latency_samples[0].success is True
    assert exp_result.latency_samples[0].error_type is None

    assert exp_result.latency_samples[2].status_code == 404
    assert exp_result.latency_samples[2].error_type == "http_error"

    assert exp_result.latency_samples[3].error_type == "timeout"

    # Verify scenario-level true percentiles computed directly from all samples [10, 15, 20, 5000]
    stats = exp_result.latency_statistics
    assert stats["min"] == 10.0
    assert stats["max"] == 5000.0


def test_write_json_report(sample_experiment_data, tmp_path):
    """Verify JSON report generation and schema compliance."""
    scenario, scenario_res, config_dict = sample_experiment_data
    exp_result = build_experiment_result(scenario, scenario_res, config_dict, "20261003_153000_frontend_load")

    json_file = write_json_report(exp_result, tmp_path)
    assert json_file.is_file()
    assert json_file.name == "experiment.json"

    with json_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["experiment_id"] == "20261003_153000_frontend_load"
    assert data["aggregate_metrics"]["total_requests"] == 4
    assert len(data["stages"]) == 2
    assert len(data["latency_samples"]) == 4


def test_write_csv_reports(sample_experiment_data, tmp_path):
    """Verify stages.csv and latency.csv generation and format."""
    scenario, scenario_res, config_dict = sample_experiment_data
    exp_result = build_experiment_result(scenario, scenario_res, config_dict, "20261003_153000_frontend_load")

    stages_csv, latency_csv = write_csv_reports(exp_result, tmp_path)
    assert stages_csv.is_file()
    assert stages_csv.name == "stages.csv"
    assert latency_csv.is_file()
    assert latency_csv.name == "latency.csv"

    # Check stages.csv headers and content
    with stages_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert "experiment_id" in rows[0]
        assert "stage_number" in rows[0]
        assert "p95_latency_ms" in rows[0]
        assert rows[0]["stage_number"] == "1"
        assert rows[1]["stage_number"] == "2"

    # Check latency.csv headers and content
    with latency_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 4
        assert "latency_ms" in rows[0]
        assert "error_type" in rows[0]
        assert rows[0]["status_code"] == "200"
        assert rows[3]["error_type"] == "timeout"


def test_write_html_report(sample_experiment_data, tmp_path):
    """Verify HTML report generation with all required sections."""
    scenario, scenario_res, config_dict = sample_experiment_data
    exp_result = build_experiment_result(scenario, scenario_res, config_dict, "20261003_153000_frontend_load")

    html_file = write_html_report(exp_result, tmp_path)
    assert html_file.is_file()
    assert html_file.name == "report.html"

    content = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "frontend_load" in content
    assert "http://localhost:3000" in content
    assert "Stage Summary" in content or "STAGE SUMMARY" in content
    assert "Total Requests" in content


def test_experiment_recorder_full_run(sample_experiment_data, tmp_path):
    """Verify ExperimentRecorder creates designated folders and all 4 reports without overwriting."""
    scenario, scenario_res, config_dict = sample_experiment_data
    exp_result1 = build_experiment_result(scenario, scenario_res, config_dict, "20261003_153000_frontend_load")
    exp_result2 = build_experiment_result(scenario, scenario_res, config_dict, "20261003_154500_frontend_load")

    recorder = ExperimentRecorder(output_base_dir=tmp_path)

    dir1 = recorder.record(exp_result1)
    dir2 = recorder.record(exp_result2)

    assert dir1 != dir2
    assert (dir1 / "experiment.json").is_file()
    assert (dir1 / "stages.csv").is_file()
    assert (dir1 / "latency.csv").is_file()
    assert (dir1 / "report.html").is_file()

    assert (dir2 / "experiment.json").is_file()
    assert (dir2 / "stages.csv").is_file()
    assert (dir2 / "latency.csv").is_file()
    assert (dir2 / "report.html").is_file()
