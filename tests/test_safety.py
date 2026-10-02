"""Tests for SafetyController."""

import pytest
from app.config import AppConfig
from app.safety.controller import SafetyController, SafetyValidationError


@pytest.fixture
def default_controller():
    config = AppConfig(
        target_url="http://localhost:8000",
        request_timeout=5.0,
        max_test_duration=60,
        max_request_rate=100,
        max_concurrency=20,
    )
    return SafetyController(config)


@pytest.mark.parametrize(
    "valid_url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://example.com",
        "http://example.com/test?param=1",
        "https://sub.domain.local:8443/api/v1",
    ],
)
def test_valid_target_urls(default_controller, valid_url):
    """Verify that well-formed HTTP/HTTPS URLs pass validation."""
    assert default_controller.validate_target_url(valid_url) == valid_url


@pytest.mark.parametrize(
    "invalid_url,expected_match",
    [
        ("", "URL cannot be empty"),
        ("   ", "URL cannot be empty"),
        ("ftp://localhost:8000", "Unsupported scheme"),
        ("file:///etc/passwd", "Unsupported scheme"),
        ("localhost:8000", "Missing URL scheme"),
        ("http://", "Missing host"),
        ("https://", "Missing host"),
        ("javascript:alert(1)", "Unsupported scheme"),
    ],
)
def test_invalid_target_urls(default_controller, invalid_url, expected_match):
    """Verify that malformed or unauthorized scheme URLs raise SafetyValidationError."""
    with pytest.raises(SafetyValidationError, match=expected_match):
        default_controller.validate_target_url(invalid_url)


def test_limits_within_bounds(default_controller):
    """Verify that parameters within configured bounds pass validation."""
    default_controller.validate_limits(
        timeout=3.0,
        duration=30,
        rate=50,
        concurrency=10,
    )


@pytest.mark.parametrize(
    "kwargs,expected_match",
    [
        ({"timeout": 0}, "Timeout must be greater than 0"),
        ({"timeout": -1.0}, "Timeout must be greater than 0"),
        ({"timeout": 10.0}, "Timeout exceeds configured maximum"),
        ({"duration": 0}, "Duration must be greater than 0"),
        ({"duration": 120}, "Duration exceeds configured maximum"),
        ({"rate": 0}, "Request rate must be greater than 0"),
        ({"rate": 200}, "Request rate exceeds configured maximum"),
        ({"concurrency": 0}, "Concurrency must be greater than 0"),
        ({"concurrency": 50}, "Concurrency exceeds configured maximum"),
    ],
)
def test_limits_exceeding_bounds(default_controller, kwargs, expected_match):
    """Verify that limits exceeding configured maximums raise SafetyValidationError."""
    with pytest.raises(SafetyValidationError, match=expected_match):
        default_controller.validate_limits(**kwargs)
