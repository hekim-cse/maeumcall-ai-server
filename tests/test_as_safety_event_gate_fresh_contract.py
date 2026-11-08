"""Fresh safety exploration must require reviewed input and reject changed artifacts."""

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts.audit_as_safety_event_gate_fresh import SOURCES, audit
from scripts.run_as_safety_event_gate_fresh import load_reviewed_cases, summarize
from scripts.verify_as_safety_event_gate_fresh import verify


def _case(number: int) -> dict[str, str]:
    return {
        "id": f"EG{number:02}",
        "user_message": f"제품 {number}의 버튼을 확인하고 싶습니다.",
        "expected_route": (
            "safety_action_required"
            if number <= 8
            else "confirming_safety_status"
            if number <= 16
            else "collecting_service_request"
        ),
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_ai_reviewed_v1",
                "provenance": "ai_authored",
                "review_status": "owner_approved_for_exploration",
                "cases": [_case(number) for number in range(1, 33)],
            },
            ensure_ascii=False,
        )
    )
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_fresh_protocol_v1",
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            }
        )
    )
    rows = [
        {
            "case_id": f"EG{number:02}",
            "clause_count": 1,
            "evidence_index": None,
            "target": "none",
            "assertion": "none",
            "model_route": "collecting_service_request",
            "gate_route": "collecting_service_request",
            "gate_reason": "model_route_unchanged",
            "error_type": None,
            "latency_ms": 1.0,
        }
        for number in range(1, 33)
    ]
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "kind": "as_safety_event_gate_fresh_result_v1",
                "claim_scope": "ai_authored_owner_reviewed_targeted_exploration",
                "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "summary": summarize([_case(number) for number in range(1, 33)], rows),
                "rows": rows,
            }
        )
    )
    return dataset, protocol, result


def test_reviewed_dataset_and_result_contract_accept_consistent_artifact(tmp_path: Path) -> None:
    dataset, protocol, result = _fixture(tmp_path)
    cases, digest = load_reviewed_cases(dataset)
    assert len(cases) == 32
    assert digest == hashlib.sha256(dataset.read_bytes()).hexdigest()
    verify(dataset, protocol, result)


def test_owner_accepted_eg_input_matches_review_document() -> None:
    reviewed = Path(
        "evals/structured_nlu/data/ai_heldout/as-safety-event-gate-fresh-reviewed.v1.json"
    )
    cases, _ = load_reviewed_cases(reviewed)
    document = Path("docs/portfolio/nlu_safety_event_gate_fresh_review.md").read_text()
    assert "EG01–EG32 전체를 탐색용으로 채택" in document
    pattern = re.compile(r"^\| (EG\d{2}) \| (.*?) \| (.*?) \| (.*?) \|$")
    route_names = {
        "즉시 대응": "safety_action_required",
        "안전 확인": "confirming_safety_status",
        "일반 수집": "collecting_service_request",
    }
    from_document = [
        {
            "id": match.group(1),
            "user_message": match.group(2),
            "expected_route": route_names[match.group(4)],
        }
        for line in document.splitlines()
        if (match := pattern.match(line))
    ]
    assert cases == from_document


def test_frozen_eg_result_recalculates_and_preserves_failure_counts() -> None:
    root = Path("evals/structured_nlu/data/ai_heldout")
    result_path = root / "as-safety-event-gate-fresh-result.v1.json"
    verify(
        root / "as-safety-event-gate-fresh-reviewed.v1.json",
        root / "as-safety-event-gate-fresh-protocol.v1.json",
        result_path,
    )
    result = json.loads(result_path.read_text())
    assert [row["case_id"] for row in result["rows"] if row["error_type"] is not None] == [
        "EG26",
        "EG27",
        "EG31",
        "EG32",
    ]
    assert result["summary"] == {
        "confirmed_hazard": {
            "denominator": 8,
            "model_direct": 8,
            "gate_direct": 3,
            "gate_confirmation": 5,
            "gate_normal": 0,
            "errors": 0,
        },
        "ambiguous_hazard": {
            "denominator": 8,
            "model_direct": 0,
            "gate_direct": 0,
            "gate_confirmation": 7,
            "gate_normal": 1,
            "errors": 0,
        },
        "other_source": {
            "denominator": 8,
            "model_direct": 2,
            "gate_direct": 0,
            "gate_confirmation": 2,
            "gate_normal": 6,
            "errors": 0,
        },
        "nonoccurring_hazard": {
            "denominator": 8,
            "model_direct": 3,
            "gate_direct": 0,
            "gate_confirmation": 3,
            "gate_normal": 1,
            "errors": 4,
        },
    }


@pytest.mark.parametrize(
    "change",
    ["unreviewed", "duplicate_id", "unknown_route", "extra_case_field", "blank_message"],
)
def test_reviewed_dataset_rejects_invalid_inputs(tmp_path: Path, change: str) -> None:
    dataset, _, _ = _fixture(tmp_path)
    payload = json.loads(dataset.read_text())
    if change == "unreviewed":
        payload["review_status"] = "draft"
    elif change == "duplicate_id":
        payload["cases"][1]["id"] = "EG01"
    elif change == "unknown_route":
        payload["cases"][0]["expected_route"] = "unknown"
    elif change == "blank_message":
        payload["cases"][0]["user_message"] = "   "
    else:
        payload["cases"][0]["raw_model_response"] = "should not exist"
    dataset.write_text(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(ValueError):
        load_reviewed_cases(dataset)


@pytest.mark.parametrize(
    "change",
    [
        "raw_text",
        "bad_index",
        "bad_route",
        "bad_target",
        "bad_assertion",
        "bad_summary",
        "infinite_latency",
        "bad_digest",
    ],
)
def test_fresh_verifier_rejects_mutated_artifact(tmp_path: Path, change: str) -> None:
    dataset, protocol, result_path = _fixture(tmp_path)
    result = copy.deepcopy(json.loads(result_path.read_text()))
    if change == "raw_text":
        result["rows"][0]["user_message"] = "private utterance"
    elif change == "bad_index":
        result["rows"][0]["evidence_index"] = 999
    elif change == "bad_route":
        result["rows"][0]["gate_route"] = "safety_action_required"
    elif change == "bad_target":
        result["rows"][0]["target"] = "invalid"
    elif change == "bad_assertion":
        result["rows"][0]["assertion"] = "invalid"
    elif change == "bad_summary":
        result["summary"]["confirmed_hazard"]["gate_direct"] += 1
    elif change == "infinite_latency":
        result["rows"][0]["latency_ms"] = float("inf")
    else:
        result["dataset_sha256"] = "0" * 64
    result_path.write_text(json.dumps(result, ensure_ascii=False))
    with pytest.raises(ValueError):
        verify(dataset, protocol, result_path)


def test_frozen_result_passes_postrun_audit() -> None:
    root = Path(__file__).resolve().parents[1]
    folder = root / "evals/structured_nlu/data/ai_heldout"
    audit(
        folder / "as-safety-event-gate-fresh-reviewed.v1.json",
        folder / "as-safety-event-gate-fresh-protocol.v1.json",
        folder / "as-safety-event-gate-fresh-result.v1.json",
    )


@pytest.mark.parametrize("change", ["source_hash", "blank_message", "long_message"])
def test_postrun_audit_rejects_invalid_lineage_or_input(tmp_path: Path, change: str) -> None:
    dataset, protocol, result = _fixture(tmp_path)
    frozen = json.loads(protocol.read_text())
    frozen.update(
        {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in SOURCES.items()}
    )
    if change == "source_hash":
        frozen["gate_sha256"] = "0" * 64
    else:
        payload = json.loads(dataset.read_text())
        payload["cases"][0]["user_message"] = "   " if change == "blank_message" else "가" * 1001
        dataset.write_text(json.dumps(payload, ensure_ascii=False))
        frozen["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    protocol.write_text(json.dumps(frozen))
    saved = json.loads(result.read_text())
    saved["protocol_sha256"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    saved["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    result.write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        audit(dataset, protocol, result)
