"""Join a frozen RE/V model journal with a current regex audit, without graph execution.

The pre-model guard audit runs the current regex implementation on original
utterances after the model journal was recorded. The entity-link verifier
reports recorded model decisions on 22 exposed cases.
This audit shows their overlap and a hybrid counterfactual: a guard match
forces the direct route if every case were guard-eligible, while nonmatches
retain the oracle-derived route from the entity-link diagnostic. Eligibility
and actual graph execution are unmeasured.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import audit_as_safety_pre_model_guard as guard
from scripts import verify_as_safety_entity_link_diagnostic as entity

DATA = entity.DATA
DEFAULT_PROTOCOL = DATA / "as-safety-entity-link-diagnostic-protocol.v1.json"
DEFAULT_JOURNAL = DATA / "as-safety-entity-link-diagnostic-journal.v1.jsonl"
DIRECT = "safety_action_required"


def _source_versions(protocol_path: Path, journal_path: Path) -> dict[str, dict[str, str]]:
    """Hash local files after the audit; this is not an atomic execution snapshot."""
    paths = {
        "combined_audit": Path(__file__),
        "regex_audit": Path(guard.__file__),
        "regex_implementation": Path(guard.has_explicit_safety_issue.__code__.co_filename),
        "entity_link_verifier": Path(entity.__file__),
        "entity_link_protocol": protocol_path,
        "entity_link_journal": journal_path,
        "re_dataset": guard.SOURCES[0][0],
        "v_dataset": guard.SOURCES[1][0],
    }
    return {
        name: {"path": str(path.resolve()), "sha256": entity.digest(path)}
        for name, path in paths.items()
    }


def audit(protocol_path: Path = DEFAULT_PROTOCOL, journal_path: Path = DEFAULT_JOURNAL) -> dict:
    """Count guard/model overlap and conditional route effects by case ID."""
    if (
        guard.SOURCES[0][0].resolve() != entity.SOURCES["re_dataset_sha256"].resolve()
        or guard.SOURCES[1][0].resolve() != entity.SOURCES["v_dataset_sha256"].resolve()
    ):
        raise ValueError("guard and entity audits use different source datasets")
    guard_report = guard.audit()
    verified = entity.verify(protocol_path, journal_path)
    cases = verified["per_case"]
    ids = [row["id"] for row in cases]
    if (
        guard_report["cases"] != 32
        or len(cases) != 22
        or tuple(ids) != entity.CASE_IDS
        or verified["summary"]["all"]["denominator"] != 22
        or verified["summary"]["all"]["errors"] != 0
    ):
        raise ValueError("guard/entity denominator differs")
    matches = guard_report["forced_safety_ids"]
    if (
        len(matches) != guard_report["forced_safety"]
        or len(matches) != len(set(matches))
        or any(
            case_id
            not in {*(f"RE{i:02}" for i in range(1, 17)), *(f"V{i:02}" for i in range(1, 17))}
            for case_id in matches
        )
    ):
        raise ValueError("guard match IDs differ")
    matched = set(matches)
    active_matched = [row for row in cases if row["id"] in matched]
    model_errors = [row for row in cases if row["predicted_relation"] != row["gold_relation"]]
    matched_errors = [row for row in model_errors if row["id"] in matched]
    unmatched_errors = [row for row in model_errors if row["id"] not in matched]

    conditional = [
        {
            **row,
            "hybrid_counterfactual_route": DIRECT
            if row["id"] in matched
            else row["predicted_route"],
        }
        for row in cases
    ]
    route_changed = [
        row["id"]
        for row in conditional
        if row["hybrid_counterfactual_route"] != row["predicted_route"]
    ]
    false_direct = [
        row["id"]
        for row in conditional
        if row["hybrid_counterfactual_route"] == DIRECT and row["gold_route"] != DIRECT
    ]
    oracle_derived_false_direct = [
        row["id"]
        for row in cases
        if row["predicted_route"] == DIRECT and row["gold_route"] != DIRECT
    ]
    guard_added_false_direct = [
        row["id"]
        for row in conditional
        if row["id"] in false_direct and row["id"] not in oracle_derived_false_direct
    ]
    matched_false_direct = [row["id"] for row in active_matched if row["gold_route"] != DIRECT]
    return {
        "claim_scope": "exposed_ai_authored_conditional_layer_join_only",
        "actual_service_execution_measured": False,
        "guard_eligibility_known": False,
        "source_versions_capture": "post_audit_non_atomic_local_file_hashes_not_frozen_snapshot",
        "source_versions": _source_versions(protocol_path, journal_path),
        "model_cases": len(cases),
        "model_relation_errors": len(model_errors),
        "model_error_ids": [row["id"] for row in model_errors],
        "guard_pattern_matches_in_model_cases": len(active_matched),
        "guard_pattern_match_ids": [row["id"] for row in active_matched],
        "model_errors_with_guard_pattern": len(matched_errors),
        "model_error_with_guard_pattern_ids": [row["id"] for row in matched_errors],
        "model_errors_without_guard_pattern": len(unmatched_errors),
        "model_error_without_guard_pattern_ids": [row["id"] for row in unmatched_errors],
        "guard_pattern_false_direct_if_eligible": len(matched_false_direct),
        "guard_pattern_false_direct_ids": matched_false_direct,
        "hybrid_counterfactual_if_all_guard_eligible": {
            "assumption_only": True,
            "nonmatch_route_source": "entity_link_diagnostic_oracle_derived_route",
            "route_changed_from_entity_link_ids": route_changed,
            "oracle_derived_hybrid_route_denominator": len(conditional),
            "oracle_derived_hybrid_route_correct": sum(
                row["hybrid_counterfactual_route"] == row["gold_route"] for row in conditional
            ),
            "false_direct_ids": false_direct,
            "oracle_derived_false_direct_ids": oracle_derived_false_direct,
            "guard_added_false_direct_ids": guard_added_false_direct,
        },
    }


def main() -> None:
    """Print a finite, text-free post-run diagnostic summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    args = parser.parse_args()
    print(json.dumps(audit(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
