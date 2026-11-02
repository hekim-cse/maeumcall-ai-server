import copy

import pytest

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from scripts.compare_workflow_schema_experiment import compare
from scripts.gguf_service_workflow_schema import workflow_response_schema

pytestmark = pytest.mark.unit


def test_schema_cannot_emit_provide_details_with_all_null_fields():
    spec = EVALUATION_CONTRACTS["배달:배달 지연 문의"].workflow_spec
    schema = workflow_response_schema(
        spec,
        conversation_state="collecting_delay_inquiry",
        current_fields=dict.fromkeys(spec.field_keys),
    )

    provide_branches = [
        branch
        for branch in schema["anyOf"]
        if branch["properties"]["user_action"]["enum"] == ["provide_details"]
    ]
    assert len(provide_branches) == len(spec.field_keys)
    for branch in provide_branches:
        field_shapes = branch["properties"]["fields"]["properties"]
        assert any(
            shape.get("type") == "string" or "enum" in shape and None not in shape["enum"]
            for shape in field_shapes.values()
        )


def test_ablation_comparison_rejects_changed_model_or_source():
    baseline = {
        "kind": "exploratory_gguf_review_draft_round2_v1",
        "complete": True,
        "sentence_draft_sha256": "a",
        "label_draft_sha256": "b",
        "model_sha256": "c",
        "server_image_digest": "d",
        "runtime": "local",
        "container_cpu_limit": 2,
        "server_threads": 2,
        "context_size": 4096,
        "request_settings": {"temperature": 0},
        "selected_case_ids": ["H14"],
        "observations": [
            {"case_id": "H14", "contract_valid": False, "draft_label_mismatch_fields": []}
        ],
    }
    constrained = copy.deepcopy(baseline)
    constrained["workflow_schema_constrained"] = True
    constrained["schema_format"] = "json_object"
    constrained["observations"][0]["contract_valid"] = True

    result = compare(baseline, constrained)
    assert result["new_contract_pass_case_ids"] == ["H14"]
    assert result["new_draft_match_case_ids"] == ["H14"]
    assert "accuracy" not in result

    constrained["model_sha256"] = "different"
    with pytest.raises(ValueError, match="model_sha256"):
        compare(baseline, constrained)
