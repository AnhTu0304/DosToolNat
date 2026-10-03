"""Incident scenario discovery, file reading, and schema validation."""

from pathlib import Path
from typing import Any, Dict, List, Union
import yaml
from pydantic import ValidationError

from app.incidents.models import IncidentScenario


def load_incident(
    path_or_name: Union[str, Path],
    scenarios_dir: Path = Path("scenarios"),
) -> IncidentScenario:
    """Load, parse, and validate an IncidentScenario from a YAML file path or scenario name."""
    candidate_path = Path(path_or_name)

    if candidate_path.is_file():
        target_file = candidate_path
    else:
        name_str = str(path_or_name).strip()
        yaml_file = scenarios_dir / f"{name_str}.yaml"
        yml_file = scenarios_dir / f"{name_str}.yml"

        if yaml_file.is_file():
            target_file = yaml_file
        elif yml_file.is_file():
            target_file = yml_file
        else:
            raise FileNotFoundError(f"Incident scenario not found: {path_or_name}")

    with target_file.open("r", encoding="utf-8") as f:
        try:
            raw_data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML format in incident file '{target_file}': {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError(f"Invalid incident configuration in '{target_file}': root must be a mapping")

    if "fault" not in raw_data:
        raise ValueError(f"File '{target_file}' is not an incident scenario (missing 'fault' configuration)")

    try:
        return IncidentScenario.model_validate(raw_data)
    except ValidationError as exc:
        raise ValueError(f"Invalid incident configuration in '{target_file}': {exc}") from exc


def list_incidents(scenarios_dir: Path = Path("scenarios")) -> List[Dict[str, Any]]:
    """Scan scenarios directory for available YAML incident scenarios."""
    scenarios_dir = Path(scenarios_dir)
    if not scenarios_dir.is_dir():
        return []

    available: List[Dict[str, Any]] = []
    files = sorted(list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml")))

    for f in files:
        try:
            with f.open("r", encoding="utf-8") as stream:
                data = yaml.safe_load(stream)
                if isinstance(data, dict) and "fault" in data:
                    available.append({
                        "name": data.get("name", f.stem),
                        "description": data.get("description", ""),
                        "target": data.get("target", "N/A"),
                        "fault_type": data.get("fault", {}).get("type", "unknown") if isinstance(data.get("fault"), dict) else "unknown",
                        "path": f,
                    })
        except Exception:
            continue

    return available
