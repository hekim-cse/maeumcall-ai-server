"""Build the owner-reviewed SC corpus without calling a model."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutReviewLedger
from services.flow.common.state_contract import SCENARIO_STATE_VERSION
from services.flow.support.contracts import SERVICE_REQUEST_SPEC

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_safety_contract_fresh_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_safety_contract_fresh_field_review.md"
OUTPUT = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-contract-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-contract-ledger.v1.json"
CASE_IDS = tuple(f"SC{number:02}" for number in range(1, 21))


def _rows(path: Path) -> dict[str, list[str]]:
    """Read one review table and require every SC case exactly once."""
    rows: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"SC\d{2}", cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate ID in {path}: {cells[0]}")
            rows[cells[0]] = cells
    if tuple(sorted(rows)) != CASE_IDS:
        raise ValueError(f"expected SC01–SC20 exactly once in {path}")
    return rows


def _write_once(path: Path, data: bytes) -> None:
    """Publish complete bytes without replacing an existing reviewed artifact."""
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temp:
        temp.write(data)
        temp.flush()
        os.fsync(temp.fileno())
        temp_path = Path(temp.name)
    try:
        os.link(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    """Validate owner-reviewed labels and write the dataset plus ledger once."""
    if OUTPUT.exists() or LEDGER.exists():
        raise ValueError("reviewed corpus or ledger already exists; never overwrite frozen inputs")
    utterances = _rows(REVIEW)
    labels = _rows(FIELDS)
    cases = []
    for number, case_id in enumerate(CASE_IDS, start=1):
        row, label_row = utterances[case_id], labels[case_id]
        if len(row) != 4 or len(label_row) != 4:
            raise ValueError(f"malformed review row: {case_id}")
        action = label_row[1].strip("`")
        category = row[1]
        expected_category = (
            "명시적 위험"
            if number <= 4
            else "다른 위험 표현"
            if number <= 8
            else "위험 부정"
            if number <= 12
            else "미확정·가정"
            if number <= 16
            else "범위 밖"
        )
        if category != expected_category:
            raise ValueError(f"category mismatch: {case_id}")
        if (action == "unknown") != (number >= 17):
            raise ValueError(f"action mismatch: {case_id}")
        fields = {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
        if label_row[2] != "없음":
            for assignment in label_row[2].split("; "):
                key, value = assignment.strip("`").split("=", 1)
                if key not in fields or fields[key] is not None:
                    raise ValueError(f"unknown or duplicate field in {case_id}: {key}")
                fields[key] = {"accepted_values": [value]}
        if (fields["safety_status"] == {"accepted_values": ["safety_issue"]}) != (number <= 8):
            raise ValueError(f"safety label mismatch: {case_id}")
        if number >= 17 and any(value is not None for value in fields.values()):
            raise ValueError(f"out-of-scope case has a field: {case_id}")
        case_name = f"nlu-safety-contract-{case_id.lower()}"
        cases.append(
            {
                "id": case_name,
                "conversation_group_id": case_name,
                "split": "test",
                "scenario_key": "고객센터:a/s 접수",
                "conversation_state": "greeting",
                "current_fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
                "offered_alternative_times": [],
                "user_message": row[2],
                "labels": {
                    "intent": SERVICE_REQUEST_SPEC.intent,
                    "user_action": action,
                    "change_field": None,
                    "fields": fields,
                },
                "tags": ["hard_negative"]
                if number >= 17
                else ["safety", "multi_field"]
                if number <= 8
                else ["multi_field"],
                "provenance": "ai_authored",
                "review_status": "adjudicated",
            }
        )
    dataset = AIHeldoutDataset.model_validate(
        {
            "kind": "ai_authored_heldout_dataset_v1",
            "dataset_version": 1,
            "state_contract_version": SCENARIO_STATE_VERSION,
            "declared_model_exposure": "not_run",
            "cases": cases,
        }
    )
    dataset_bytes = (
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    ledger = AIHeldoutReviewLedger.model_validate(
        {
            "kind": "ai_authored_heldout_review_v1",
            "reviewed_for": "ai_authored_heldout_accuracy",
            "dataset_sha256": digest,
            "accepted_case_ids": [case.id for case in dataset.cases],
            "adjudicator_id": "portfolio_owner",
            "adjudicated_at": datetime.now(UTC).isoformat(),
            "rationale": (
                "Owner accepted all 20 AI-authored utterances and safety or scope directions, "
                "then separately accepted every action, non-null field, null field, and "
                "single accepted value on 2026-11-06. One owner adjudicated; no independent second reviewer."
            ),
        }
    )
    ledger_bytes = (
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    _write_once(OUTPUT, dataset_bytes)
    _write_once(LEDGER, ledger_bytes)
    print(f"validated {len(dataset.cases)} cases; dataset sha256 {digest}")


if __name__ == "__main__":
    main()
