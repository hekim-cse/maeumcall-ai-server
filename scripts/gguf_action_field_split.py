"""Experimental first-stage action selection for local GGUF workflow probes."""

from __future__ import annotations

import json

from llm.structured_output import require_exact_keys
from services.flow.service_workflow.contracts import ServiceWorkflowSpec


def action_messages(
    spec: ServiceWorkflowSpec,
    *,
    conversation_state: str,
    current_fields: dict[str, str | None],
    user_message: str,
) -> list[dict[str, str]]:
    allowed = sorted(spec.actions_by_state[conversation_state])
    field_scope = "\n".join(f"- {field.key}: {field.description}" for field in spec.fields)
    prompt = f"""'{spec.category} / {spec.title}' 전화 시뮬레이션의 이번 발화 행동만 판단하세요.
현재 상태: {conversation_state}
현재 허용 행동: {json.dumps(allowed, ensure_ascii=False)}
이전에 확인한 필드: {json.dumps(current_fields, ensure_ascii=False, sort_keys=True)}
이 업무에서 수집하는 정보:
{field_scope}
이번 발화: {user_message}

판단 기준:
- 이번 발화가 이 업무에서 수집하는 정보를 새로 제공하면 provide_details입니다.
- 이미 수집한 정보를 바꾸려 하면 change_detail이며 change_field는 그 필드 이름입니다.
- 이 업무 진행 자체를 명확히 취소하면 cancel_workflow입니다. 단순히 다른 정보를
  물으면서 기존 주문이나 진행 내용은 그대로 둔다는 말은 취소가 아닙니다.
- 요청 목적이 이 업무의 정보 수집 범위 밖이거나 의도가 불명확하면 unknown입니다.
- 나머지 행동은 현재 상태의 허용 목록과 발화 의미에 따라 선택합니다.
- 발화에 없는 정보나 취소 의도를 추측하지 마세요.
반환 형식: {{"user_action": 허용 행동 하나, "change_field": 필드 이름 또는 null}}
JSON 객체 하나만 출력하세요."""
    return [
        {"role": "system", "content": "업무 행동만 판단하고 JSON 객체 하나만 반환합니다."},
        {"role": "user", "content": prompt},
    ]


def validate_action_choice(
    parsed: dict,
    *,
    spec: ServiceWorkflowSpec,
    conversation_state: str,
    current_fields: dict[str, str | None],
) -> dict[str, str | None]:
    require_exact_keys(parsed, {"user_action", "change_field"})
    action = parsed["user_action"]
    target = parsed["change_field"]
    if not isinstance(action, str) or action not in spec.actions_by_state[conversation_state]:
        raise ValueError("action is not allowed for current state")
    if action == "change_detail":
        if not isinstance(target, str) or target not in spec.field_keys:
            raise ValueError("change_detail needs a known change_field")
        if current_fields[target] is None:
            raise ValueError("change_detail target must already be collected")
    elif target is not None:
        raise ValueError("change_field must be null for other actions")
    return {"user_action": action, "change_field": target}
