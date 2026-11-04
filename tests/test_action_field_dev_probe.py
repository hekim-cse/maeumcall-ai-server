import copy
import hashlib

import pytest

from scripts.action_field_dev_cases import load_cases
from scripts.compare_action_field_model_reports import compare
from scripts.probe_gguf_action_field_dev import (
    KIND,
    condition_order,
    file_sha256,
    summarize_pairs,
)

pytestmark = pytest.mark.unit


def _observation(*, valid: bool, action_match: bool) -> dict:
    return {
        "contract_valid": valid,
        "draft_label_mismatch_fields": [] if action_match else ["user_action"],
        "action_draft_match": action_match,
        "field_draft_match": True,
        "first_stage_action_draft_match": action_match,
        "elapsed_seconds": 2.5,
        "attempts": [
            {
                "prompt_tokens": 100,
                "cached_prompt_tokens": 25,
                "completion_tokens": 12,
            }
        ],
    }


def _report(model_sha: str) -> dict:
    pairs = [
        {
            "case_id": "D01",
            "repetition": 1,
            "order": ["baseline", "split"],
            "baseline": _observation(valid=False, action_match=False),
            "split": _observation(valid=True, action_match=True),
        }
    ]
    return {
        "kind": KIND,
        "not_official_quality_score": True,
        "complete": True,
        "case_source_sha256": "a" * 64,
        "implementation_sha256": "d" * 64,
        "code_git_commit": "e" * 40,
        "server_image_digest": "sha256:" + "b" * 64,
        "runtime": "local arm64",
        "container_cpu_limit": 2,
        "server_threads": 2,
        "context_size": 4096,
        "request_settings": {"temperature": 0},
        "schema_format": "json_object",
        "case_ids": ["D01"],
        "repetitions": 1,
        "model": model_sha,
        "model_sha256": model_sha,
        "pairs": pairs,
        "summary": summarize_pairs(pairs),
    }


def test_development_cases_keep_ai_origin_and_reviewed_meaning_boundary():
    cases = load_cases()
    assert [case["id"] for case in cases] == [f"D{index:02}" for index in range(1, 9)]
    d05 = cases[4]
    assert d05["labels"]["fields"]["evidence_status"] is None
    assert d05["labels"]["fields"]["resolution_preference"] is None
    assert d05["labels"]["user_action"] == "provide_details"


def test_condition_order_is_counterbalanced_across_cases_and_repetitions():
    assert condition_order(0, 0) == ("baseline", "split")
    assert condition_order(1, 0) == ("split", "baseline")
    assert condition_order(0, 1) == ("split", "baseline")


def test_model_file_hash_uses_file_contents(tmp_path):
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"pinned model bytes")
    assert file_sha256(model_file) == hashlib.sha256(b"pinned model bytes").hexdigest()


def test_comparison_counts_contract_change_and_rejects_changed_source():
    first, second = _report("1" * 64), _report("2" * 64)
    result = compare(first, second)
    assert result["not_official_quality_score"] is True
    assert result["model_results"][0]["paired_contract_new_passes"] == ["D01.r1"]
    assert result["model_results"][0]["split"]["first_stage_action_draft_matches"] == 1

    changed = copy.deepcopy(second)
    changed["case_source_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="case_source_sha256"):
        compare(first, changed)


def test_comparison_rejects_forged_summary():
    first, second = _report("1" * 64), _report("2" * 64)
    second["summary"]["split"]["contract_passes"] = 99
    with pytest.raises(ValueError, match="summary does not match"):
        compare(first, second)
