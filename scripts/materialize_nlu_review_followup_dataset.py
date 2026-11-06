"""Build the reviewed RF corpus without calling a model."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutReviewLedger

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_review_followup_fresh_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_review_followup_field_review.md"
TEMPLATE = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-scope-reviewed.v2.json"
OUTPUT = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-review-followup-ledger.v1.json"
CASE_IDS = tuple(f"RF{number:02}" for number in range(1, 13))
SCENARIOS = {
    "A/S 접수": ("고객센터:a/s 접수", "NS01"),
    "교수님 면담 예약": ("교수님:면담 예약", "NS11"),
}


def _rows(path: Path) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"RF\d{2}", cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate ID in {path}: {cells[0]}")
            rows[cells[0]] = cells
    if tuple(sorted(rows)) != CASE_IDS:
        raise ValueError(f"expected RF01–RF12 exactly once in {path}")
    return rows


def main() -> None:
    if OUTPUT.exists() or LEDGER.exists():
        raise ValueError("reviewed corpus or ledger exists; never overwrite frozen inputs")
    utterances = _rows(REVIEW)
    labels = _rows(FIELDS)
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    template_cases = {case["id"].upper().split("-")[-1]: case for case in template["cases"]}
    cases = []
    for case_id in CASE_IDS:
        row, label_row = utterances[case_id], labels[case_id]
        if len(row) != 5 or len(label_row) != 4:
            raise ValueError(f"malformed review row: {case_id}")
        scenario = SCENARIOS.get(row[1])
        if scenario is None or (case_id <= "RF06") != (row[1] == "A/S 접수"):
            raise ValueError(f"unexpected workflow for {case_id}: {row[1]}")
        scenario_key, template_id = scenario
        old = template_cases[template_id]
        if old["scenario_key"] != scenario_key:
            raise ValueError(f"template workflow mismatch: {case_id}")
        case = old.copy()
        case["id"] = f"nlu-review-followup-{case_id.lower()}"
        case["conversation_group_id"] = case["id"]
        case["user_message"] = row[3]
        action = label_row[2].strip("`")
        direction = row[4].strip("`")
        if (direction == "안전 우선") != (case_id in {"RF01", "RF03", "RF04"}):
            raise ValueError(f"safety direction mismatch: {case_id}")
        if direction != "안전 우선" and direction != action:
            raise ValueError(f"action direction mismatch: {case_id}")
        if action == "unknown":
            case["tags"] = ["hard_negative"]
        elif case_id in {"RF01", "RF03", "RF04"}:
            case["tags"] = ["safety", "multi_field"]
        elif case_id == "RF09":
            case["tags"] = ["single_field"]
        else:
            case["tags"] = ["multi_field"]
        fields = {key: None for key in old["labels"]["fields"]}
        if label_row[3] != "없음":
            for assignment in label_row[3].split("; "):
                key, value = assignment.strip("`").split("=", 1)
                if key not in fields or fields[key] is not None:
                    raise ValueError(f"unknown or duplicate field in {case_id}: {key}")
                fields[key] = {"accepted_values": [value]}
        case["labels"] = {
            "intent": label_row[1].strip("`"),
            "user_action": action,
            "change_field": None,
            "fields": fields,
        }
        cases.append(case)
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
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    ledger = AIHeldoutReviewLedger.model_validate(
        {
            "kind": "ai_authored_heldout_review_v1",
            "reviewed_for": "ai_authored_heldout_accuracy",
            "dataset_sha256": digest,
            "accepted_case_ids": sorted(case.id for case in dataset.cases),
            "adjudicator_id": "portfolio_owner",
            "adjudicated_at": datetime.now(UTC).isoformat(),
            "rationale": (
                "Owner revised RF08 and RF12, accepted all 12 AI-authored utterances "
                "and action directions, then separately accepted every action, "
                "non-null field, null field, and single accepted value on 2026-11-06. "
                "One owner adjudicated; no independent second reviewer."
            ),
        }
    )
    ledger_bytes = (
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    OUTPUT.write_bytes(dataset_bytes)
    LEDGER.write_bytes(ledger_bytes)
    print(f"validated {len(dataset.cases)} cases; dataset sha256 {digest}")


if __name__ == "__main__":
    main()
