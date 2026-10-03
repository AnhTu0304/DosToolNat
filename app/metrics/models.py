"""Data models for request results, load test reports, and experiment records."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
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
    results: List[RequestResult] = Field(default_factory=list, description="Raw request execution results")


class LatencySampleRecord(BaseModel):
    """Fine-grained latency and status record for an individual HTTP request."""

    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    stage_number: int = Field(description="Stage index (1-based)")
    latency_ms: Optional[float] = Field(default=None, description="Request response time in ms")
    status_code: Optional[int] = Field(default=None, description="HTTP response status code")
    success: bool = Field(description="True if 2xx or 3xx response received")
    error_type: Optional[str] = Field(default=None, description="Error classification (timeout, connection_error, http_error)")


class StageMetricsRecord(BaseModel):
    """Summarized metrics for a single stage within an experiment."""

    stage_number: int
    target_rate: float
    actual_rps: float
    concurrency: int
    duration_seconds: float
    total_requests: int
    successful: int
    failed: int
    timeouts: int
    connection_errors: int
    http_2xx: int
    http_3xx: int
    http_4xx: int
    http_5xx: int
    min_latency_ms: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float


class AggregateMetricsRecord(BaseModel):
    """Aggregated outcome metrics across the entire experiment."""

    total_requests: int
    successful: int
    failed: int
    timeouts: int
    connection_errors: int
    http_2xx: int = 0
    http_3xx: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    success_rate: float
    error_rate: float
    average_rps: float = 0.0


class ExperimentResult(BaseModel):
    """Comprehensive structured outcome of an experiment run for reporting and archiving."""

    experiment_id: str = Field(description="Unique sortable experiment identifier")
    scenario_name: str = Field(description="Scenario identifier")
    description: str = Field(default="", description="Scenario description")
    target: str = Field(description="Target endpoint URL")
    method: str = Field(default="GET", description="HTTP method used")
    start_time: str = Field(description="ISO 8601 start timestamp")
    end_time: str = Field(description="ISO 8601 end timestamp")
    total_duration_seconds: float = Field(description="Total experiment runtime in seconds")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Safety and runtime configurations")
    aggregate_metrics: AggregateMetricsRecord = Field(description="Overall aggregate metrics")
    latency_statistics: Dict[str, float] = Field(description="True scenario-level latency percentiles from raw samples")
    stages: List[StageMetricsRecord] = Field(default_factory=list, description="Per-stage metrics")
    latency_samples: List[LatencySampleRecord] = Field(default_factory=list, description="Individual request samples")
