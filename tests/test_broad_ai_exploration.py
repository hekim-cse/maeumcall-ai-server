import hashlib
import json

import pytest

from scripts.broad_ai_exploration_cases import FIELD_DRAFT, SENTENCES, load_cases
from scripts.compare_gguf_broad_ai_dev import compare
from scripts.probe_gguf_broad_ai_dev import KIND, summarize

pytestmark = pytest.mark.unit


def test_broad_ai_draft_covers_all_scenarios_without_reusing_exact_previous_messages():
    cases = load_cases()
    previous = json.loads(
        (
            SENTENCES.parents[2] / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
        ).read_text()
    )
    old_messages = {case["user_message"] for case in previous["cases"]}
    old_messages.update(
        case["user_message"]
        for case in json.loads(
            (
                SENTENCES.parents[2]
                / "evals/structured_nlu/data/exploratory/action-field-dev-2026-11-04.json"
            ).read_text()
        )["cases"]
    )
    assert len(cases) == 32
    assert len({case["scenario_key"] for case in cases}) == 16
    assert not old_messages.intersection(case["user_message"] for case in cases)
    for first, second in zip(cases[::2], cases[1::2], strict=True):
        assert first["scenario_key"] == second["scenario_key"]
        assert first["labels"]["user_action"] != "unknown"
        assert second["labels"]["user_action"] == "unknown"
        assert all(value is None for value in second["labels"]["fields"].values())


def test_broad_ai_source_rejects_unreviewed_metadata(tmp_path):
    source = json.loads(FIELD_DRAFT.read_text())
    source["provenance"] = "human_authored"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="AI-assisted exploratory"):
        load_cases(fields_path=changed)


def _report(model: str, model_hash: str) -> dict:
    cases = load_cases()
    observations = [
        {
            "case_id": case["id"],
            "scenario_key": case["scenario_key"],
            "repetition": repetition,
            "contract_valid": True,
            "action_draft_match": True,
            "field_draft_match": True,
            "draft_label_mismatch_fields": [],
            "elapsed_seconds": 1.0,
            "attempts": [{"prompt_tokens": 10, "cached_prompt_tokens": 0, "completion_tokens": 5}],
        }
        for repetition in (1, 2)
        for case in cases
    ]
    report = {
        "kind": KIND,
        "candidate_status": "ai_assisted_unreviewed",
        "sentence_action_review": "user_accepted_for_exploration_2026-11-04",
        "normalized_value_status": "ai_draft_unreviewed",
        "not_official_quality_score": True,
        "complete": True,
        "sentence_source_sha256": hashlib.sha256(SENTENCES.read_bytes()).hexdigest(),
        "field_draft_sha256": hashlib.sha256(FIELD_DRAFT.read_bytes()).hexdigest(),
        "implementation_sha256": "c" * 64,
        "code_git_commit": "d" * 40,
        "server_image_digest": "e" * 64,
        "runtime": "test",
        "container_cpu_limit": 2,
        "container_memory_gib": 6,
        "server_threads": 2,
        "server_parallel": 1,
        "context_size": 4096,
        "request_settings": {"temperature": 0},
        "case_ids": [case["id"] for case in cases],
        "repetitions": 2,
        "model": model,
        "model_sha256": model_hash,
        "observations": observations,
    }
    report["summary"] = summarize(observations)
    return report


def test_broad_ai_comparison_verifies_paired_inputs_and_summaries():
    first = _report("Q4", "4" * 64)
    second = _report("Q5", "5" * 64)
    second["observations"][0]["action_draft_match"] = False
    second["summary"] = summarize(second["observations"])

    result = compare(first, second)
    assert result["case_count"] == 32
    assert result["paired_action_draft_match"]["first_only"] == ["B01.r1"]
    assert result["models"][0]["summary"]["observations"] == 64

    second["summary"]["contract_passes"] = 0
    with pytest.raises(ValueError, match="summary differs"):
        compare(first, second)
