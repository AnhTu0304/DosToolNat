"""Reusable statistical calculations for latency, rates, and distributions."""

import math
from typing import Dict, List


def calculate_min(values: List[float]) -> float:
    """Return the minimum value or 0.0 if empty."""
    return round(min(values), 2) if values else 0.0


def calculate_max(values: List[float]) -> float:
    """Return the maximum value or 0.0 if empty."""
    return round(max(values), 2) if values else 0.0


def calculate_average(values: List[float]) -> float:
    """Return the arithmetic mean or 0.0 if empty."""
    return round(sum(values) / len(values), 2) if values else 0.0


def calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calculate the p-th percentile from a sorted list of floats using linear interpolation."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return round(sorted_values[0], 2)

    k = (percentile / 100.0) * (n - 1)
    f = math.floor(k)
    c = k - f

    if f + 1 < n:
        return round(sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f]), 2)
    return round(sorted_values[f], 2)


def calculate_success_rate(successful: int, total: int) -> float:
    """Calculate percentage of successful requests, safeguarded against division by zero."""
    if total <= 0:
        return 0.0
    return round((successful / total) * 100.0, 2)


def calculate_error_rate(failed: int, total: int) -> float:
    """Calculate percentage of failed requests, safeguarded against division by zero."""
    if total <= 0:
        return 0.0
    return round((failed / total) * 100.0, 2)


def calculate_latency_summary(latencies: List[float]) -> Dict[str, float]:
    """Compute comprehensive latency statistics from raw samples."""
    if not latencies:
        return {
            "min": 0.0,
            "max": 0.0,
            "average": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
        }

    sorted_lats = sorted(latencies)
    return {
        "min": calculate_min(sorted_lats),
        "max": calculate_max(sorted_lats),
        "average": calculate_average(sorted_lats),
        "p50": calculate_percentile(sorted_lats, 50.0),
        "p90": calculate_percentile(sorted_lats, 90.0),
        "p95": calculate_percentile(sorted_lats, 95.0),
        "p99": calculate_percentile(sorted_lats, 99.0),
    }
