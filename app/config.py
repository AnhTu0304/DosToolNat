"""Configuration management using Pydantic and PyYAML."""

from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field, field_validator


LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AppConfig(BaseModel):
    """Application configuration schema with safety boundaries."""

    target_url: str = Field(
        default="http://localhost:8000",
        description="Target URL for testing",
    )
    request_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Request timeout in seconds",
    )
    max_test_duration: int = Field(
        default=60,
        gt=0,
        description="Maximum test duration in seconds (safety default)",
    )
    max_request_rate: int = Field(
        default=100,
        gt=0,
        description="Maximum requests per second (safety default)",
    )
    max_concurrency: int = Field(
        default=20,
        gt=0,
        description="Maximum concurrent connections (safety default)",
    )
    log_level: LogLevel = Field(
        default="INFO",
        description="Logging level",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.upper().strip()
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if v_upper in valid_levels:
                return v_upper
        return v


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load configuration from a YAML file or return default configuration."""
    if path is None:
        return AppConfig()

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return AppConfig()

    return AppConfig(**data)
