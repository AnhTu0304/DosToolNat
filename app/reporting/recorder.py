"""Experiment recorder and orchestrator for Phase 4 metrics persistence."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.metrics.models import (
    ExperimentResult,
    StageMetricsRecord,
    AggregateMetricsRecord,
    LatencySampleRecord,
)
from app.metrics.statistics import (
    calculate_success_rate,
    calculate_error_rate,
    calculate_latency_summary,
)
from app.reporting.json_reporter import write_json_report
from app.reporting.csv_reporter import write_csv_reports
from app.reporting.html_reporter import write_html_report
from app.scenarios.models import Scenario, ScenarioResult


def generate_experiment_id(scenario_name: str, now: Optional[datetime] = None) -> str:
    """Generate a unique experiment ID in format YYYYMMDD_HHMMSS_<scenario_name>."""
    if now is None:
        now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{scenario_name}"


def _determine_error_type(sample) -> Optional[str]:
    """Helper to categorize request error types."""
    if sample.success:
        return None
    if getattr(sample, "timeout", False):
        return "timeout"
    if getattr(sample, "connection_error", False):
        return "connection_error"
    if sample.status_code and sample.status_code >= 400:
        return "http_error"

    msg = (sample.error_message or "").lower()
    if "timeout" in msg:
        return "timeout"
    if "connect" in msg:
        return "connection_error"
    return "request_error"


def build_experiment_result(
    scenario: Scenario,
    scenario_result: ScenarioResult,
    config: Dict[str, Any],
    experiment_id: Optional[str] = None,
) -> ExperimentResult:
    """Transform in-memory scenario execution results into a complete, structured ExperimentResult."""
    if not experiment_id:
        experiment_id = generate_experiment_id(scenario.name)

    stages_records: List[StageMetricsRecord] = []
    all_latency_samples: List[LatencySampleRecord] = []
    raw_latencies_for_stats: List[float] = []

    # Process each stage
    for stage_res in scenario_result.stage_results:
        rep = stage_res.report
        stg = stage_res.stage

        stage_record = StageMetricsRecord(
            stage_number=stage_res.stage_index,
            target_rate=stg.rate,
            actual_rps=rep.actual_rate,
            concurrency=stg.concurrency,
            duration_seconds=stg.duration,
            total_requests=rep.total_requests,
            successful=rep.successful_requests,
            failed=rep.failed_requests,
            timeouts=rep.timeouts,
            connection_errors=rep.connection_errors,
            http_2xx=rep.status_2xx,
            http_3xx=rep.status_3xx,
            http_4xx=rep.status_4xx,
            http_5xx=rep.status_5xx,
            min_latency_ms=rep.min_latency,
            avg_latency_ms=rep.average_latency,
            p50_latency_ms=rep.p50_latency,
            p95_latency_ms=rep.p95_latency,
            p99_latency_ms=rep.p99_latency,
            max_latency_ms=rep.max_latency,
        )
        stages_records.append(stage_record)

        # Collect latency samples
        for req in rep.results:
            # Convert float timestamp to ISO 8601 UTC
            if isinstance(req.timestamp, (int, float)):
                ts_iso = datetime.fromtimestamp(req.timestamp, tz=timezone.utc).isoformat()
            else:
                ts_iso = str(req.timestamp)

            error_type = _determine_error_type(req)

            all_latency_samples.append(
                LatencySampleRecord(
                    timestamp=ts_iso,
                    stage_number=stage_res.stage_index,
                    latency_ms=req.latency_ms,
                    status_code=req.status_code,
                    success=req.success,
                    error_type=error_type,
                )
            )

            if req.latency_ms is not None:
                raw_latencies_for_stats.append(req.latency_ms)

    # Compute scenario-level aggregated metrics
    http_2xx = sum(s.http_2xx for s in stages_records)
    http_3xx = sum(s.http_3xx for s in stages_records)
    http_4xx = sum(s.http_4xx for s in stages_records)
    http_5xx = sum(s.http_5xx for s in stages_records)

    tot_req = scenario_result.total_requests
    tot_succ = scenario_result.total_successful
    tot_failed = scenario_result.total_failed

    avg_rps = (tot_req / scenario_result.total_duration) if scenario_result.total_duration > 0 else 0.0

    aggregate_metrics = AggregateMetricsRecord(
        total_requests=tot_req,
        successful=tot_succ,
        failed=tot_failed,
        timeouts=scenario_result.total_timeouts,
        connection_errors=scenario_result.total_connection_errors,
        http_2xx=http_2xx,
        http_3xx=http_3xx,
        http_4xx=http_4xx,
        http_5xx=http_5xx,
        success_rate=calculate_success_rate(tot_succ, tot_req),
        error_rate=calculate_error_rate(tot_failed, tot_req),
        average_rps=avg_rps,
    )

    # Calculate true scenario-level latency statistics from all raw samples
    latency_statistics = calculate_latency_summary(raw_latencies_for_stats)

    # Determine timestamps
    if stages_records and scenario_result.stage_results[0].report.start_time:
        st_epoch = scenario_result.stage_results[0].report.start_time
        ts_start = datetime.fromtimestamp(st_epoch, tz=timezone.utc).isoformat()
    else:
        ts_start = datetime.now(timezone.utc).isoformat()

    if stages_records and scenario_result.stage_results[-1].report.end_time:
        et_epoch = scenario_result.stage_results[-1].report.end_time
        ts_end = datetime.fromtimestamp(et_epoch, tz=timezone.utc).isoformat()
    else:
        ts_end = datetime.now(timezone.utc).isoformat()

    return ExperimentResult(
        experiment_id=experiment_id,
        scenario_name=scenario.name,
        target=str(scenario.target),
        method=scenario.method,
        description=scenario.description,
        start_time=ts_start,
        end_time=ts_end,
        total_duration_seconds=scenario_result.total_duration,
        configuration=config,
        aggregate_metrics=aggregate_metrics,
        latency_statistics=latency_statistics,
        stages=stages_records,
        latency_samples=all_latency_samples,
    )


class ExperimentRecorder:
    """Manages the creation of output folders and multi-format report export."""

    def __init__(self, output_base_dir: Path = Path("reports")):
        self.output_base_dir = Path(output_base_dir)

    def record(self, experiment: ExperimentResult) -> Path:
        """Create target directory reports/<scenario_name>/<experiment_id>/ and save all reports."""
        target_dir = self.output_base_dir / experiment.scenario_name / experiment.experiment_id
        target_dir.mkdir(parents=True, exist_ok=True)

        write_json_report(experiment, target_dir)
        write_csv_reports(experiment, target_dir)
        write_html_report(experiment, target_dir)

        return target_dir
