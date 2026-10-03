"""HTTP runners for connectivity and controlled load testing."""

import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Optional, Set
import httpx

from app.engine.worker import execute_request
from app.engine.scheduler import RateScheduler
from app.metrics.collector import MetricsCollector
from app.metrics.models import LoadTestReport


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


class LoadTestRunner:
    """Orchestrates controlled asynchronous load test execution."""

    def __init__(
        self,
        target_url: str,
        rate: float,
        concurrency: int,
        duration: float,
        timeout: float = 5.0,
        headers: Optional[Dict[str, str]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        on_progress: Optional[Callable[[dict, float], None]] = None,
    ) -> None:
        self.target_url = target_url
        self.rate = float(rate)
        self.concurrency = int(concurrency)
        self.duration = float(duration)
        self.timeout = float(timeout)
        self.headers = headers or {}
        self.transport = transport
        self.on_progress = on_progress
        self._scheduler: Optional[RateScheduler] = None
        self._stopped = False

    def stop(self) -> None:
        """Signal the runner and scheduler to stop generating new requests."""
        self._stopped = True
        if self._scheduler:
            self._scheduler.stop()

    async def run(self) -> LoadTestReport:
        """Execute the load test scenario and return the aggregated report."""
        collector = MetricsCollector(
            target=self.target_url,
            requested_rate=self.rate,
            concurrency=self.concurrency,
            duration=self.duration,
        )
        self._scheduler = RateScheduler(rate=self.rate, duration=self.duration)
        semaphore = asyncio.Semaphore(self.concurrency)
        active_tasks: Set[asyncio.Task] = set()

        limits = httpx.Limits(
            max_connections=max(self.concurrency * 2, 10),
            max_keepalive_connections=self.concurrency,
        )

        start_wall_time = time.time()
        start_mono = time.perf_counter()

        client = httpx.AsyncClient(
            timeout=self.timeout,
            transport=self.transport,
            limits=limits,
            headers=self.headers,
        )

        async def worker_wrapper():
            result = await execute_request(client, self.target_url, semaphore)
            collector.add_result(result)

        async def progress_reporter():
            while not self._stopped:
                await asyncio.sleep(0.3)
                elapsed = time.perf_counter() - start_mono
                if self.on_progress:
                    stats = collector.get_current_stats(elapsed)
                    self.on_progress(stats, elapsed)

        reporter_task = asyncio.create_task(progress_reporter())

        try:
            async for _ in self._scheduler.generate_ticks():
                if self._stopped:
                    break
                task = asyncio.create_task(worker_wrapper())
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

        except asyncio.CancelledError:
            self.stop()
        finally:
            reporter_task.cancel()
            try:
                await reporter_task
            except asyncio.CancelledError:
                pass

            if active_tasks:
                await asyncio.wait(active_tasks, timeout=min(self.timeout, 5.0))

            await client.aclose()

        end_wall_time = time.time()
        return collector.build_report(start_wall_time, end_wall_time)
