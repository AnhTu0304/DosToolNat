"""Tests for reusable statistical calculations."""

import pytest
from app.metrics.statistics import (
    calculate_min,
    calculate_max,
    calculate_average,
    calculate_percentile,
    calculate_success_rate,
    calculate_error_rate,
    calculate_latency_summary,
)


def test_statistics_empty_list():
    """Verify safe zero results on empty list."""
    assert calculate_min([]) == 0.0
    assert calculate_max([]) == 0.0
    assert calculate_average([]) == 0.0
    assert calculate_percentile([], 50.0) == 0.0
    assert calculate_percentile([], 95.0) == 0.0
    assert calculate_percentile([], 99.0) == 0.0

    summary = calculate_latency_summary([])
    assert summary["min"] == 0.0
    assert summary["max"] == 0.0
    assert summary["average"] == 0.0
    assert summary["p50"] == 0.0
    assert summary["p95"] == 0.0
    assert summary["p99"] == 0.0


def test_statistics_single_element():
    """Verify single element statistics."""
    values = [42.5]
    assert calculate_min(values) == 42.5
    assert calculate_max(values) == 42.5
    assert calculate_average(values) == 42.5
    assert calculate_percentile(values, 50.0) == 42.5
    assert calculate_percentile(values, 95.0) == 42.5
    assert calculate_percentile(values, 99.0) == 42.5


def test_statistics_multi_elements():
    """Verify percentiles and averages with known dataset [10, 20, 30, 40, 50]."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_min(values) == 10.0
    assert calculate_max(values) == 50.0
    assert calculate_average(values) == 30.0
    assert calculate_percentile(sorted(values), 50.0) == 30.0
    assert calculate_percentile(sorted(values), 95.0) == 48.0
    assert calculate_percentile(sorted(values), 99.0) == 49.6


def test_rates_with_non_zero_and_zero_totals():
    """Verify success rate and error rate calculation with division by zero safeguards."""
    assert calculate_success_rate(170, 170) == 100.0
    assert calculate_error_rate(0, 170) == 0.0

    assert calculate_success_rate(150, 200) == 75.0
    assert calculate_error_rate(50, 200) == 25.0

    # Zero total requests
    assert calculate_success_rate(0, 0) == 0.0
    assert calculate_error_rate(0, 0) == 0.0
