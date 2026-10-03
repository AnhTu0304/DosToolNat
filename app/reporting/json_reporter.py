"""JSON reporter for serializing experiment results."""

import json
from pathlib import Path
from app.metrics.models import ExperimentResult


def write_json_report(experiment: ExperimentResult, output_dir: Path) -> Path:
    """Serialize ExperimentResult to a formatted experiment.json file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_file = output_dir / "experiment.json"

    data = experiment.model_dump(mode="json")
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return target_file
