from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutDataset
from evals.structured_nlu.ai_reviewed_internal_policy_v1 import (
    CLAIM_LABEL,
    POLICY_ID,
    audit_internal_corpus,
    case_sha256,
    policy_sha256,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import DatasetSplit


def _artifacts():
    source = AIHeldoutDataset.model_validate_json(
        Path("evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json").read_bytes()
    )
    by_scenario = {}
    for case in source.cases:
        by_scenario.setdefault(case.scenario_key, []).append(case)
    assert len(by_scenario) == 16

    def make(split, copies):
        cases = []
        for scenario_index, (scenario, originals) in enumerate(sorted(by_scenario.items())):
            positive = next(case for case in originals if case.labels.user_action != "unknown")
            negative = next(case for case in originals if case.labels.user_action == "unknown")
            later = next(
                state
                for state in sorted(EVALUATION_CONTRACTS[scenario].conversation_states)
                if state.startswith(("collecting_", "asking_"))
                and "unknown" in EVALUATION_CONTRACTS[scenario].allowed_actions_for_state(state)
            )
            for copy_index in range(copies):
                for category, original in enumerate((positive, negative)):
                    case_id = f"{split[0]}{scenario_index:02}{copy_index}{category}"
                    updates = {
                        "id": case_id,
                        "conversation_group_id": f"group-{case_id}",
                        "split": DatasetSplit(split),
                        "user_message": f"{original.user_message} 가상 검증 번호 {case_id}",
                    }
                    if split == "test" and copy_index == 1 and category == 1:
                        updates["conversation_state"] = later
                    cases.append(original.model_copy(update=updates))
        dataset = source.model_copy(update={"cases": tuple(cases)})
        raw = dataset.model_dump_json().encode()
        ledger = {
            "kind": "ai_authored_heldout_review_v1",
            "reviewed_for": "ai_authored_heldout_accuracy",
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "accepted_case_ids": sorted(case.id for case in cases),
            "adjudicator_id": "portfolio-owner",
            "adjudicated_at": "2026-11-16T00:00:00+09:00",
            "rationale": "Synthetic test fixture; no real human review is claimed.",
        }
        case_ledger = {
            "kind": "ai_reviewed_internal_case_decisions_v1",
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "decisions": [
                {
                    "case_id": case.id,
                    "case_sha256": case_sha256(case),
                    "adjudicator_role_id": "portfolio-owner",
                    "adjudicated_at": "2026-11-16T00:00:00+09:00",
                    "decision": "accepted",
                    "rationale": f"Synthetic structural decision for {case.id}; no human review is claimed.",
                }
                for case in sorted(cases, key=lambda item: item.id)
            ],
        }
        return raw, json.dumps(ledger).encode(), json.dumps(case_ledger).encode()

    return (*make("validation", 1), *make("test", 2))


def _audit(artifacts, **overrides):
    (
        validation_raw,
        validation_ledger,
        validation_case_ledger,
        test_raw,
        test_ledger,
        test_case_ledger,
    ) = artifacts
    arguments = {
        "validation_dataset_bytes": validation_raw,
        "validation_ledger_bytes": validation_ledger,
        "validation_case_ledger_bytes": validation_case_ledger,
        "test_dataset_bytes": test_raw,
        "test_ledger_bytes": test_ledger,
        "test_case_ledger_bytes": test_case_ledger,
        "prior_exposed_messages": ("이미 모델에 보낸 별도 문장",),
    }
    arguments.update(overrides)
    return audit_internal_corpus(**arguments)


def _rebound_test_artifacts(artifacts, test):
    raw = json.dumps(test).encode()
    ledger = json.loads(artifacts[4])
    ledger["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    ledger["accepted_case_ids"] = sorted(case["id"] for case in test["cases"])
    case_ledger = json.loads(artifacts[5])
    case_ledger["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    cases = AIHeldoutDataset.model_validate_json(raw).cases
    case_ledger["decisions"] = [
        {
            **next(item for item in case_ledger["decisions"] if item["case_id"] == case.id),
            "case_sha256": case_sha256(case),
        }
        for case in sorted(cases, key=lambda item: item.id)
    ]
    return {
        "test_dataset_bytes": raw,
        "test_ledger_bytes": json.dumps(ledger).encode(),
        "test_case_ledger_bytes": json.dumps(case_ledger).encode(),
    }


def test_balanced_internal_corpus_qualifies():
    result = _audit(_artifacts())
    assert result.policy_id == POLICY_ID
    assert result.policy_sha256 == policy_sha256()
    assert CLAIM_LABEL == "AI 작성·사람 검수 내부 공식 표본 평가"
    assert (result.validation_cases, result.test_cases) == (32, 64)
    assert (result.validation_per_scenario, result.test_per_scenario) == (2, 4)
    assert result.scenario_count == 16


def test_prior_exposed_test_utterance_is_rejected():
    artifacts = _artifacts()
    test = AIHeldoutDataset.model_validate_json(artifacts[3])
    with pytest.raises(ValueError, match="previously exposed"):
        _audit(artifacts, prior_exposed_messages=(test.cases[0].user_message,))


def test_empty_exposure_inventory_is_rejected():
    with pytest.raises(ValueError, match="inventory"):
        _audit(_artifacts(), prior_exposed_messages=())


def test_blank_exposure_inventory_entry_is_rejected():
    with pytest.raises(ValueError, match="blank message"):
        _audit(_artifacts(), prior_exposed_messages=(" ",))


def test_changed_test_label_requires_new_ledger():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    test["cases"][0]["user_message"] += " 변경"
    with pytest.raises(ValueError, match="ledger does not match"):
        _audit(artifacts, test_dataset_bytes=json.dumps(test).encode())


def test_split_overlap_is_rejected():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    test["cases"][0]["conversation_group_id"] = "group-v0000"
    with pytest.raises(ValueError, match="conversation groups overlap"):
        _audit(artifacts, **_rebound_test_artifacts(artifacts, test))


def test_missing_later_state_is_rejected():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    for case in test["cases"]:
        case["conversation_state"] = "greeting"
    with pytest.raises(ValueError, match="later state"):
        _audit(artifacts, **_rebound_test_artifacts(artifacts, test))


def test_unbalanced_scenario_is_rejected():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    test["cases"].pop()
    with pytest.raises(ValueError, match="equal case counts"):
        _audit(artifacts, **_rebound_test_artifacts(artifacts, test))


def test_unknown_without_hard_negative_tag_is_rejected():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    negative = next(case for case in test["cases"] if case["labels"]["user_action"] == "unknown")
    negative["tags"] = ["ambiguous"]
    with pytest.raises(ValueError, match="category/tag conflict"):
        _audit(artifacts, **_rebound_test_artifacts(artifacts, test))


def test_every_case_requires_a_separate_decision():
    artifacts = _artifacts()
    case_ledger = json.loads(artifacts[5])
    case_ledger["decisions"].pop()
    with pytest.raises(ValueError, match="case ledger IDs differ"):
        _audit(artifacts, test_case_ledger_bytes=json.dumps(case_ledger).encode())


def test_changed_case_requires_new_case_fingerprint_even_with_new_dataset_sha():
    artifacts = _artifacts()
    test = json.loads(artifacts[3])
    test["cases"][0]["user_message"] += " 변경"
    rebound = _rebound_test_artifacts(artifacts, test)
    case_ledger = json.loads(rebound["test_case_ledger_bytes"])
    original = json.loads(artifacts[5])
    case_ledger["decisions"][0]["case_sha256"] = original["decisions"][0]["case_sha256"]
    rebound["test_case_ledger_bytes"] = json.dumps(case_ledger).encode()
    with pytest.raises(ValueError, match="case decision content differs"):
        _audit(artifacts, **rebound)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("adjudicated_at", "2026-11-16T00:00:00", "timezone"),
        ("rationale", " ", "string_too_short"),
        ("decision", "rejected", "literal_error"),
        ("unexpected_field", "value", "extra_forbidden"),
    ],
)
def test_case_decisions_require_time_and_reason(field, value, message):
    artifacts = _artifacts()
    case_ledger = json.loads(artifacts[5])
    case_ledger["decisions"][0][field] = value
    with pytest.raises(ValueError, match=message):
        _audit(artifacts, test_case_ledger_bytes=json.dumps(case_ledger).encode())
