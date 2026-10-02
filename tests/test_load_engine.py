"""Tests for asynchronous HTTP worker and load test runner."""

import asyncio
import httpx
import pytest
from app.engine.worker import execute_request
from app.engine.runner import LoadTestRunner
from app.metrics.models import RequestResult, LoadTestReport


@pytest.mark.anyio
async def test_worker_success():
    """Verify worker returns success for HTTP 200 response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(transport=transport) as client:
        result: RequestResult = await execute_request(client, "http://testserver/api", semaphore)

    assert result.status_code == 200
    assert result.success is True
    assert result.timeout is False
    assert result.connection_error is False
    assert result.latency_ms >= 0


@pytest.mark.anyio
async def test_worker_http_errors():
    """Verify worker captures HTTP 404 and 500 responses without crashing."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/404":
            return httpx.Response(404, text="Not Found")
        return httpx.Response(500, text="Server Error")

    transport = httpx.MockTransport(handler)
    semaphore = asyncio.Semaphore(2)

    async with httpx.AsyncClient(transport=transport) as client:
        res_404 = await execute_request(client, "http://testserver/404", semaphore)
        res_500 = await execute_request(client, "http://testserver/500", semaphore)

    assert res_404.status_code == 404
    assert res_404.success is False

    assert res_500.status_code == 500
    assert res_500.success is False


@pytest.mark.anyio
async def test_worker_timeout_and_connection_error():
    """Verify worker captures TimeoutException and ConnectError cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/timeout":
            raise httpx.ReadTimeout("Simulated timeout", request=request)
        raise httpx.ConnectError("Connection refused", request=request)

    transport = httpx.MockTransport(handler)
    semaphore = asyncio.Semaphore(2)

    async with httpx.AsyncClient(transport=transport) as client:
        res_timeout = await execute_request(client, "http://testserver/timeout", semaphore)
        res_connect = await execute_request(client, "http://testserver/connect", semaphore)

    assert res_timeout.timeout is True
    assert res_timeout.success is False
    assert res_timeout.status_code is None

    assert res_connect.connection_error is True
    assert res_connect.success is False
    assert res_connect.status_code is None


@pytest.mark.anyio
async def test_load_test_runner_execution():
    """Verify LoadTestRunner coordinates scheduler, worker, and metrics collector."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)

    runner = LoadTestRunner(
        target_url="http://testserver/load",
        rate=10.0,
        concurrency=3,
        duration=0.5,
        timeout=2.0,
        transport=transport,
    )

    report: LoadTestReport = await runner.run()

    assert report.total_requests >= 4
    assert report.successful_requests == report.total_requests
    assert report.failed_requests == 0
    assert report.status_2xx == report.total_requests
    assert report.concurrency == 3
    assert report.average_latency >= 0


@pytest.mark.anyio
async def test_load_test_runner_graceful_shutdown():
    """Verify LoadTestRunner can be stopped early cleanly."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)

    runner = LoadTestRunner(
        target_url="http://testserver/load",
        rate=20.0,
        concurrency=2,
        duration=5.0,  # Long duration
        timeout=2.0,
        transport=transport,
    )

    async def stop_after_delay():
        await asyncio.sleep(0.2)
        runner.stop()

    asyncio.create_task(stop_after_delay())
    report: LoadTestReport = await runner.run()

    assert report.total_requests < 20  # Stopped well before the 100 requests of 5.0s
    assert report.elapsed_time < 2.0
