"""HTTP connectivity runner for single request testing."""

import time
from dataclasses import dataclass
import httpx


@dataclass
class ConnectivityResult:
    """Represents the outcome of a connectivity check."""

    target: str
    method: str = "GET"
    status_code: int | None = None
    latency_ms: float = 0.0
    success: bool = False
    error_message: str | None = None


class ConnectivityRunner:
    """Executes single HTTP connectivity checks against targets."""

    def __init__(self, timeout: float = 5.0, client: httpx.Client | None = None) -> None:
        self.timeout = timeout
        self._client = client

    def test_connectivity(self, target_url: str) -> ConnectivityResult:
        """Perform a single GET request to verify target connectivity.

        Measures response latency and handles transport/HTTP exceptions cleanly.
        """
        start_time = time.perf_counter()
        owns_client = self._client is None
        client = self._client if self._client is not None else httpx.Client(timeout=self.timeout)

        try:
            response = client.get(target_url)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return ConnectivityResult(
                target=target_url,
                method="GET",
                status_code=response.status_code,
                latency_ms=round(elapsed_ms, 2),
                success=True,
                error_message=None,
            )
        except httpx.TimeoutException:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectivityResult(
                target=target_url,
                method="GET",
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                success=False,
                error_message="Request timeout (timed out)",
            )
        except httpx.ConnectError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectivityResult(
                target=target_url,
                method="GET",
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                success=False,
                error_message="Connection refused or unreachable",
            )
        except httpx.RequestError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectivityResult(
                target=target_url,
                method="GET",
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                success=False,
                error_message=f"Request error: {exc}",
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectivityResult(
                target=target_url,
                method="GET",
                status_code=None,
                latency_ms=round(elapsed_ms, 2),
                success=False,
                error_message=f"Unexpected error: {exc}",
            )
        finally:
            if owns_client:
                client.close()
