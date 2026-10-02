"""Tests for ScenarioRunner."""

import asyncio
import httpx
import pytest

from app.scenarios.models import Scenario, ScenarioStage, ScenarioResult
from app.scenarios.runner import ScenarioRunner


@pytest.mark.anyio
async def test_scenario_runner_sequential_execution():
    """Verify ScenarioRunner executes stages sequentially and aggregates totals."""
    call_log = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(request.url.path)
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)

    scenario = Scenario(
        name="test_ramp",
        description="Test sequential ramp",
        target="http://testserver/api",
        method="GET",
        stages=[
            ScenarioStage(rate=10, concurrency=2, duration=0.2),
            ScenarioStage(rate=20, concurrency=4, duration=0.2),
        ],
    )

    started_stages = []
    completed_stages = []

    def on_stage_start(stage_idx: int, stage: ScenarioStage):
        started_stages.append(stage_idx)

    def on_stage_complete(stage_idx: int, stage_result):
        completed_stages.append(stage_idx)

    runner = ScenarioRunner(
        scenario=scenario,
        timeout=2.0,
        transport=transport,
        on_stage_start=on_stage_start,
        on_stage_complete=on_stage_complete,
    )

    result: ScenarioResult = await runner.run()

    assert started_stages == [1, 2]
    assert completed_stages == [1, 2]
    assert len(result.stage_results) == 2
    assert result.scenario_name == "test_ramp"
    assert result.target == "http://testserver/api"
    assert result.total_requests == sum(s.report.total_requests for s in result.stage_results)
    assert result.total_successful == result.total_requests
    assert result.total_failed == 0
    assert result.total_timeouts == 0
    assert result.total_connection_errors == 0
    assert result.total_duration >= 0.35


@pytest.mark.anyio
async def test_scenario_runner_stop_early():
    """Verify ScenarioRunner stops remaining stages when stopped."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(handler)

    scenario = Scenario(
        name="long_scenario",
        description="Multi stage to cancel",
        target="http://testserver/api",
        method="GET",
        stages=[
            ScenarioStage(rate=10, concurrency=2, duration=0.2),
            ScenarioStage(rate=10, concurrency=2, duration=5.0),
            ScenarioStage(rate=10, concurrency=2, duration=5.0),
        ],
    )

    runner = ScenarioRunner(
        scenario=scenario,
        timeout=2.0,
        transport=transport,
    )

    async def cancel_runner():
        await asyncio.sleep(0.3)
        runner.stop()

    asyncio.create_task(cancel_runner())
    result: ScenarioResult = await runner.run()

    # Stage 3 should never have been run
    assert len(result.stage_results) <= 2
