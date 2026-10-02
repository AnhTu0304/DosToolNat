"""Tests for Scenario models, YAML loader, and safety validation."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.config import AppConfig
from app.safety.controller import SafetyController, SafetyValidationError
from app.scenarios.models import Scenario, ScenarioStage
from app.scenarios.loader import load_scenario, list_scenarios


@pytest.fixture
def sample_scenario_yaml(tmp_path):
    yaml_content = """
name: test_scenario
description: A controlled test scenario
target: http://localhost:5000/api/products
method: GET
stages:
  - rate: 5
    concurrency: 2
    duration: 10
  - rate: 10
    concurrency: 5
    duration: 15
"""
    file_path = tmp_path / "test_scenario.yaml"
    file_path.write_text(yaml_content, encoding="utf-8")
    return file_path


def test_scenario_yaml_loading(sample_scenario_yaml):
    """Verify loading and parsing a valid scenario YAML file."""
    scenario = load_scenario(sample_scenario_yaml)
    assert scenario.name == "test_scenario"
    assert scenario.description == "A controlled test scenario"
    assert scenario.target == "http://localhost:5000/api/products"
    assert scenario.method == "GET"
    assert len(scenario.stages) == 2
    assert scenario.stages[0].rate == 5.0
    assert scenario.stages[0].concurrency == 2
    assert scenario.stages[0].duration == 10.0
    assert scenario.stages[1].rate == 10.0
    assert scenario.stages[1].concurrency == 5
    assert scenario.stages[1].duration == 15.0
    assert scenario.total_duration == 25.0


def test_scenario_validation_empty_name():
    """Verify rejection of empty scenario name."""
    with pytest.raises(ValidationError):
        Scenario(
            name="",
            target="http://localhost:3000",
            method="GET",
            stages=[ScenarioStage(rate=1, concurrency=1, duration=10)],
        )


def test_invalid_method():
    """Verify rejection of non-GET methods."""
    with pytest.raises(ValidationError):
        Scenario(
            name="invalid_method_test",
            target="http://localhost:3000",
            method="POST",  # Must be GET only
            stages=[ScenarioStage(rate=1, concurrency=1, duration=10)],
        )


def test_empty_stages():
    """Verify rejection of empty stages list."""
    with pytest.raises(ValidationError):
        Scenario(
            name="no_stages",
            target="http://localhost:3000",
            method="GET",
            stages=[],
        )


@pytest.mark.parametrize(
    "rate,concurrency,duration",
    [
        (0, 1, 10),
        (-5, 1, 10),
        (5, 0, 10),
        (5, -2, 10),
        (5, 1, 0),
        (5, 1, -10),
    ],
)
def test_invalid_stage_parameters(rate, concurrency, duration):
    """Verify rejection of non-positive stage parameters."""
    with pytest.raises(ValidationError):
        ScenarioStage(rate=rate, concurrency=concurrency, duration=duration)


def test_stage_safety_validation():
    """Verify SafetyController rejects stages that violate safety thresholds."""
    config = AppConfig(
        max_request_rate=100,
        max_concurrency=20,
        max_test_duration=60,
    )
    controller = SafetyController(config)

    # Rate too high
    scenario_high_rate = Scenario(
        name="high_rate",
        target="http://localhost:3000",
        method="GET",
        stages=[ScenarioStage(rate=500, concurrency=5, duration=10)],
    )
    with pytest.raises(SafetyValidationError, match="Requested rate"):
        controller.validate_scenario(scenario_high_rate)

    # Concurrency too high
    scenario_high_concurrency = Scenario(
        name="high_concurrency",
        target="http://localhost:3000",
        method="GET",
        stages=[ScenarioStage(rate=10, concurrency=50, duration=10)],
    )
    with pytest.raises(SafetyValidationError, match="Requested concurrency"):
        controller.validate_scenario(scenario_high_concurrency)


def test_total_scenario_duration_validation():
    """Verify SafetyController enforces cumulative duration across all stages."""
    config = AppConfig(
        max_request_rate=100,
        max_concurrency=20,
        max_test_duration=60,  # Max allowed total is 60s
    )
    controller = SafetyController(config)

    # 4 stages of 20s = 80s total > 60s max
    scenario_long_total = Scenario(
        name="long_scenario",
        target="http://localhost:3000",
        method="GET",
        stages=[
            ScenarioStage(rate=2, concurrency=1, duration=20),
            ScenarioStage(rate=2, concurrency=1, duration=20),
            ScenarioStage(rate=2, concurrency=1, duration=20),
            ScenarioStage(rate=2, concurrency=1, duration=20),
        ],
    )
    with pytest.raises(SafetyValidationError, match="Total scenario duration"):
        controller.validate_scenario(scenario_long_total)


def test_scenario_list(tmp_path):
    """Verify listing scenarios from a directory."""
    (tmp_path / "scen1.yaml").write_text("name: scen1\ntarget: http://localhost:3000\nmethod: GET\nstages:\n  - rate: 1\n    concurrency: 1\n    duration: 5", encoding="utf-8")
    (tmp_path / "scen2.yml").write_text("name: scen2\ntarget: http://localhost:3000\nmethod: GET\nstages:\n  - rate: 1\n    concurrency: 1\n    duration: 5", encoding="utf-8")
    (tmp_path / "not_a_scenario.txt").write_text("random text", encoding="utf-8")

    scenarios = list_scenarios(tmp_path)
    names = [s["name"] for s in scenarios if "name" in s]
    assert "scen1" in names
    assert "scen2" in names
    assert len(scenarios) == 2


def test_scenario_not_found(tmp_path):
    """Verify FileNotFoundError when scenario does not exist."""
    with pytest.raises(FileNotFoundError, match="Scenario not found"):
        load_scenario("non_existent_scenario", scenarios_dir=tmp_path)
