"""Data models for load test scenarios and results."""

from dataclasses import dataclass
from typing import List, Literal
from pydantic import BaseModel, Field

from app.metrics.models import LoadTestReport


class ScenarioStage(BaseModel):
    """Configuration for an individual stage in a multi-stage scenario."""

    rate: float = Field(gt=0, description="Target request rate in requests/sec")
    concurrency: int = Field(gt=0, description="Maximum concurrent requests")
    duration: float = Field(gt=0, description="Stage duration in seconds")


class Scenario(BaseModel):
    """Declarative definition of a multi-stage load testing scenario."""

    name: str = Field(min_length=1, description="Scenario identifier")
    description: str = Field(default="", description="Human-readable description")
    target: str = Field(min_length=1, description="Target URL")
    method: Literal["GET"] = Field(default="GET", description="HTTP method (only GET permitted)")
    stages: List[ScenarioStage] = Field(min_length=1, description="Sequential stages of the scenario")

    @property
    def total_duration(self) -> float:
        """Calculate the total duration across all sequential stages."""
        return sum(stage.duration for stage in self.stages)


@dataclass
class StageResult:
    """Execution outcome for a single stage within a scenario."""

    stage_index: int
    stage: ScenarioStage
    report: LoadTestReport


class ScenarioResult(BaseModel):
    """Complete aggregated outcome of an entire multi-stage scenario run."""

    scenario_name: str
    target: str
    total_duration: float
    stage_results: List[StageResult]
    total_requests: int
    total_successful: int
    total_failed: int
    total_timeouts: int
    total_connection_errors: int
