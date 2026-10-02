"""Safety controller for validating test parameters before execution."""

from urllib.parse import urlparse
from app.config import AppConfig


class SafetyValidationError(ValueError):
    """Raised when parameters violate safety boundaries."""
    pass


class SafetyController:
    """Validates target URL and runtime limits against configured safety boundaries."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def validate_target_url(self, url: str) -> str:
        """Validate target URL for scheme, format, and network location.

        Returns the normalized target URL string if valid.
        Raises SafetyValidationError if invalid.
        """
        if not url or not url.strip():
            raise SafetyValidationError("URL cannot be empty")

        url_clean = url.strip()
        parsed = urlparse(url_clean)

        unsupported_schemes = {"ftp", "ssh", "file", "javascript", "mailto", "tel", "ws", "wss", "git"}
        if parsed.scheme.lower() in unsupported_schemes:
            raise SafetyValidationError(
                f"Unsupported scheme '{parsed.scheme}': only http and https are allowed"
            )

        if not parsed.scheme or "://" not in url_clean:
            raise SafetyValidationError("Missing URL scheme (e.g., http:// or https://)")

        if parsed.scheme.lower() not in {"http", "https"}:
            raise SafetyValidationError(
                f"Unsupported scheme '{parsed.scheme}': only http and https are allowed"
            )

        if not parsed.netloc:
            raise SafetyValidationError("Missing host in URL")

        return url_clean

    def validate_limits(
        self,
        timeout: float | None = None,
        duration: int | None = None,
        rate: int | None = None,
        concurrency: int | None = None,
    ) -> None:
        """Validate execution parameters against safety thresholds."""
        if timeout is not None:
            if timeout <= 0:
                raise SafetyValidationError("Timeout must be greater than 0")
            if timeout > self.config.request_timeout:
                raise SafetyValidationError(
                    f"Timeout exceeds configured maximum ({self.config.request_timeout}s)"
                )

        if duration is not None:
            if duration <= 0:
                raise SafetyValidationError("Duration must be greater than 0")
            if duration > self.config.max_test_duration:
                raise SafetyValidationError(
                    f"Duration exceeds configured maximum ({self.config.max_test_duration}s)"
                )

        if rate is not None:
            if rate <= 0:
                raise SafetyValidationError("Request rate must be greater than 0")
            if rate > self.config.max_request_rate:
                raise SafetyValidationError(
                    f"Request rate exceeds configured maximum ({self.config.max_request_rate})"
                )

        if concurrency is not None:
            if concurrency <= 0:
                raise SafetyValidationError("Concurrency must be greater than 0")
            if concurrency > self.config.max_concurrency:
                raise SafetyValidationError(
                    f"Concurrency exceeds configured maximum ({self.config.max_concurrency})"
                )
