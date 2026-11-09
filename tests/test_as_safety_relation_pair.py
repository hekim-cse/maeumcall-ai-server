"""Check approved RE input and independent result integrity boundaries."""

import json

import pytest

from scripts.run_as_safety_relation_pair import load_reviewed, summarize
from scripts.verify_as_safety_relation_pair import sha256, verify

DATASET = "evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json"
PROTOCOL = "evals/structured_nlu/data/ai_heldout/as-safety-relation-pair-protocol.v1.json"
RESULT = "evals/structured_nlu/data/ai_heldout/as-safety-relation-pair-result.v1.json"


def test_reviewed_relation_cases_are_ordered_and_bounded():
    from pathlib import Path

    cases, digest = load_reviewed(
        Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json")
    )
    assert [case["id"] for case in cases] == [f"RE{index:02}" for index in range(1, 17)]
    assert len(digest) == 64


def test_reviewed_relation_cases_reject_changed_gold(tmp_path):
    from pathlib import Path

    source = Path("evals/structured_nlu/data/ai_heldout/as-safety-relation-fresh-reviewed.v1.json")
    payload = json.loads(source.read_text())
    payload["cases"][0]["expected_relation"]["hazard_index"] = 3
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="source index"):
        load_reviewed(changed)


def test_summary_keeps_errors_separate():
    rows = [
        {f"{arm}_{field}": None for arm in ("baseline", "relation") for field in ("route", "error")}
        for _ in range(16)
    ]
    rows[0]["baseline_route"] = "safety_action_required"
    rows[0]["relation_error"] = "TimeoutError"
    summary = summarize(rows)
    assert summary["confirmed_hazard"]["baseline_direct"] == 1
    assert summary["confirmed_hazard"]["relation_errors"] == 1


def test_verifier_rejects_protocol_mismatch(tmp_path):
    dataset = tmp_path / "dataset.json"
    protocol = tmp_path / "protocol.json"
    result = tmp_path / "result.json"
    dataset.write_text(json.dumps({"review_status": "owner_approved_for_exploration"}))
    protocol.write_text(json.dumps({"dataset_sha256": "0" * 64}))
    result.write_text("{}")
    with pytest.raises(ValueError, match="protocol dataset hash"):
        verify(dataset, protocol, result)


def test_frozen_result_reverifies():
    from pathlib import Path

    assert (
        verify(Path(DATASET), Path(PROTOCOL), Path(RESULT))["confirmed_hazard"]["denominator"] == 4
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda value: value["rows"][0].__setitem__(
                "relation_route", "collecting_service_request"
            ),
            "route differs",
        ),
        (
            lambda value: value["summary"]["confirmed_hazard"].__setitem__("relation_direct", 3),
            "summary differs",
        ),
        (
            lambda value: value["rows"][0].__setitem__("relation_latency_ms", float("nan")),
            "invalid latency",
        ),
    ],
)
def test_verifier_rejects_tampered_result(tmp_path, change, message):
    from pathlib import Path

    result = json.loads(Path(RESULT).read_text())
    change(result)
    changed = tmp_path / "result.json"
    changed.write_text(json.dumps(result))
    with pytest.raises(ValueError, match=message):
        verify(Path(DATASET), Path(PROTOCOL), changed)


def test_verifier_rejects_changed_reviewed_relation(tmp_path):
    from pathlib import Path

    dataset = json.loads(Path(DATASET).read_text())
    dataset["cases"][0]["expected_relation"]["event_status"] = "uncertain"
    changed = tmp_path / "dataset.json"
    changed.write_text(json.dumps(dataset))
    protocol = json.loads(Path(PROTOCOL).read_text())
    protocol["dataset_sha256"] = sha256(changed)
    changed_protocol = tmp_path / "protocol.json"
    changed_protocol.write_text(json.dumps(protocol))
    result = json.loads(Path(RESULT).read_text())
    result["protocol_sha256"] = sha256(changed_protocol)
    result["dataset_sha256"] = sha256(changed)
    changed_result = tmp_path / "result.json"
    changed_result.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="reviewed relation and route differ"):
        verify(changed, changed_protocol, changed_result)
