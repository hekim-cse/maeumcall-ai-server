"""Regression checks for joining a regex-only guard and a fixed model journal."""

from __future__ import annotations

import json

import pytest

from scripts import audit_as_safety_layered_failure as layered


def test_recorded_model_join_separates_errors_from_conditional_guard_effects():
    """Do not treat a regex match as observed graph execution or extra model error."""
    report = layered.audit()
    assert report["claim_scope"] == "exposed_ai_authored_conditional_layer_join_only"
    assert report["actual_service_execution_measured"] is False
    assert report["guard_eligibility_known"] is False
    assert report["source_versions_capture"] == (
        "post_audit_non_atomic_local_file_hashes_not_frozen_snapshot"
    )
    assert report["model_cases"] == 22
    assert report["model_relation_errors"] == 5
    assert report["model_error_ids"] == ["RE09", "RE11", "V02", "V06", "V08"]
    assert report["guard_pattern_match_ids"] == ["RE09", "RE11", "V01", "V02", "V05"]
    assert report["model_error_with_guard_pattern_ids"] == ["RE09", "RE11", "V02"]
    assert report["model_error_without_guard_pattern_ids"] == ["V06", "V08"]
    assert report["guard_pattern_false_direct_ids"] == ["RE09", "RE11", "V02"]
    versions = report["source_versions"]
    assert set(versions) == {
        "combined_audit",
        "regex_audit",
        "regex_implementation",
        "entity_link_verifier",
        "entity_link_protocol",
        "entity_link_journal",
        "re_dataset",
        "v_dataset",
    }
    assert all(len(source["sha256"]) == 64 for source in versions.values())
    conditional = report["hybrid_counterfactual_if_all_guard_eligible"]
    assert conditional["assumption_only"] is True
    assert conditional["nonmatch_route_source"] == "entity_link_diagnostic_oracle_derived_route"
    assert conditional["route_changed_from_entity_link_ids"] == ["V02"]
    assert conditional["oracle_derived_hybrid_route_denominator"] == 22
    assert conditional["oracle_derived_hybrid_route_correct"] == 17
    assert conditional["false_direct_ids"] == ["RE09", "RE11", "V02"]
    assert conditional["oracle_derived_false_direct_ids"] == ["RE09", "RE11"]
    assert conditional["guard_added_false_direct_ids"] == ["V02"]
    assert "연기" not in json.dumps(report, ensure_ascii=False)
    assert "user_message" not in report


@pytest.mark.parametrize("mutation", ["duplicate", "unknown_id", "count"])
def test_guard_join_rejects_inconsistent_match_inventory(monkeypatch, mutation):
    """Fail rather than silently joining an invalid guard match list."""
    original = layered.guard.audit()
    changed = {**original, "forced_safety_ids": list(original["forced_safety_ids"])}
    if mutation == "duplicate":
        changed["forced_safety_ids"][1] = changed["forced_safety_ids"][0]
    elif mutation == "unknown_id":
        changed["forced_safety_ids"][1] = "ZZ99"
    else:
        changed["forced_safety"] += 1
    monkeypatch.setattr(layered.guard, "audit", lambda: changed)
    with pytest.raises(ValueError, match="guard match IDs differ"):
        layered.audit()


def test_source_dataset_mismatch_is_rejected(monkeypatch, tmp_path):
    """The two audits must use the same RE/V source files."""
    changed = ((tmp_path / "different.json", "RE"), layered.guard.SOURCES[1])
    monkeypatch.setattr(layered.guard, "SOURCES", changed)
    with pytest.raises(ValueError, match="different source datasets"):
        layered.audit()
