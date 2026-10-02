"""Worker executing individual HTTP GET requests with concurrency control."""

import asyncio
import time
from typing import Optional
import httpx
from app.metrics.models import RequestResult


async def execute_request(
    client: httpx.AsyncClient,
    target_url: str,
    semaphore: asyncio.Semaphore,
) -> RequestResult:
    """Execute a single HTTP GET request under concurrency semaphore constraint."""
    async with semaphore:
        start_time = time.perf_counter()
        timestamp = time.time()
        try:
            response = await client.get(target_url)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            status = response.status_code
            is_success = 200 <= status < 400
            err_msg = None if is_success else f"HTTP {status}"

            return RequestResult(
                timestamp=timestamp,
                status_code=status,
                latency_ms=round(latency_ms, 2),
                success=is_success,
                timeout=False,
                connection_error=False,
                error_message=err_msg,
            )
        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                status_code=None,
                latency_ms=round(latency_ms, 2),
                success=False,
                timeout=True,
                connection_error=False,
                error_message="Request timed out",
            )
        except httpx.ConnectError:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                status_code=None,
                latency_ms=round(latency_ms, 2),
                success=False,
                timeout=False,
                connection_error=True,
                error_message="Connection refused or unreachable",
            )
        except httpx.RequestError as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                status_code=None,
                latency_ms=round(latency_ms, 2),
                success=False,
                timeout=False,
                connection_error=True,
                error_message=f"Request error: {exc}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return RequestResult(
                timestamp=timestamp,
                status_code=None,
                latency_ms=round(latency_ms, 2),
                success=False,
                timeout=False,
                connection_error=False,
                error_message=f"Unexpected error: {exc}",
            )
