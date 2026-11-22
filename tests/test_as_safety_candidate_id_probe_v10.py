"""Pre-run checks for the new candidate-ID prompt and frozen requests."""

import copy
import json

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe, verify


def test_both_development_controls_have_source_only_catalogs():
    controls = probe.cases()
    assert set(controls) == set(probe.CASE_ORDER)
    assert [len(probe.catalog(controls[name]).candidates) for name in probe.CASE_ORDER] == [7, 4]
    assert any(c.quote == "선풍기 모터" for c in probe.catalog(controls["PC01"]).candidates)


def test_prompt_and_wire_request_never_include_gold_fields():
    controls = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    for case in controls.values():
        selected = probe.catalog(case)
        messages = probe.messages(case, selected)
        assert "subject_span에 인용" not in messages[1]["content"]
        assert "candidate_id" in messages[1]["content"]
        assert "gold_subject_span" not in json.dumps(messages, ensure_ascii=False)
        assert "gold_kind" not in json.dumps(messages, ensure_ascii=False)
        baseline = probe.request_bytes(case, policy)
        changed = copy.deepcopy(case)
        changed["gold_subject_span"] = {"clause_index": 1, "quote": "선풍기"}
        changed["gold_kind"] = "subject"
        assert probe.request_bytes(changed, policy) == baseline


def test_independent_request_builder_matches_probe_bytes():
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    for case in probe.cases().values():
        assert verify._request(case, policy) == probe.request_bytes(case, policy)


def test_independent_scoring_separates_contract_and_semantics():
    controls = probe.cases()
    catalog = probe.catalog(controls["PC01"])
    correct_id = next(c.id for c in catalog.candidates if c.quote == "선풍기 모터")
    assert (
        verify._score(
            json.dumps({"candidate_id": correct_id, "event_subject_kind": "location"}).encode(),
            controls["PC01"],
        )["B_exact"]
        is True
    )
    assert (
        verify._score(b'{"candidate_id":"P999","event_subject_kind":"location"}', controls["PC01"])[
            "contract_error"
        ]
        == "candidate_not_offered"
    )
    assert (
        verify._score(b'{"candidate_id":null,"event_subject_kind":"unresolved"}', controls["NC01"])[
            "valid_hold"
        ]
        is True
    )
