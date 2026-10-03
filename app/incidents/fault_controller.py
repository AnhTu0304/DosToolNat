"""Fault controller abstractions for controlled and safe test fault injection."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from app.incidents.models import FaultConfig, FaultType


class BaseFaultController(ABC):
    """Abstract interface for managing fault injection lifecycle."""

    @abstractmethod
    async def activate(self) -> None:
        """Activate the fault."""
        pass

    @abstractmethod
    async def deactivate(self) -> None:
        """Deactivate the fault and perform cleanup."""
        pass

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Return True if fault is currently active."""
        pass

    @abstractmethod
    def get_request_headers(self) -> Dict[str, str]:
        """Headers to be appended to outgoing load requests while fault is active."""
        pass


class HeaderFaultController(BaseFaultController):
    """Fault controller that injects explicit test instruction headers into requests."""

    def __init__(self, config: FaultConfig):
        self.config = config
        self._active = False

    async def activate(self) -> None:
        self._active = True

    async def deactivate(self) -> None:
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def get_request_headers(self) -> Dict[str, str]:
        """Generate headers instructing test servers/proxies to simulate the designated fault."""
        if not self._active:
            return {}

        headers: Dict[str, str] = {
            "X-Test-Fault-Type": self.config.type.value,
        }

        if self.config.type == FaultType.LATENCY:
            headers["X-Test-Fault-Delay-Ms"] = str(self.config.delay_ms)
        elif self.config.type == FaultType.HTTP_5XX:
            headers["X-Test-Fault-Error-Rate"] = str(self.config.error_rate)
        elif self.config.type == FaultType.COMBINED:
            headers["X-Test-Fault-Delay-Ms"] = str(self.config.delay_ms)
            headers["X-Test-Fault-Error-Rate"] = str(self.config.error_rate)

        return headers


class EndpointFaultController(BaseFaultController):
    """Fault controller interacting with a dedicated test mock control API."""

    def __init__(self, config: FaultConfig, control_client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self.client = control_client or httpx.AsyncClient(timeout=5.0)
        self._active = False

    async def activate(self) -> None:
        if self.config.target_endpoint:
            payload = {
                "fault_type": self.config.type.value,
                "delay_ms": self.config.delay_ms,
                "error_rate": self.config.error_rate,
            }
            try:
                await self.client.post(self.config.target_endpoint, json=payload)
            except Exception:
                pass  # Non-blocking fallback to header injection
        self._active = True

    async def deactivate(self) -> None:
        if self.config.target_endpoint and self._active:
            try:
                await self.client.post(f"{self.config.target_endpoint}/reset")
            except Exception:
                pass
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def get_request_headers(self) -> Dict[str, str]:
        if not self._active:
            return {}
        return {
            "X-Test-Fault-Type": self.config.type.value,
            "X-Test-Fault-Delay-Ms": str(self.config.delay_ms or 0),
            "X-Test-Fault-Error-Rate": str(self.config.error_rate or 0),
        }
