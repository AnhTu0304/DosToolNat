"""Scenario runner orchestrating sequential execution of multi-stage load scenarios."""

import time
from typing import Callable, List, Optional
import httpx

from app.engine.runner import LoadTestRunner
from app.scenarios.models import Scenario, ScenarioStage, StageResult, ScenarioResult


class ScenarioRunner:
    """Orchestrates sequential execution of stages defined in a Scenario."""

    def __init__(
        self,
        scenario: Scenario,
        timeout: float = 5.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        on_stage_start: Optional[Callable[[int, ScenarioStage], None]] = None,
        on_stage_progress: Optional[Callable[[int, dict, float], None]] = None,
        on_stage_complete: Optional[Callable[[int, StageResult], None]] = None,
    ) -> None:
        self.scenario = scenario
        self.timeout = timeout
        self.transport = transport
        self.on_stage_start = on_stage_start
        self.on_stage_progress = on_stage_progress
        self.on_stage_complete = on_stage_complete

        self._current_runner: Optional[LoadTestRunner] = None
        self._stopped = False

    def stop(self) -> None:
        """Signal the scenario runner to cease executing current and future stages."""
        self._stopped = True
        if self._current_runner:
            self._current_runner.stop()

    async def run(self) -> ScenarioResult:
        """Execute all stages sequentially and return aggregated ScenarioResult."""
        stage_results: List[StageResult] = []
        start_time = time.perf_counter()

        for idx, stage in enumerate(self.scenario.stages, start=1):
            if self._stopped:
                break

            if self.on_stage_start:
                self.on_stage_start(idx, stage)

            def stage_progress_cb(stats: dict, elapsed: float, s_idx: int = idx) -> None:
                if self.on_stage_progress:
                    self.on_stage_progress(s_idx, stats, elapsed)

            self._current_runner = LoadTestRunner(
                target_url=self.scenario.target,
                rate=stage.rate,
                concurrency=stage.concurrency,
                duration=stage.duration,
                timeout=self.timeout,
                transport=self.transport,
                on_progress=stage_progress_cb,
            )

            try:
                report = await self._current_runner.run()
            except Exception:
                if self._stopped:
                    break
                raise

            stage_res = StageResult(stage_index=idx, stage=stage, report=report)
            stage_results.append(stage_res)

            if self.on_stage_complete:
                self.on_stage_complete(idx, stage_res)

            if self._stopped:
                break

        elapsed_total = round(time.perf_counter() - start_time, 2)

        total_requests = sum(s.report.total_requests for s in stage_results)
        total_successful = sum(s.report.successful_requests for s in stage_results)
        total_failed = sum(s.report.failed_requests for s in stage_results)
        total_timeouts = sum(s.report.timeouts for s in stage_results)
        total_connection_errors = sum(s.report.connection_errors for s in stage_results)

        return ScenarioResult(
            scenario_name=self.scenario.name,
            target=self.scenario.target,
            total_duration=elapsed_total,
            stage_results=stage_results,
            total_requests=total_requests,
            total_successful=total_successful,
            total_failed=total_failed,
            total_timeouts=total_timeouts,
            total_connection_errors=total_connection_errors,
        )
