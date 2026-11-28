"""Evaluate the two independent changes on fixed pairs and the exposed ES lattice."""

import hashlib
import json
from pathlib import Path

from experiments.as_safety_pair_evaluation import compare_with_locations, summarize
from experiments.as_safety_wire_coordination import DETECTORS
from scripts.audit_as_safety_source_selection import audit

ROOT = Path(__file__).resolve().parents[1]
KIND = "as_safety_wire_coordination_reviewed_v1"
DATA = ROOT / "evals/structured_nlu/data/ai_heldout/as-safety-wire-coordination-reviewed.v1.json"
DATA_SHA256 = "510b7b06cd41ee1c2b9ed9a93e356164365980fd1a09731146179ea670f50a8c"
PRIOR = ROOT / "evals/structured_nlu/results/as-safety-es-multi-event-development.v1.json"
PRIOR_SHA256 = "5dc37f989c3a7de004e3cff3f10a840190b62a90ccad49147cda026d959685a9"


def read_fixed(path: Path, checksum: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise ValueError(f"fixed input changed: {path.name}")
    return json.loads(raw)


def paired_evaluation() -> dict:
    metadata = read_fixed(DATA, DATA_SHA256)
    result = compare_with_locations(DATA, KIND, DETECTORS)
    if result["input_sha256"] != DATA_SHA256:
        raise ValueError("reviewed input changed during comparison")
    for label in ("other_event_source", "partial_span"):
        ids = metadata[f"{label}_candidates"]
        positives = [row for row in result["rows"] if row["id"] in set(ids)]
        if len(positives) != len(ids) or any(row["gold"] != "abstain" for row in positives):
            raise ValueError(f"{label} must consist of unique abstention labels")
        for name, summary in result["summary"].items():
            summary[f"{label}_total"] = len(positives)
            summary[f"{label}_false_approval"] = sum(row[name] == "approve" for row in positives)
    result["groups"] = {
        prefix: {
            name: summarize([row for row in result["rows"] if row["case"].startswith(prefix)], name)
            for name in DETECTORS
        }
        for prefix in ("WL", "CE", "WC")
    }
    return result


def baseline_projection(report: dict, rule: str) -> dict:
    return {
        "settings": {
            key: report[key]
            for key in (
                "input_sha256",
                "kiwipiepy",
                "kiwipiepy_model",
                "candidate_settings",
                "skipped_nonoccurring",
                "gold_availability",
            )
        },
        "outcomes": report["outcomes"][rule],
        "rows": [
            {
                **{key: value for key, value in row.items() if key != "rules"},
                "decision": row["rules"][rule],
            }
            for row in report["rows"]
        ],
    }


def es_evaluation() -> dict:
    prior = read_fixed(PRIOR, PRIOR_SHA256)
    current = audit(DETECTORS)
    if baseline_projection(current, "baseline") != baseline_projection(prior, "multi_event_action"):
        raise ValueError("prior ES baseline was not reproduced")
    return {
        **current,
        "kind": "as_safety_es_wire_coordination_development_v1",
        "historical_result_sha256": PRIOR_SHA256,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            {"paired": paired_evaluation(), "es": es_evaluation()}, ensure_ascii=False, indent=2
        )
    )
