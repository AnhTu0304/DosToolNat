"""Tests for configuration management."""

import pytest
from pydantic import ValidationError
from app.config import AppConfig, load_config


def test_default_config():
    """Verify default configuration values."""
    config = AppConfig()
    assert config.target_url == "http://localhost:8000"
    assert config.request_timeout == 5.0
    assert config.max_test_duration == 60
    assert config.max_request_rate == 100
    assert config.max_concurrency == 20
    assert config.log_level == "INFO"


def test_load_config_from_valid_yaml(tmp_path):
    """Verify loading config from a valid YAML file."""
    yaml_content = """
    target_url: "https://example.com/api"
    request_timeout: 10
    max_test_duration: 120
    max_request_rate: 50
    max_concurrency: 10
    log_level: "DEBUG"
    """
    config_file = tmp_path / "custom_config.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    config = load_config(config_file)
    assert config.target_url == "https://example.com/api"
    assert config.request_timeout == 10.0
    assert config.max_test_duration == 120
    assert config.max_request_rate == 50
    assert config.max_concurrency == 10
    assert config.log_level == "DEBUG"


def test_load_config_file_not_found():
    """Verify error when config file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_file.yaml")


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("request_timeout", 0),
        ("request_timeout", -5),
        ("max_test_duration", 0),
        ("max_test_duration", -10),
        ("max_request_rate", 0),
        ("max_concurrency", 0),
        ("log_level", "INVALID_LEVEL"),
    ],
)
def test_invalid_config_values(field, invalid_value):
    """Verify validation errors for out-of-bound or invalid configuration."""
    with pytest.raises(ValidationError):
        AppConfig(**{field: invalid_value})
