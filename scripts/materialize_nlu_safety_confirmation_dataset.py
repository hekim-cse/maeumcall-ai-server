"""Freeze reviewed CF cases and graph goals without calling a model."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutDataset, AIHeldoutReviewLedger
from scripts.materialize_nlu_safety_postfreeze_dataset import _write_once
from services.flow.common.state_contract import SCENARIO_STATE_VERSION
from services.flow.support.contracts import SERVICE_REQUEST_SPEC

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/portfolio/nlu_safety_confirmation_fresh_review.md"
FIELDS = ROOT / "docs/portfolio/nlu_safety_confirmation_field_review.md"
DATASET = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-confirmation-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-confirmation-ledger.v1.json"
GOALS = ROOT / "evals/structured_nlu/data/ai_heldout/nlu-safety-confirmation-goals.v1.json"
IDS = tuple(f"CF{number:02}" for number in range(1, 33))
EXPECTED_DIRECTIONS = (
    ("현재 A/S 대상의 실제 위험",) * 12
    + (
        "현상은 있으나 위험 여부 미확정",
        "현상은 있으나 위험 여부 미확정",
        "현상은 있으나 위험 여부 미확정",
        "냄새의 출처 미확정",
        "현상은 있으나 위험 여부 미확정",
        "냄새의 출처 미확정",
        "현상은 있으나 위험 여부 미확정",
        "현상은 있으나 위험 여부 미확정",
    )
    + (
        "현재 위험 진술 없음",
        "다른 제품의 위험 경험",
        "가정형 위험 질문",
        "다른 출처의 냄새",
        "온라인 자료의 위험 묘사",
        "원래 형태의 묘사",
        "후기의 위험 묘사",
        "가정형 위험 질문",
        "화면 표시의 비유",
        "다른 출처의 냄새",
        "명시적 위험 부정",
        "그을음이 아닌 외관 자국",
    )
)


def _rows(path: Path) -> dict[str, list[str]]:
    """Read exactly one reviewed row per CF case."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"CF\d{2}", cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate CF ID in {path}: {cells[0]}")
            rows[cells[0]] = cells
    if tuple(sorted(rows)) != IDS:
        raise ValueError(f"expected CF01–CF32 exactly once in {path}")
    return rows


def _publish_unchanged_or_create(path: Path, data: bytes) -> None:
    """Recover a missing artifact while preserving already published bytes."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"existing frozen artifact differs: {path}")
    else:
        _write_once(path, data)


def main() -> None:
    """Validate user-reviewed utterances and labels, then publish immutable inputs."""
    sentences = _rows(REVIEW)
    labels = _rows(FIELDS)
    cases = []
    goals = []
    for number, case_id in enumerate(IDS, start=1):
        utterance, label = sentences[case_id], labels[case_id]
        if len(utterance) != 3 or len(label) != 4:
            raise ValueError(f"malformed CF review row: {case_id}")
        if not utterance[1] or not utterance[2]:
            raise ValueError(f"empty CF utterance or direction: {case_id}")
        action = label[1].strip("`")
        if action not in {"provide_details", "unknown"}:
            raise ValueError(f"unexpected action: {case_id}")
        fields = {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
        entries = re.findall(r"`([^`]+)`", label[2])
        if label[2] != "모두 공란" and not entries:
            raise ValueError(f"missing non-null field values: {case_id}")
        for entry in entries:
            key, value = entry.split("=", 1)
            if key not in fields or fields[key] is not None or not value:
                raise ValueError(f"invalid or duplicate field: {case_id}:{key}")
            fields[key] = {"accepted_values": [value]}
        expected_action = "provide_details" if any(fields.values()) else "unknown"
        if action != expected_action:
            raise ValueError(f"action and fields disagree: {case_id}")
        if utterance[2] != EXPECTED_DIRECTIONS[number - 1]:
            raise ValueError(f"direction differs: {case_id}")
        if number <= 12:
            expected_state = "safety_action_required"
            if fields["safety_status"] != {"accepted_values": ["safety_issue"]}:
                raise ValueError(f"confirmed risk label differs: {case_id}")
        elif number <= 20:
            expected_state = "confirming_safety_status"
            if fields["safety_status"] is not None:
                raise ValueError(f"ambiguous risk must have null safety label: {case_id}")
        else:
            expected_state = "collecting_service_request"
            if fields["safety_status"] == {"accepted_values": ["safety_issue"]}:
                raise ValueError(f"negative risk label differs: {case_id}")
        declared_state = label[3].strip("`")
        if declared_state != ("일반 A/S 경로" if number > 20 else expected_state):
            raise ValueError(f"graph goal differs: {case_id}")
        present_count = sum(value is not None for value in fields.values())
        tags = []
        if present_count == 1:
            tags.append("single_field")
        elif present_count > 1:
            tags.append("multi_field")
        if number <= 12:
            tags.append("safety")
        elif number <= 20:
            tags.append("ambiguous")
        elif action == "unknown":
            tags.append("hard_negative")
        else:
            tags.append("negation")
        case_name = f"nlu-safety-confirmation-{case_id.lower()}"
        cases.append(
            {
                "id": case_name,
                "conversation_group_id": case_name,
                "split": "test",
                "scenario_key": "고객센터:a/s 접수",
                "conversation_state": "greeting",
                "current_fields": {key: None for key in SERVICE_REQUEST_SPEC.field_keys},
                "offered_alternative_times": [],
                "user_message": utterance[1],
                "labels": {
                    "intent": SERVICE_REQUEST_SPEC.intent,
                    "user_action": action,
                    "change_field": None,
                    "fields": fields,
                },
                "tags": tags,
                "provenance": "ai_authored",
                "review_status": "adjudicated",
            }
        )
        goals.append({"case_id": case_name, "expected_state": expected_state})

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
                "Owner separately accepted CF01–CF32 AI-authored utterances and safety directions, "
                "then all actions, field values, null fields, and graph goals on 2026-11-07. "
                "This is a targeted exploratory set with one owner, not the official benchmark."
            ),
        }
    )
    ledger_bytes = (
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    goal_bytes = (
        json.dumps(
            {
                "kind": "ai_authored_safety_confirmation_goals_v1",
                "dataset_sha256": digest,
                "goals": goals,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    if LEDGER.exists() and not DATASET.exists():
        raise ValueError("review ledger exists without dataset")
    if GOALS.exists() and not DATASET.exists():
        raise ValueError("graph goals exist without dataset")
    _publish_unchanged_or_create(DATASET, dataset_bytes)
    if LEDGER.exists():
        previous = AIHeldoutReviewLedger.model_validate_json(LEDGER.read_bytes())
        if previous.dataset_sha256 != digest or previous.accepted_case_ids != tuple(
            case.id for case in dataset.cases
        ):
            raise ValueError("existing review ledger differs from dataset")
    else:
        _write_once(LEDGER, ledger_bytes)
    _publish_unchanged_or_create(GOALS, goal_bytes)
    print(f"validated {len(cases)} cases; dataset sha256 {digest}")


if __name__ == "__main__":
    main()
