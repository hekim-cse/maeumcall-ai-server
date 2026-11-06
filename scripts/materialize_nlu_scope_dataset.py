"""Materialize the owner-reviewed NS corpus from its exact review tables.

Run this before model exposure. The script validates every case against the
live scenario contract and never calls a model.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutReviewLedger

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_scope_fresh_v2_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_scope_fresh_v2_field_review.md"
TEMPLATE = ROOT / "evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json"
OUTPUT = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-scope-reviewed.v2.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-scope-review-ledger.v2.json"


def _table_rows(path: Path) -> dict[str, list[str]]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"NS\d{2}", cells[0]):
            rows[cells[0]] = cells
    if sorted(rows) != [f"NS{n:02}" for n in range(1, 33)]:
        raise ValueError(f"expected NS01–NS32 once in {path}")
    return rows


def main() -> None:
    if OUTPUT.exists() or LEDGER.exists():
        raise ValueError("reviewed corpus or ledger already exists; do not overwrite")
    utterances = _table_rows(REVIEW)
    labels = _table_rows(FIELDS)
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    cases = []
    for number, old in enumerate(template["cases"], start=1):
        case_id = f"NS{number:02}"
        row = utterances[case_id]
        label_row = labels[case_id]
        if len(row) != 4 or len(label_row) != 4:
            raise ValueError(f"malformed review row: {case_id}")
        case = old.copy()
        case["id"] = f"nlu-scope-{case_id.lower()}"
        case["conversation_group_id"] = case["id"]
        case["user_message"] = row[3]
        case["tags"] = ["hard_negative"] if number % 2 == 0 else ["multi_field"]
        expected_direction = "범위 밖" if number % 2 == 0 else "정보 제공"
        if row[2] != expected_direction:
            raise ValueError(f"unexpected direction for {case_id}: {row[2]}")
        fields = {key: None for key in case["labels"]["fields"]}
        if label_row[3] != "없음":
            for field_assignment in label_row[3].split("; "):
                key, value = field_assignment.strip("`").split("=", 1)
                if key not in fields or fields[key] is not None:
                    raise ValueError(f"unknown or duplicate field in {case_id}: {key}")
                fields[key] = {"accepted_values": [value]}
        case["labels"] = {
            "intent": None if label_row[1] == "`null`" else label_row[1].strip("`"),
            "user_action": label_row[2].strip("`"),
            "change_field": None,
            "fields": fields,
        }
        cases.append(case)
    if len(cases) != 32:
        raise ValueError("template must have exactly 32 paired cases")
    dataset = AIHeldoutDataset.model_validate(
        {
            "kind": "ai_authored_heldout_dataset_v1",
            "dataset_version": 1,
            "state_contract_version": template["state_contract_version"],
            "declared_model_exposure": "not_run",
            "cases": cases,
        }
    )
    dataset_bytes = (
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    dataset_sha = hashlib.sha256(dataset_bytes).hexdigest()
    ledger = AIHeldoutReviewLedger.model_validate(
        {
            "kind": "ai_authored_heldout_review_v1",
            "reviewed_for": "ai_authored_heldout_accuracy",
            "dataset_sha256": dataset_sha,
            "accepted_case_ids": sorted(case.id for case in dataset.cases),
            "adjudicator_id": "portfolio_owner",
            "adjudicated_at": datetime.now(UTC).isoformat(),
            "rationale": (
                "Owner accepted all 32 AI-authored NS utterances and in/out-scope "
                "directions, then accepted every action, non-null field, null field, "
                "and single accepted value in the separate review table on "
                "2026-11-06. One owner adjudicated; no independent second reviewer."
            ),
        }
    )
    ledger_bytes = (
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    OUTPUT.write_bytes(dataset_bytes)
    LEDGER.write_bytes(ledger_bytes)
    print(f"validated {len(dataset.cases)} cases; dataset sha256 {dataset_sha}")


if __name__ == "__main__":
    main()
