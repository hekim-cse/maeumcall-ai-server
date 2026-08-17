from __future__ import annotations

import json
from typing import Any

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import allowed_string, complete_validated_json, optional_string
from services.flow.service_workflow.contracts import (
    MAX_WORKFLOW_FIELD_LENGTH,
    WORKFLOW_ACTIONS,
    FieldContract,
    ServiceWorkflowSpec,
)


def analyze_service_workflow_message(
    spec: ServiceWorkflowSpec,
    *,
    conversation_state: str,
    current_fields: dict[str, str | None],
    user_message: str,
) -> dict[str, Any]:
    field_schema = "\n".join(_field_instruction(field) for field in spec.fields)
    current_fields_json = json.dumps(current_fields, ensure_ascii=False, sort_keys=True)
    field_keys_json = json.dumps(list(spec.field_keys), ensure_ascii=False)
    closing_states_json = json.dumps(
        [spec.ready_state, "cancelled", *(guard.state for guard in spec.guards)],
        ensure_ascii=False,
    )
    prompt = f"""
다음은 '{spec.category} / {spec.title}' 전화 시뮬레이션의 업무 상태 분석입니다.
현재 발화에 명시된 정보와 행동만 구조화하세요. 추측하거나 값을 만들어내지 마세요.

현재 conversation_state: {conversation_state}
현재까지 검증된 필드: {current_fields_json}
사용자 발화: {user_message}

반환 JSON schema:
{{
  "intent": "{spec.intent}",
  "fields": {{
    {", ".join(f'"{key}": string 또는 null' for key in spec.field_keys)}
  }},
  "user_action": string,
  "change_field": string 또는 null
}}

필드 의미:
{field_schema}

행동 기준:
- 새 업무 정보를 말하면 provide_details
- {spec.confirming_state}에서 정보가 맞다고 명시적으로 확인하면 confirm_details
- 이미 말한 정보를 수정하려 하면 change_detail, change_field는 {field_keys_json} 중 하나
- 업무 진행을 취소하면 cancel_workflow
- {closing_states_json} 중 한 상태에서 안전 조치 확인 또는 마무리 의사를 밝히면 go_closing
- closing에서 통화를 끝내려 하면 end_call
- 어느 기준에도 확실히 해당하지 않으면 unknown

계약:
- fields에는 위 필드 키를 빠짐없이 정확히 한 번씩 넣습니다.
- 현재 발화에서 새로 확인되지 않은 값은 null입니다. 현재까지의 값을 복사하지 않습니다.
- change_detail이 아니면 change_field는 null입니다.
- JSON 객체 외의 문장, markdown, 코드블록을 출력하지 않습니다.
"""
    return complete_validated_json(
        [
            {
                "role": "system",
                "content": (
                    "너는 전화 시뮬레이션 서버의 엄격한 업무 상태 분석기이다. "
                    "사용자가 말하지 않은 사실을 추론하지 않고 JSON 객체만 출력한다."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        completion=complete_hf_json,
        validator=lambda parsed: _validate_analysis(spec, parsed),
        operation=f"{spec.graph_name}_extraction",
    )


def _validate_analysis(spec: ServiceWorkflowSpec, parsed: dict[str, Any]) -> dict[str, Any]:
    expected_keys = {"intent", "fields", "user_action", "change_field"}
    if set(parsed) != expected_keys:
        raise ValueError(f"response keys must be exactly {sorted(expected_keys)}")
    if parsed.get("intent") != spec.intent:
        raise ValueError(f"intent must be {spec.intent}")

    raw_fields = parsed.get("fields")
    if not isinstance(raw_fields, dict) or set(raw_fields) != set(spec.field_keys):
        raise ValueError(f"fields keys must be exactly {sorted(spec.field_keys)}")
    fields: dict[str, str | None] = {}
    for field in spec.fields:
        value = optional_string(raw_fields, field.key)
        if value is not None and len(value) > MAX_WORKFLOW_FIELD_LENGTH:
            raise ValueError(f"{field.key} must be at most {MAX_WORKFLOW_FIELD_LENGTH} characters")
        if value is not None and field.options:
            allowed_values = {option.value for option in field.options}
            if value not in allowed_values:
                raise ValueError(f"{field.key} must be one of {sorted(allowed_values)}")
        fields[field.key] = value

    user_action = allowed_string(parsed, "user_action", set(WORKFLOW_ACTIONS))
    change_field = optional_string(parsed, "change_field")
    if user_action == "change_detail":
        if change_field not in spec.field_keys:
            raise ValueError("change_field must name a workflow field")
    elif change_field is not None:
        raise ValueError("change_field must be null unless user_action is change_detail")

    return {
        "intent": spec.intent,
        "fields": fields,
        "user_action": user_action,
        "change_field": change_field,
    }


def _field_instruction(field: FieldContract) -> str:
    if not field.options:
        return f"- {field.key}: string 또는 null — {field.description}"
    options = ", ".join(f'"{option.value}"({option.label})' for option in field.options)
    return (
        f"- {field.key}: 다음 코드 또는 null [{options}] — {field.description}. "
        "사용자 표현을 의미가 맞는 코드로만 분류합니다."
    )
