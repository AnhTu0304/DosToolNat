"""Pydantic data models for Phase 5 Controlled Fault & Incident Injection."""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, model_validator

from app.metrics.models import LatencySampleRecord
from app.scenarios.models import ScenarioStage


class FaultType(str, Enum):
    """Supported fault injection types."""
    LATENCY = "latency"
    HTTP_5XX = "http_5xx"
    COMBINED = "combined"


class FaultConfig(BaseModel):
    """Configuration defining a controlled fault to be injected."""
    type: FaultType = Field(description="Fault classification type")
    duration: float = Field(..., gt=0, le=60, description="Fault duration in seconds")
    delay_ms: Optional[float] = Field(None, ge=0, description="Latency delay in milliseconds")
    error_rate: Optional[float] = Field(None, ge=0.0, le=1.0, description="Ratio of 5xx errors (0.0 to 1.0)")
    target_endpoint: Optional[str] = Field(None, description="Optional dedicated test fault endpoint")

    @model_validator(mode="after")
    def validate_fault_parameters(self) -> "FaultConfig":
        """Ensure parameters match the chosen fault type."""
        if self.type == FaultType.LATENCY:
            if self.delay_ms is None or self.delay_ms <= 0:
                raise ValueError("delay_ms must be provided and greater than 0 for latency fault")
        elif self.type == FaultType.HTTP_5XX:
            if self.error_rate is None or self.error_rate <= 0:
                raise ValueError("error_rate must be provided and greater than 0 for http_5xx fault")
        elif self.type == FaultType.COMBINED:
            if self.delay_ms is None or self.delay_ms <= 0:
                raise ValueError("delay_ms must be provided and greater than 0 for combined fault")
            if self.error_rate is None or self.error_rate <= 0:
                raise ValueError("error_rate must be provided and greater than 0 for combined fault")
        return self


class RecoveryCriteria(BaseModel):
    """Configurable conditions determining when a service has safely recovered."""
    max_p95_ms: float = Field(50.0, ge=0, description="Maximum acceptable P95 latency in ms")
    max_error_rate: float = Field(0.01, ge=0.0, le=1.0, description="Maximum acceptable error rate (0.0 to 1.0)")
    consecutive_healthy_samples: int = Field(3, ge=1, description="Number of consecutive healthy evaluations required")


class RecoveryConfig(BaseModel):
    """Configuration for monitoring service recovery post-fault."""
    enabled: bool = Field(default=True, description="Whether to monitor for recovery")
    criteria: RecoveryCriteria = Field(default_factory=RecoveryCriteria, description="Recovery criteria thresholds")
    timeout: float = Field(default=30.0, gt=0, le=60, description="Max monitoring duration before timing out")


class IncidentLifecycleState(str, Enum):
    """Explicit lifecycle states for reproducible fault experiments."""
    CREATED = "created"
    BASELINE = "baseline"
    LOAD_STARTED = "load_started"
    FAULT_STARTED = "fault_started"
    FAULT_ACTIVE = "fault_active"
    FAULT_ENDED = "fault_ended"
    RECOVERY_STARTED = "recovery_started"
    RECOVERED = "recovered"
    NOT_RECOVERED = "not_recovered"
    RECOVERY_TIMEOUT = "recovery_timeout"
    COMPLETED = "completed"
    FAILED = "failed"


class TimelineEvent(BaseModel):
    """Discrete experiment event recorded in chronological order."""
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    event: str = Field(description="Event name")
    phase: str = Field(description="Experiment phase")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class FaultExecutionRecord(BaseModel):
    """Status and measurement record of the injected fault."""
    fault_type: str = Field(description="Type of fault injected")
    start_time: Optional[str] = Field(None, description="Fault activation start timestamp")
    end_time: Optional[str] = Field(None, description="Fault deactivation timestamp")
    duration_seconds: float = Field(default=0.0, description="Observed fault duration in seconds")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Configuration applied")
    status: str = Field(default="pending", description="Status: completed, failed, interrupted")


class RecoveryExecutionRecord(BaseModel):
    """Measurement and assessment of post-fault recovery."""
    enabled: bool = Field(default=True)
    start_time: Optional[str] = Field(None)
    end_time: Optional[str] = Field(None)
    recovery_duration_seconds: Optional[float] = Field(None, description="Time taken to achieve healthy criteria")
    status: str = Field(default="not_evaluated", description="recovered, not_recovered, recovery_timeout")
    criteria: Dict[str, Any] = Field(default_factory=dict)


class PhaseMetricsSummary(BaseModel):
    """Aggregated metrics for a distinct phase (Baseline, During Fault, Recovery)."""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timeouts: int = 0
    connection_errors: int = 0
    http_2xx: int = 0
    http_3xx: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    average_rps: float = 0.0
    min_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0


class IncidentScenario(BaseModel):
    """Declarative definition of an incident experiment."""
    name: str = Field(..., min_length=1, description="Unique incident scenario name")
    description: str = Field(default="", description="Incident description")
    target: str = Field(..., description="Target URL")
    method: str = Field(default="GET", description="HTTP method")
    baseline: ScenarioStage = Field(..., description="Baseline normal traffic stage")
    fault: FaultConfig = Field(..., description="Fault injection configuration")
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig, description="Recovery monitoring configuration")

    @model_validator(mode="after")
    def validate_safety_boundaries(self) -> "IncidentScenario":
        """Verify total incident experiment duration does not exceed configured safety bounds (60s)."""
        recovery_dur = self.recovery.timeout if self.recovery.enabled else 0.0
        total = self.baseline.duration + self.fault.duration + recovery_dur
        if total > 60.0:
            raise ValueError(
                f"Total experiment duration ({total:.1f}s = baseline {self.baseline.duration:.1f}s + "
                f"fault {self.fault.duration:.1f}s + recovery {recovery_dur:.1f}s) "
                f"exceeds maximum allowed safety limit of 60.0s."
            )
        return self


class IncidentResult(BaseModel):
    """Comprehensive outcome of a Phase 5 incident experiment."""
    experiment_id: str
    experiment_type: str = "incident"
    scenario_name: str
    description: str = ""
    target: str
    method: str = "GET"
    start_time: str
    end_time: str
    total_duration_seconds: float
    lifecycle_state: IncidentLifecycleState
    before_metrics: PhaseMetricsSummary
    during_metrics: PhaseMetricsSummary
    after_metrics: PhaseMetricsSummary
    fault: FaultExecutionRecord
    recovery: RecoveryExecutionRecord
    timeline: List[TimelineEvent] = Field(default_factory=list)
    latency_samples: List[LatencySampleRecord] = Field(default_factory=list)
