"""Materialize owner-reviewed PF safety cases without a model call."""

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
REVIEW = ROOT / "docs/portfolio/nlu_safety_postfreeze_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_safety_postfreeze_field_review.md"
OUTPUT = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-ledger.v1.json"
CASE_IDS = tuple(f"PF{number:02}" for number in range(1, 17))


def _rows(path: Path) -> dict[str, list[str]]:
    """Read one review table with no duplicate or missing PF IDs."""
    rows: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"PF\d{2}", cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate ID in {path}: {cells[0]}")
            rows[cells[0]] = cells
    if tuple(sorted(rows)) != CASE_IDS:
        raise ValueError(f"expected PF01–PF16 exactly once in {path}")
    return rows


def _write_once(path: Path, data: bytes) -> None:
    """Create a reviewed artifact atomically without replacing prior bytes."""
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
    """Validate reviewed labels, then publish the dataset and review ledger."""
    if LEDGER.exists() and not OUTPUT.exists():
        raise ValueError("review ledger exists without its dataset")
    utterances = _rows(REVIEW)
    labels = _rows(FIELDS)
    cases = []
    for number, case_id in enumerate(CASE_IDS, start=1):
        row, label_row = utterances[case_id], labels[case_id]
        if len(row) != 4 or len(label_row) != 3:
            raise ValueError(f"malformed review row: {case_id}")
        direction = row[3]
        negative_directions = {
            "현재 위험 진술 없음, 일반 A/S",
            "현재 제품의 위험 진술 없음, 일반 A/S",
            "현재 A/S 대상의 위험 진술 없음, 일반 A/S",
            "현재 위험 미확정, 일반 A/S",
        }
        if number <= 8 and direction != "현재 위험 있음, 안전 우선":
            raise ValueError(f"positive safety direction mismatch: {case_id}")
        if number > 8 and direction not in negative_directions:
            raise ValueError(f"negative safety direction mismatch: {case_id}")
        fields = {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
        for assignment in label_row[1].split("; "):
            key, value = assignment.strip("`").split("=", 1)
            if key not in fields or fields[key] is not None:
                raise ValueError(f"unknown or duplicate field in {case_id}: {key}")
            fields[key] = {"accepted_values": [value]}
        if (fields["safety_status"] == {"accepted_values": ["safety_issue"]}) != (number <= 8):
            raise ValueError(f"safety label mismatch: {case_id}")
        expected_goal = "`safety_action_required`" if number <= 8 else "일반 A/S 경로"
        if label_row[2] != expected_goal:
            raise ValueError(f"graph goal mismatch: {case_id}")
        case_name = f"nlu-safety-postfreeze-{case_id.lower()}"
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
                    "user_action": "provide_details",
                    "change_field": None,
                    "fields": fields,
                },
                "tags": ["safety", "multi_field"] if number <= 8 else ["multi_field"],
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
                "Owner accepted PF01–PF16 AI-authored utterances and safety directions, "
                "then separately accepted every action, field value, null field, and graph "
                "goal on 2026-11-07. One owner adjudicated; no independent second reviewer."
            ),
        }
    )
    ledger_bytes = (
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    if OUTPUT.exists():
        if OUTPUT.read_bytes() != dataset_bytes:
            raise ValueError("existing reviewed dataset differs from current input")
    else:
        _write_once(OUTPUT, dataset_bytes)
    if LEDGER.exists():
        frozen_ledger = AIHeldoutReviewLedger.model_validate_json(LEDGER.read_bytes())
        if frozen_ledger.dataset_sha256 != digest or frozen_ledger.accepted_case_ids != tuple(
            case.id for case in dataset.cases
        ):
            raise ValueError("existing review ledger differs from dataset")
    else:
        _write_once(LEDGER, ledger_bytes)
    print(f"validated {len(dataset.cases)} cases; dataset sha256 {digest}")


if __name__ == "__main__":
    main()
