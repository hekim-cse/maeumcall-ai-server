import copy
import json

import pytest

from scripts.compare_exploratory_gguf_reports import KIND, _load, compare

pytestmark = pytest.mark.unit


def _report(*, matches: tuple[bool, bool], model_sha: str) -> dict:
    return {
        "kind": KIND,
        "not_official_quality_score": True,
        "complete": True,
        "sentence_draft_sha256": "a" * 64,
        "label_draft_sha256": "b" * 64,
        "request_settings": {"temperature": 0},
        "server_image_digest": "sha256:" + "c" * 64,
        "runtime": "Docker Desktop linux/arm64 CPU",
        "container_cpu_limit": 2,
        "server_threads": 2,
        "context_size": 4096,
        "selected_case_ids": ["H01", "H02"],
        "case_count": 2,
        "model_sha256": model_sha,
        "observations": [
            {
                "case_id": case_id,
                "contract_valid": True,
                "draft_label_mismatch_fields": [] if matches[index] else ["user_action"],
            }
            for index, case_id in enumerate(("H01", "H02"))
        ],
    }


def test_comparison_counts_paired_draft_match_changes_without_accuracy_claim():
    baseline = _report(matches=(True, False), model_sha="1" * 64)
    candidate = _report(matches=(False, True), model_sha="2" * 64)

    result = compare(baseline, candidate)

    assert result["not_official_quality_score"] is True
    assert result["baseline_draft_matches"] == 1
    assert result["candidate_draft_matches"] == 1
    assert result["draft_match_delta_cases"] == 0
    assert result["improved_case_ids"] == ["H02"]
    assert result["regressed_case_ids"] == ["H01"]
    assert "accuracy" not in result


def test_comparison_rejects_different_labels_or_cases():
    baseline = _report(matches=(True, False), model_sha="1" * 64)
    candidate = _report(matches=(True, True), model_sha="2" * 64)
    candidate["label_draft_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="label_draft_sha256"):
        compare(baseline, candidate)

    candidate = copy.deepcopy(candidate)
    candidate["label_draft_sha256"] = baseline["label_draft_sha256"]
    candidate["selected_case_ids"].reverse()
    with pytest.raises(ValueError, match="selected_case_ids"):
        compare(baseline, candidate)

    candidate = _report(matches=(True, True), model_sha="2" * 64)
    candidate["server_threads"] = 4
    with pytest.raises(ValueError, match="server_threads"):
        compare(baseline, candidate)


def test_report_loader_rejects_partial_results(tmp_path):
    report = _report(matches=(True, False), model_sha="1" * 64)
    report["complete"] = False
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(report))

    with pytest.raises(ValueError, match="incomplete"):
        _load(path)
