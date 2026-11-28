"""Replay the exposed ES catalog with the temporal and multi-event source rules."""

import hashlib
import json
from pathlib import Path

from experiments.as_safety_multi_event_action import DETECTORS as NEW_DETECTORS
from scripts.audit_as_safety_source_selection import DETECTORS, audit

HISTORICAL = Path(__file__).resolve().parents[1] / (
    "evals/structured_nlu/results/as-safety-source-selection-es-development.v1.json"
)
HISTORICAL_SHA256 = "db2cbb9a04f09c44b81c747846557a4083d2f35a567ea6ca00e880464705544b"


def historical_view(result: dict) -> dict:
    return {
        **result,
        "outcomes": {name: result["outcomes"][name] for name in DETECTORS},
        "rows": [
            {**row, "rules": {name: row["rules"][name] for name in DETECTORS}}
            for row in result["rows"]
        ],
    }


def evaluate() -> dict:
    raw = HISTORICAL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HISTORICAL_SHA256:
        raise ValueError("historical ES result changed")
    result = audit(
        DETECTORS
        | {
            "temporal_action": NEW_DETECTORS["baseline"],
            "multi_event_action": NEW_DETECTORS["multi_event"],
        }
    )
    if historical_view(result) != json.loads(raw):
        raise ValueError("historical ES audit was not reproduced")
    return {
        **result,
        "kind": "as_safety_es_multi_event_development_v1",
        "historical_result_sha256": HISTORICAL_SHA256,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
