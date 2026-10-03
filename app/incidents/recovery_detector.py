"""Recovery detector implementing configurable criteria evaluation."""

from typing import Optional
from app.incidents.models import RecoveryCriteria


class RecoveryDetector:
    """Evaluates real-time metrics against recovery criteria over consecutive samples."""

    def __init__(self, criteria: RecoveryCriteria, timeout: float = 30.0):
        self.criteria = criteria
        self.timeout = timeout
        self.status = "monitoring"
        self._consecutive_healthy = 0

    @property
    def consecutive_healthy(self) -> int:
        return self._consecutive_healthy

    def evaluate(self, p95_ms: float, error_rate: float) -> bool:
        """Evaluate a sample. Return True if healthy streak satisfies criteria."""
        if self.status == "recovered":
            return True

        is_healthy = (
            p95_ms <= self.criteria.max_p95_ms and
            error_rate <= self.criteria.max_error_rate
        )

        if is_healthy:
            self._consecutive_healthy += 1
            if self._consecutive_healthy >= self.criteria.consecutive_healthy_samples:
                self.status = "recovered"
                return True
        else:
            self._consecutive_healthy = 0

        return False

    def record_timeout(self) -> None:
        """Mark status as recovery_timeout if criteria were not satisfied in time."""
        if self.status != "recovered":
            self.status = "recovery_timeout"

    def record_unrecovered(self) -> None:
        """Mark status as not_recovered if recovery phase ended without satisfaction."""
        if self.status != "recovered":
            self.status = "not_recovered"
