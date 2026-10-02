"""Data models for request results and load test reports."""

from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field


@dataclass
class RequestResult:
    """Outcome of a single HTTP request executed by a worker."""

    timestamp: float
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    success: bool = False
    timeout: bool = False
    connection_error: bool = False
    error_message: Optional[str] = None


class LoadTestReport(BaseModel):
    """Complete summary report of a load test run."""

    target: str = Field(description="Target URL")
    method: str = Field(default="GET", description="HTTP method used")
    requested_rate: float = Field(description="Configured target requests per second")
    actual_rate: float = Field(description="Actual achieved requests per second")
    concurrency: int = Field(description="Maximum concurrency limit")
    duration: float = Field(description="Configured duration in seconds")
    total_requests: int = Field(default=0, description="Total requests dispatched")
    successful_requests: int = Field(default=0, description="Total successful requests (2xx, 3xx)")
    failed_requests: int = Field(default=0, description="Total failed requests (4xx, 5xx, errors)")
    status_2xx: int = Field(default=0, description="Count of 2xx responses")
    status_3xx: int = Field(default=0, description="Count of 3xx responses")
    status_4xx: int = Field(default=0, description="Count of 4xx responses")
    status_5xx: int = Field(default=0, description="Count of 5xx responses")
    timeouts: int = Field(default=0, description="Count of timed out requests")
    connection_errors: int = Field(default=0, description="Count of connection failures")
    min_latency: float = Field(default=0.0, description="Minimum latency in ms")
    max_latency: float = Field(default=0.0, description="Maximum latency in ms")
    average_latency: float = Field(default=0.0, description="Mean latency in ms")
    p50_latency: float = Field(default=0.0, description="50th percentile (median) latency in ms")
    p95_latency: float = Field(default=0.0, description="95th percentile latency in ms")
    p99_latency: float = Field(default=0.0, description="99th percentile latency in ms")
    start_time: float = Field(description="Test start timestamp")
    end_time: float = Field(description="Test completion timestamp")
    elapsed_time: float = Field(description="Total elapsed wall-clock seconds")
