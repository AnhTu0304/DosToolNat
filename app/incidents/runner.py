"""Incident runner orchestrating baseline, fault injection, and recovery monitoring."""

import asyncio
from datetime import datetime, timezone
import time
from typing import Callable, List, Optional, Dict, Any
import httpx

from app.engine.runner import LoadTestRunner
from app.incidents.fault_controller import BaseFaultController, HeaderFaultController
from app.incidents.models import (
    IncidentScenario,
    IncidentResult,
    IncidentLifecycleState,
    TimelineEvent,
    PhaseMetricsSummary,
    FaultExecutionRecord,
    RecoveryExecutionRecord,
)
from app.incidents.recovery_detector import RecoveryDetector
from app.metrics.models import LatencySampleRecord, LoadTestReport
from app.metrics.statistics import (
    calculate_success_rate,
    calculate_error_rate,
    calculate_latency_summary,
)


def _build_phase_summary(report: LoadTestReport) -> PhaseMetricsSummary:
    """Helper to convert LoadTestReport into PhaseMetricsSummary."""
    lats = [r.latency_ms for r in report.results if r.latency_ms is not None]
    stats = calculate_latency_summary(lats)

    succ_rate = calculate_success_rate(report.successful_requests, report.total_requests)
    err_rate = calculate_error_rate(report.failed_requests, report.total_requests)

    return PhaseMetricsSummary(
        total_requests=report.total_requests,
        successful=report.successful_requests,
        failed=report.failed_requests,
        timeouts=report.timeouts,
        connection_errors=report.connection_errors,
        http_2xx=report.status_2xx,
        http_3xx=report.status_3xx,
        http_4xx=report.status_4xx,
        http_5xx=report.status_5xx,
        average_rps=report.actual_rate,
        min_latency_ms=stats["min"],
        avg_latency_ms=stats["average"],
        p50_latency_ms=stats["p50"],
        p90_latency_ms=stats.get("p90", stats["p95"]),
        p95_latency_ms=stats["p95"],
        p99_latency_ms=stats["p99"],
        max_latency_ms=stats["max"],
        success_rate=succ_rate,
        error_rate=err_rate,
    )


class IncidentRunner:
    """Orchestrates the entire lifecycle of a controlled incident experiment."""

    def __init__(
        self,
        scenario: IncidentScenario,
        timeout: float = 5.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        fault_controller: Optional[BaseFaultController] = None,
        on_event: Optional[Callable[[TimelineEvent], None]] = None,
        on_progress: Optional[Callable[[str, dict, float], None]] = None,
    ) -> None:
        self.scenario = scenario
        self.timeout = timeout
        self.transport = transport
        self.fault_controller = fault_controller or HeaderFaultController(scenario.fault)
        self.on_event = on_event
        self.on_progress = on_progress

        self.recovery_detector: Optional[RecoveryDetector] = None
        if scenario.recovery.enabled:
            self.recovery_detector = RecoveryDetector(
                criteria=scenario.recovery.criteria,
                timeout=scenario.recovery.timeout,
            )

        self.timeline: List[TimelineEvent] = []
        self.lifecycle_state = IncidentLifecycleState.CREATED
        self._stopped = False
        self._current_runner: Optional[LoadTestRunner] = None

    def _record_event(self, event: str, phase: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Create and append an ISO 8601 UTC chronological timeline event."""
        now_iso = datetime.now(timezone.utc).isoformat()
        evt = TimelineEvent(
            timestamp=now_iso,
            event=event,
            phase=phase,
            details=details or {},
        )
        self.timeline.append(evt)
        if self.on_event:
            self.on_event(evt)

    def stop(self) -> None:
        """Interrupt and cease the experiment, ensuring fault deactivation."""
        self._stopped = True
        if self._current_runner:
            self._current_runner.stop()

    async def run(self) -> IncidentResult:
        """Execute the incident lifecycle with guaranteed fault deactivation and cleanup."""
        start_time_iso = datetime.now(timezone.utc).isoformat()
        exp_start_perf = time.perf_counter()

        self._record_event("experiment_started", "init")

        baseline_report: Optional[LoadTestReport] = None
        fault_report: Optional[LoadTestReport] = None
        recovery_report: Optional[LoadTestReport] = None

        fault_start_time_iso: Optional[str] = None
        fault_end_time_iso: Optional[str] = None
        fault_duration_actual: float = 0.0

        recovery_start_time_iso: Optional[str] = None
        recovery_end_time_iso: Optional[str] = None
        recovery_duration_actual: Optional[float] = None
        recovery_status = "disabled" if not self.scenario.recovery.enabled else "not_evaluated"

        all_latency_samples: List[LatencySampleRecord] = []

        try:
            # 1. BASELINE PHASE
            if not self._stopped:
                self.lifecycle_state = IncidentLifecycleState.BASELINE
                self._record_event("baseline_started", "baseline")

                self._current_runner = LoadTestRunner(
                    target_url=self.scenario.target,
                    rate=self.scenario.baseline.rate,
                    concurrency=self.scenario.baseline.concurrency,
                    duration=self.scenario.baseline.duration,
                    timeout=self.timeout,
                    transport=self.transport,
                )
                baseline_report = await self._current_runner.run()

                # Collect baseline samples
                for req in baseline_report.results:
                    ts = datetime.fromtimestamp(req.timestamp, tz=timezone.utc).isoformat() if isinstance(req.timestamp, (int, float)) else str(req.timestamp)
                    err_type = "timeout" if req.timeout else ("connection_error" if req.connection_error else ("http_error" if req.status_code and req.status_code >= 400 else None))
                    all_latency_samples.append(
                        LatencySampleRecord(
                            timestamp=ts,
                            stage_number=1,
                            latency_ms=req.latency_ms,
                            status_code=req.status_code,
                            success=req.success,
                            error_type=err_type,
                        )
                    )

                self._record_event("baseline_completed", "baseline", {
                    "total_requests": baseline_report.total_requests,
                    "successful": baseline_report.successful_requests,
                })

            # 2. FAULT INJECTION PHASE
            if not self._stopped:
                self.lifecycle_state = IncidentLifecycleState.FAULT_STARTED
                self._record_event("fault_started", "fault", {
                    "fault_type": self.scenario.fault.type.value,
                    "duration": self.scenario.fault.duration,
                })

                await self.fault_controller.activate()
                self.lifecycle_state = IncidentLifecycleState.FAULT_ACTIVE
                fault_start_time_iso = datetime.now(timezone.utc).isoformat()
                fault_start_perf = time.perf_counter()

                fault_headers = self.fault_controller.get_request_headers()

                self._current_runner = LoadTestRunner(
                    target_url=self.scenario.target,
                    rate=self.scenario.baseline.rate,
                    concurrency=self.scenario.baseline.concurrency,
                    duration=self.scenario.fault.duration,
                    timeout=self.timeout,
                    headers=fault_headers,
                    transport=self.transport,
                )
                fault_report = await self._current_runner.run()

                # Always deactivate fault immediately
                await self.fault_controller.deactivate()
                fault_end_time_iso = datetime.now(timezone.utc).isoformat()
                fault_duration_actual = round(time.perf_counter() - fault_start_perf, 2)
                self.lifecycle_state = IncidentLifecycleState.FAULT_ENDED
                self._record_event("fault_ended", "fault", {
                    "duration": fault_duration_actual,
                })

                # Collect fault samples
                for req in fault_report.results:
                    ts = datetime.fromtimestamp(req.timestamp, tz=timezone.utc).isoformat() if isinstance(req.timestamp, (int, float)) else str(req.timestamp)
                    err_type = "timeout" if req.timeout else ("connection_error" if req.connection_error else ("http_error" if req.status_code and req.status_code >= 400 else None))
                    all_latency_samples.append(
                        LatencySampleRecord(
                            timestamp=ts,
                            stage_number=2,
                            latency_ms=req.latency_ms,
                            status_code=req.status_code,
                            success=req.success,
                            error_type=err_type,
                        )
                    )

            # 3. RECOVERY MONITORING PHASE
            if not self._stopped and self.scenario.recovery.enabled and self.recovery_detector:
                self.lifecycle_state = IncidentLifecycleState.RECOVERY_STARTED
                recovery_start_time_iso = datetime.now(timezone.utc).isoformat()
                recovery_start_perf = time.perf_counter()
                self._record_event("recovery_started", "recovery")

                # Run recovery load in 1-second evaluation windows until recovered or timeout
                recovery_results_list = []
                recovered = False
                remaining_time = self.scenario.recovery.timeout

                while remaining_time > 0 and not self._stopped:
                    window_duration = min(1.0, remaining_time)
                    self._current_runner = LoadTestRunner(
                        target_url=self.scenario.target,
                        rate=self.scenario.baseline.rate,
                        concurrency=self.scenario.baseline.concurrency,
                        duration=window_duration,
                        timeout=self.timeout,
                        transport=self.transport,
                    )
                    window_report = await self._current_runner.run()
                    recovery_results_list.extend(window_report.results)

                    w_lats = [r.latency_ms for r in window_report.results if r.latency_ms is not None]
                    w_stats = calculate_latency_summary(w_lats)
                    w_err_rate = calculate_error_rate(window_report.failed_requests, window_report.total_requests)

                    recovered = self.recovery_detector.evaluate(
                        p95_ms=w_stats["p95"],
                        error_rate=w_err_rate / 100.0,
                    )

                    remaining_time -= window_duration

                    if recovered:
                        recovery_end_time_iso = datetime.now(timezone.utc).isoformat()
                        recovery_duration_actual = round(time.perf_counter() - recovery_start_perf, 2)
                        self.lifecycle_state = IncidentLifecycleState.RECOVERED
                        recovery_status = "recovered"
                        self._record_event("recovered", "recovery", {
                            "recovery_duration": recovery_duration_actual,
                        })
                        break

                if not recovered:
                    recovery_end_time_iso = datetime.now(timezone.utc).isoformat()
                    recovery_duration_actual = round(time.perf_counter() - recovery_start_perf, 2)
                    self.recovery_detector.record_timeout()
                    self.lifecycle_state = IncidentLifecycleState.RECOVERY_TIMEOUT
                    recovery_status = "recovery_timeout"
                    self._record_event("recovery_timeout", "recovery")

                # Consolidate recovery report
                from app.metrics.collector import MetricsCollector
                rec_collector = MetricsCollector(
                    target=self.scenario.target,
                    requested_rate=self.scenario.baseline.rate,
                    concurrency=self.scenario.baseline.concurrency,
                    duration=recovery_duration_actual,
                )
                for r in recovery_results_list:
                    rec_collector.add_result(r)
                recovery_report = rec_collector.build_report(
                    start_time=time.time() - (recovery_duration_actual or 0),
                    end_time=time.time(),
                )

                # Collect recovery samples
                for req in recovery_report.results:
                    ts = datetime.fromtimestamp(req.timestamp, tz=timezone.utc).isoformat() if isinstance(req.timestamp, (int, float)) else str(req.timestamp)
                    err_type = "timeout" if req.timeout else ("connection_error" if req.connection_error else ("http_error" if req.status_code and req.status_code >= 400 else None))
                    all_latency_samples.append(
                        LatencySampleRecord(
                            timestamp=ts,
                            stage_number=3,
                            latency_ms=req.latency_ms,
                            status_code=req.status_code,
                            success=req.success,
                            error_type=err_type,
                        )
                    )

            self.lifecycle_state = IncidentLifecycleState.COMPLETED
            self._record_event("experiment_completed", "completed")

        finally:
            # Absolute safety guarantee: ensure fault deactivation
            if self.fault_controller.is_active:
                await self.fault_controller.deactivate()

        end_time_iso = datetime.now(timezone.utc).isoformat()
        total_dur = round(time.perf_counter() - exp_start_perf, 2)

        # Fallbacks for empty reports
        empty_report = LoadTestReport(
            target=self.scenario.target,
            method="GET",
            requested_rate=0.0,
            actual_rate=0.0,
            concurrency=1,
            duration=0.0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            start_time=0.0,
            end_time=0.0,
            elapsed_time=0.0,
        )

        before_summary = _build_phase_summary(baseline_report or empty_report)
        during_summary = _build_phase_summary(fault_report or empty_report)
        after_summary = _build_phase_summary(recovery_report or empty_report)

        fault_record = FaultExecutionRecord(
            fault_type=self.scenario.fault.type.value,
            start_time=fault_start_time_iso,
            end_time=fault_end_time_iso,
            duration_seconds=fault_duration_actual,
            configuration=self.scenario.fault.model_dump(mode="json"),
            status="completed" if fault_report else "failed",
        )

        recovery_record = RecoveryExecutionRecord(
            enabled=self.scenario.recovery.enabled,
            start_time=recovery_start_time_iso,
            end_time=recovery_end_time_iso,
            recovery_duration_seconds=recovery_duration_actual,
            status=recovery_status,
            criteria=self.scenario.recovery.criteria.model_dump(mode="json") if self.scenario.recovery.enabled else {},
        )

        from app.reporting.recorder import generate_experiment_id
        exp_id = generate_experiment_id(self.scenario.name)

        return IncidentResult(
            experiment_id=exp_id,
            scenario_name=self.scenario.name,
            description=self.scenario.description,
            target=self.scenario.target,
            method=self.scenario.method,
            start_time=start_time_iso,
            end_time=end_time_iso,
            total_duration_seconds=total_dur,
            lifecycle_state=self.lifecycle_state,
            before_metrics=before_summary,
            during_metrics=during_summary,
            after_metrics=after_summary,
            fault=fault_record,
            recovery=recovery_record,
            timeline=self.timeline,
            latency_samples=all_latency_samples,
        )
