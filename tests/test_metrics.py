"""Tests for metrics collection, latency percentile calculation, and report generation."""

import pytest
from app.metrics.models import RequestResult, LoadTestReport
from app.metrics.collector import MetricsCollector


def test_empty_metrics_collector():
    """Verify that empty metrics return safe zero values."""
    collector = MetricsCollector(target="http://localhost:3000", requested_rate=10, concurrency=5)
    report = collector.build_report(start_time=100.0, end_time=110.0)

    assert report.total_requests == 0
    assert report.successful_requests == 0
    assert report.failed_requests == 0
    assert report.min_latency == 0.0
    assert report.max_latency == 0.0
    assert report.average_latency == 0.0
    assert report.p50_latency == 0.0
    assert report.p95_latency == 0.0
    assert report.p99_latency == 0.0
    assert report.actual_rate == 0.0
    assert report.elapsed_time == 10.0


def test_metrics_collector_classification():
    """Verify classification of HTTP status codes and error types."""
    collector = MetricsCollector(target="http://localhost:3000", requested_rate=10, concurrency=2)

    # Add 2xx
    collector.add_result(RequestResult(
        timestamp=1.0, status_code=200, latency_ms=10.0, success=True, timeout=False, connection_error=False
    ))
    # Add 3xx
    collector.add_result(RequestResult(
        timestamp=1.1, status_code=301, latency_ms=12.0, success=True, timeout=False, connection_error=False
    ))
    # Add 4xx
    collector.add_result(RequestResult(
        timestamp=1.2, status_code=404, latency_ms=15.0, success=False, timeout=False, connection_error=False
    ))
    # Add 5xx
    collector.add_result(RequestResult(
        timestamp=1.3, status_code=500, latency_ms=20.0, success=False, timeout=False, connection_error=False
    ))
    # Add Timeout
    collector.add_result(RequestResult(
        timestamp=1.4, status_code=None, latency_ms=5000.0, success=False, timeout=True, connection_error=False, error_message="Timed out"
    ))
    # Add Connection Error
    collector.add_result(RequestResult(
        timestamp=1.5, status_code=None, latency_ms=5.0, success=False, timeout=False, connection_error=True, error_message="Conn refused"
    ))

    report = collector.build_report(start_time=1.0, end_time=2.0)

    assert report.total_requests == 6
    assert report.successful_requests == 2  # 200 and 301
    assert report.failed_requests == 4      # 404, 500, timeout, conn_error
    assert report.status_2xx == 1
    assert report.status_3xx == 1
    assert report.status_4xx == 1
    assert report.status_5xx == 1
    assert report.timeouts == 1
    assert report.connection_errors == 1


def test_percentile_calculations():
    """Verify precision of min, max, average, and P50, P95, P99 calculations."""
    collector = MetricsCollector(target="http://localhost:3000", requested_rate=10, concurrency=5)

    # Add 100 requests with latencies 1.0, 2.0, ..., 100.0
    for i in range(1, 101):
        collector.add_result(RequestResult(
            timestamp=float(i),
            status_code=200,
            latency_ms=float(i),
            success=True,
            timeout=False,
            connection_error=False,
        ))

    report = collector.build_report(start_time=0.0, end_time=10.0)

    assert report.total_requests == 100
    assert report.min_latency == 1.0
    assert report.max_latency == 100.0
    assert report.average_latency == 50.5
    # P50 should be between 50 and 51
    assert 50.0 <= report.p50_latency <= 51.0
    # P95 should be approx 95.05
    assert 94.0 <= report.p95_latency <= 96.0
    # P99 should be approx 99.01
    assert 98.0 <= report.p99_latency <= 100.0
    assert report.actual_rate == 10.0


def test_report_serialization():
    """Verify LoadTestReport can serialize to JSON and dict."""
    collector = MetricsCollector(target="http://localhost:3000", requested_rate=10, concurrency=2)
    collector.add_result(RequestResult(
        timestamp=1.0, status_code=200, latency_ms=25.5, success=True, timeout=False, connection_error=False
    ))
    report = collector.build_report(start_time=1.0, end_time=2.0)

    report_dict = report.model_dump()
    assert report_dict["target"] == "http://localhost:3000"
    assert report_dict["total_requests"] == 1
    assert report_dict["average_latency"] == 25.5

    json_str = report.model_dump_json()
    assert '"total_requests":1' in json_str
