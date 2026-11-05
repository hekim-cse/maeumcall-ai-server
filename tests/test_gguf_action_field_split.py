import json
from contextlib import nullcontext

import pytest

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from scripts.gguf_action_field_split import validate_action_choice
from scripts.probe_gguf_structured_nlu import run_case
from scripts.validate_nlu_review_draft import load_draft_cases

pytestmark = pytest.mark.unit


def test_action_choice_rejects_uncollected_change_target():
    spec = EVALUATION_CONTRACTS["배달:주문 변경"].workflow_spec
    current_fields = dict.fromkeys(spec.field_keys)
    with pytest.raises(ValueError, match="already be collected"):
        validate_action_choice(
            {"user_action": "change_detail", "change_field": "order_number"},
            spec=spec,
            conversation_state=spec.collecting_state,
            current_fields=current_fields,
        )


def test_split_probe_calls_action_then_fields_without_persisting_generated_values(monkeypatch):
    case = next(case for case in load_draft_cases() if case["id"] == "H14")
    requests = []
    responses = iter(
        [
            {"user_action": "unknown", "change_field": None},
            {
                "intent": "delivery_delay_inquiry",
                "fields": dict.fromkeys(EVALUATION_CONTRACTS[case["scenario_key"]].field_names),
                "user_action": "unknown",
                "change_field": None,
            },
        ]
    )

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        requests.append(payload)
        generated = next(responses)
        return nullcontext(
            FakeResponse(
                {
                    "choices": [
                        {"message": {"content": json.dumps(generated)}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model="fake",
        timeout=1,
        capture_shape=True,
        constrain_workflow=True,
        schema_format="json_object",
        split_workflow=True,
    )

    assert result["contract_valid"] is True
    assert result["draft_label_mismatch_fields"] == []
    assert [attempt["stage"] for attempt in result["attempts"]] == ["action", "fields"]
    assert all(request["response_format"]["type"] == "json_object" for request in requests)
    assert case["user_message"] not in json.dumps(result, ensure_ascii=False)


def test_split_probe_exhausts_invalid_action_retries_without_field_request(monkeypatch):
    case = next(case for case in load_draft_cases() if case["id"] == "H14")
    requests = []

    class FakeResponse:
        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"user_action": "invalid_action", "change_field": None}
                                )
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requests.append(json.loads(request.data))
        return nullcontext(FakeResponse())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model="fake",
        timeout=1,
        capture_shape=True,
        constrain_workflow=True,
        schema_format="json_object",
        split_workflow=True,
    )

    assert result["contract_valid"] is False
    assert result["selected_action"] is None
    assert result["first_stage_action_draft_match"] is None
    assert len(requests) == 2
    assert [attempt["stage"] for attempt in result["attempts"]] == ["action", "action"]
    assert case["user_message"] not in json.dumps(result, ensure_ascii=False)


def test_split_probe_keeps_policy_on_original_turn_during_retry(monkeypatch):
    case = next(case for case in load_draft_cases() if case["id"] == "H14")
    requests = []

    class FakeResponse:
        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {"user_action": "invalid_action", "change_field": None}
                                )
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        requests.append(json.loads(request.data)["messages"])
        return nullcontext(FakeResponse())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model="fake",
        timeout=1,
        constrain_workflow=True,
        schema_format="json_object",
        split_workflow=True,
        extra_instruction="policy",
    )
    assert len(requests) == 2
    first, retry = requests
    assert first[1]["content"].endswith("\npolicy")
    assert retry[1]["content"] == first[1]["content"]
    assert retry[1]["content"].count("policy") == 1
    assert retry[-1]["role"] == "user"
    assert retry[-1]["content"].startswith("이전 출력은 JSON 계약 검증에 실패했습니다.")
    assert "policy" not in retry[-1]["content"]
