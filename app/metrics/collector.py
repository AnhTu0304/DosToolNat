"""Thread-safe and async-friendly metrics collector for load tests."""

import math
from typing import List, Optional
from app.metrics.models import RequestResult, LoadTestReport


def calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calculate the p-th percentile from a sorted list of floats using linear interpolation."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]

    k = (percentile / 100.0) * (n - 1)
    f = math.floor(k)
    c = k - f

    if f + 1 < n:
        return round(sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f]), 2)
    return round(sorted_values[f], 2)


class MetricsCollector:
    """Collects individual request results and computes statistical summaries."""

    def __init__(self, target: str, requested_rate: float, concurrency: int, duration: float = 0.0) -> None:
        self.target = target
        self.requested_rate = requested_rate
        self.concurrency = concurrency
        self.duration = duration
        self._results: List[RequestResult] = []

    def add_result(self, result: RequestResult) -> None:
        """Add a single request execution result."""
        self._results.append(result)

    @property
    def total_requests(self) -> int:
        return len(self._results)

    @property
    def successful_requests(self) -> int:
        return sum(1 for r in self._results if r.status_code is not None and 200 <= r.status_code < 400)

    @property
    def failed_requests(self) -> int:
        return self.total_requests - self.successful_requests

    def get_current_stats(self, elapsed_seconds: float) -> dict:
        """Return a lightweight snapshot of current progress for live display."""
        total = self.total_requests
        success = self.successful_requests
        failed = self.failed_requests
        current_rps = (total / elapsed_seconds) if elapsed_seconds > 0 else 0.0

        latencies = [r.latency_ms for r in self._results]
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "rps": round(current_rps, 1),
            "avg_latency": round(avg_latency, 1),
        }

    def build_report(self, start_time: float, end_time: float) -> LoadTestReport:
        """Compile complete statistics into a LoadTestReport."""
        elapsed = max(end_time - start_time, 0.001)
        total = len(self._results)

        status_2xx = sum(1 for r in self._results if r.status_code and 200 <= r.status_code < 300)
        status_3xx = sum(1 for r in self._results if r.status_code and 300 <= r.status_code < 400)
        status_4xx = sum(1 for r in self._results if r.status_code and 400 <= r.status_code < 500)
        status_5xx = sum(1 for r in self._results if r.status_code and 500 <= r.status_code < 600)

        timeouts = sum(1 for r in self._results if r.timeout)
        connection_errors = sum(1 for r in self._results if r.connection_error)

        successful = status_2xx + status_3xx
        failed = total - successful

        latencies = sorted(r.latency_ms for r in self._results)
        if latencies:
            min_lat = round(latencies[0], 2)
            max_lat = round(latencies[-1], 2)
            avg_lat = round(sum(latencies) / len(latencies), 2)
            p50_lat = calculate_percentile(latencies, 50.0)
            p95_lat = calculate_percentile(latencies, 95.0)
            p99_lat = calculate_percentile(latencies, 99.0)
        else:
            min_lat = 0.0
            max_lat = 0.0
            avg_lat = 0.0
            p50_lat = 0.0
            p95_lat = 0.0
            p99_lat = 0.0

        actual_rps = round(total / elapsed, 2)

        return LoadTestReport(
            target=self.target,
            method="GET",
            requested_rate=float(self.requested_rate),
            actual_rate=actual_rps,
            concurrency=self.concurrency,
            duration=self.duration,
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            status_2xx=status_2xx,
            status_3xx=status_3xx,
            status_4xx=status_4xx,
            status_5xx=status_5xx,
            timeouts=timeouts,
            connection_errors=connection_errors,
            min_latency=min_lat,
            max_latency=max_lat,
            average_latency=avg_lat,
            p50_latency=p50_lat,
            p95_latency=p95_lat,
            p99_latency=p99_lat,
            start_time=start_time,
            end_time=end_time,
            elapsed_time=round(elapsed, 2),
        )
