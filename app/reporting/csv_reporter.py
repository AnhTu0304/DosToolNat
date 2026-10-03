"""CSV reporter for exporting stage summaries and per-request latency samples."""

import csv
from pathlib import Path
from typing import Tuple
from app.metrics.models import ExperimentResult


def write_csv_reports(experiment: ExperimentResult, output_dir: Path) -> Tuple[Path, Path]:
    """Generate stages.csv and latency.csv files formatted for spreadsheet analysis."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stages_path = output_dir / "stages.csv"
    latency_path = output_dir / "latency.csv"

    # 1. Write stages.csv
    stage_headers = [
        "experiment_id",
        "scenario_name",
        "stage_number",
        "target_rate",
        "actual_rps",
        "concurrency",
        "duration_seconds",
        "total_requests",
        "successful",
        "failed",
        "timeouts",
        "connection_errors",
        "http_2xx",
        "http_3xx",
        "http_4xx",
        "http_5xx",
        "min_latency_ms",
        "avg_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "max_latency_ms",
    ]

    with stages_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=stage_headers)
        writer.writeheader()
        for stg in experiment.stages:
            writer.writerow({
                "experiment_id": experiment.experiment_id,
                "scenario_name": experiment.scenario_name,
                "stage_number": stg.stage_number,
                "target_rate": stg.target_rate,
                "actual_rps": stg.actual_rps,
                "concurrency": stg.concurrency,
                "duration_seconds": stg.duration_seconds,
                "total_requests": stg.total_requests,
                "successful": stg.successful,
                "failed": stg.failed,
                "timeouts": stg.timeouts,
                "connection_errors": stg.connection_errors,
                "http_2xx": stg.http_2xx,
                "http_3xx": stg.http_3xx,
                "http_4xx": stg.http_4xx,
                "http_5xx": stg.http_5xx,
                "min_latency_ms": stg.min_latency_ms,
                "avg_latency_ms": stg.avg_latency_ms,
                "p50_latency_ms": stg.p50_latency_ms,
                "p95_latency_ms": stg.p95_latency_ms,
                "p99_latency_ms": stg.p99_latency_ms,
                "max_latency_ms": stg.max_latency_ms,
            })

    # 2. Write latency.csv
    latency_headers = [
        "experiment_id",
        "timestamp",
        "stage_number",
        "latency_ms",
        "status_code",
        "success",
        "error_type",
    ]

    with latency_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=latency_headers)
        writer.writeheader()
        for sample in experiment.latency_samples:
            writer.writerow({
                "experiment_id": experiment.experiment_id,
                "timestamp": sample.timestamp,
                "stage_number": sample.stage_number,
                "latency_ms": sample.latency_ms if sample.latency_ms is not None else "",
                "status_code": sample.status_code if sample.status_code is not None else "",
                "success": str(sample.success).lower(),
                "error_type": sample.error_type if sample.error_type else "",
            })

    return stages_path, latency_path
