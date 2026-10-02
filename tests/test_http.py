"""Tests for HTTP connectivity runner using mock transport."""

import httpx
from app.engine.runner import ConnectivityRunner, ConnectivityResult


def test_successful_http_connectivity():
    """Verify successful HTTP 200 GET request."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        runner = ConnectivityRunner(client=client)
        result: ConnectivityResult = runner.test_connectivity("http://testserver/health")

    assert result.success is True
    assert result.status_code == 200
    assert result.target == "http://testserver/health"
    assert result.method == "GET"
    assert result.latency_ms >= 0
    assert result.error_message is None


def test_http_404_connectivity():
    """Verify HTTP response with 404 status still counts as connected but records status."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        runner = ConnectivityRunner(client=client)
        result = runner.test_connectivity("http://testserver/notfound")

    assert result.success is True
    assert result.status_code == 404
    assert result.error_message is None


def test_http_timeout_handling():
    """Verify handling of request timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Simulated timeout", request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        runner = ConnectivityRunner(client=client)
        result = runner.test_connectivity("http://testserver/slow")

    assert result.success is False
    assert result.status_code is None
    assert "timeout" in result.error_message.lower()


def test_http_connection_refused_handling():
    """Verify handling of connection refused/network failure."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        runner = ConnectivityRunner(client=client)
        result = runner.test_connectivity("http://testserver/unreachable")

    assert result.success is False
    assert result.status_code is None
    assert "connection" in result.error_message.lower()
