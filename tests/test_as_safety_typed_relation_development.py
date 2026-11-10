"""Check the frozen RE/V adapter and its independent decision verifier."""

import json
from pathlib import Path

import pytest

from scripts.as_safety_preflight_v3 import verify_frozen_sources
from scripts.run_as_safety_typed_relation_development import load_exposed_cases, load_policy
from scripts.verify_as_safety_typed_relation_development import verify, verify_candidate_decision

DATA = Path("evals/structured_nlu/data/ai_heldout")
POLICY = DATA / "as-safety-grounded-development-request.v1.json"
PROTOCOL = DATA / "as-safety-typed-relation-exposed-development-protocol.v1.json"
JOURNAL = DATA / "as-safety-typed-relation-exposed-development-result.v1.jsonl"
MESSAGE = "제 공기청정기에서 연기가 났습니다. 전원을 껐습니다."


def decision(**changes):
    """Build one bounded candidate decision with optional field changes."""
    result = {
        "product_index": 1,
        "event_index": 1,
        "source_index": 1,
        "occurrence_index": 1,
        "source_relation": "current_product",
        "event_status": "observed",
    }
    result.update(changes)
    return result


def test_runner_reuses_frozen_policy_and_only_reviewed_re_v_cases():
    """The adapter loads only the approved RE/V development cases."""
    policy = load_policy(POLICY)
    assert policy.max_tokens == 180
    assert policy.temperature == 0
    assert [case["id"] for case in load_exposed_cases()] == [
        *(f"RE{i:02}" for i in range(1, 17)),
        *(f"V{i:02}" for i in range(1, 17)),
    ]


@pytest.mark.parametrize(
    ("changes", "route"),
    [
        ({}, "safety_action_required"),
        ({"source_relation": "current_part"}, "safety_action_required"),
        ({"source_relation": "other_product"}, "collecting_service_request"),
        ({"source_relation": "location_only"}, "confirming_safety_status"),
        ({"source_relation": "alternative_unknown"}, "confirming_safety_status"),
        ({"event_status": "uncertain"}, "confirming_safety_status"),
        ({"event_status": "nonoccurring"}, "collecting_service_request"),
    ],
)
def test_verifier_recomputes_routes(changes, route):
    """The independent route calculation covers each relation branch."""
    assert verify_candidate_decision(decision(**changes), MESSAGE) == route


def test_verifier_allows_separate_source_and_occurrence_evidence():
    """A later correction may determine the source of an earlier event."""
    assert (
        verify_candidate_decision(
            decision(source_index=2, occurrence_index=1, source_relation="alternative_unknown"),
            MESSAGE,
        )
        == "confirming_safety_status"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"event_index": None},
        {"occurrence_index": None},
        {"product_index": None},
        {"source_index": None},
        {"source_index": 3},
        {"event_index": True},
        {"event_status": "none"},
    ],
)
def test_verifier_rejects_inconsistent_or_unbounded_evidence(changes):
    """Invalid or missing event edges cannot receive a scored route."""
    with pytest.raises(ValueError):
        verify_candidate_decision(decision(**changes), MESSAGE)


def test_verifier_accepts_empty_event_only_with_empty_edges():
    """No-event decisions must have no dangling evidence IDs."""
    empty = decision(
        product_index=None,
        event_index=None,
        source_index=None,
        occurrence_index=None,
        source_relation="none",
        event_status="none",
    )
    assert verify_candidate_decision(empty, MESSAGE) == "collecting_service_request"
    with pytest.raises(ValueError):
        verify_candidate_decision({**empty, "source_index": 1}, MESSAGE)


def test_policy_cannot_silently_change_request_settings(tmp_path):
    """A changed request policy cannot silently alter model conditions."""
    changed = json.loads(POLICY.read_text(encoding="utf-8"))
    changed["temperature"] = 1
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="request policy differs"):
        load_policy(path)


def test_frozen_preflight_rejects_changed_runner_digest(tmp_path):
    """A changed source hash is rejected before any new model exposure."""
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    protocol["runner_sha256"] = "0" * 64
    altered = tmp_path / "changed-protocol.json"
    altered.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="runner_sha256"):
        verify_frozen_sources(
            altered,
            {"runner_sha256": Path("scripts/run_as_safety_typed_relation_development.py")},
        )


def test_result_verifier_rejects_route_tampering(tmp_path):
    """A journal route must match its saved bounded decision."""
    events = [json.loads(line) for line in JOURNAL.read_text(encoding="utf-8").splitlines()]
    record = next(
        row
        for row in events
        if row.get("event") == "end"
        and row.get("arm") == "baseline"
        and row.get("error_stage") is None
    )
    record["route"] = next(
        route
        for route in (
            "safety_action_required",
            "confirming_safety_status",
            "collecting_service_request",
        )
        if route != record["route"]
    )
    altered = tmp_path / "changed-journal.jsonl"
    altered.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in events) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="saved route differs"):
        verify(PROTOCOL, altered)


def test_result_verifier_rejects_incomplete_exposure_journal(tmp_path):
    """A missing final call cannot be omitted from the denominator."""
    lines = JOURNAL.read_text(encoding="utf-8").splitlines()
    altered = tmp_path / "partial-journal.jsonl"
    altered.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete or duplicate calls"):
        verify(PROTOCOL, altered)
