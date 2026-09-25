from __future__ import annotations

from typing import Any

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    ActionFieldRule,
    action_field_rules_json_for_state,
    allowed_actions_json_for_state,
    allowed_string_for_state,
    build_action_field_contract,
    build_state_action_contract,
    complete_validated_json,
    optional_string,
    require_exact_keys,
    validate_action_field_delta,
)

DEFAULT_ABSENCE_STRUCTURED_RESULT: dict[str, Any] = {
    "intent": "absence_notice",
    "class_name": None,
    "absence_date": None,
    "absence_reason": None,
    "user_name": None,
    "user_action": "unknown",
}
PROFESSOR_ABSENCE_ACTIONS_BY_STATE, PROFESSOR_ABSENCE_USER_ACTIONS = build_state_action_contract(
    {
        "greeting": frozenset({"provide_absence_info", "unknown"}),
        "collecting_absence_info": frozenset({"provide_absence_info", "unknown"}),
        "confirming_absence_info": frozenset(
            {
                "confirm_info",
                "change_class_name",
                "change_absence_date",
                "change_absence_reason",
                "change_user_name",
                "unknown",
            }
        ),
        "absence_noted": frozenset({"go_closing", "unknown"}),
        "closing": frozenset({"end_call", "unknown"}),
    }
)
PROFESSOR_ABSENCE_FIELD_NAMES = frozenset(
    {"class_name", "absence_date", "absence_reason", "user_name"}
)
PROFESSOR_ABSENCE_CHANGE_TARGETS = {
    "change_class_name": "class_name",
    "change_absence_date": "absence_date",
    "change_absence_reason": "absence_reason",
    "change_user_name": "user_name",
}
PROFESSOR_ABSENCE_ACTION_FIELD_CONTRACT = build_action_field_contract(
    field_names=PROFESSOR_ABSENCE_FIELD_NAMES,
    user_actions=PROFESSOR_ABSENCE_USER_ACTIONS,
    rules={action: ActionFieldRule() for action in PROFESSOR_ABSENCE_USER_ACTIONS}
    | {
        "provide_absence_info": ActionFieldRule(
            allowed_fields=PROFESSOR_ABSENCE_FIELD_NAMES,
            require_any=True,
        ),
        **{
            action: ActionFieldRule(allowed_fields=frozenset({field_name}))
            for action, field_name in PROFESSOR_ABSENCE_CHANGE_TARGETS.items()
        },
    },
)


def analyze_professor_absence_user_message(
    conversation_state: str,
    user_message: str,
) -> dict[str, Any]:
    """
    교수님 결석 사유 전달 사용자 발화를 LLM structured output으로 분석한다.

    분석 대상:
    - class_name: 수업명
    - absence_date: 결석 날짜
    - absence_reason: 결석 사유
    - user_name: 학생 이름
    - user_action: 현재 상태에서 사용자의 행동 의도
    """
    prompt = build_professor_absence_analysis_prompt(
        conversation_state=conversation_state,
        user_message=user_message,
    )

    return complete_validated_json(
        [
            {
                "role": "system",
                "content": (
                    "너는 전화 시뮬레이션 서버의 대화 상태 분석기이다. "
                    "반드시 JSON 객체만 출력한다. 설명 문장, markdown, 코드블록은 출력하지 않는다."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        completion=complete_hf_json,
        validator=lambda parsed: _normalize_absence_analysis_result(
            parsed,
            conversation_state=conversation_state,
        ),
        operation="professor_absence_extraction",
    )


def build_professor_absence_analysis_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    allowed_actions = allowed_actions_json_for_state(
        conversation_state,
        PROFESSOR_ABSENCE_ACTIONS_BY_STATE,
    )
    action_field_rules = action_field_rules_json_for_state(
        conversation_state,
        allowed_by_state=PROFESSOR_ABSENCE_ACTIONS_BY_STATE,
        contract=PROFESSOR_ABSENCE_ACTION_FIELD_CONTRACT,
    )
    return f"""
다음은 학생이 교수님께 결석 사유를 전달하는 전화 시뮬레이션입니다.
사용자 발화를 분석해서 JSON 객체만 반환하세요.

현재 conversation_state:
{conversation_state}
현재 상태에서 허용된 user_action:
{allowed_actions}
현재 상태의 행동별 이번 턴 필드 계약:
{action_field_rules}

사용자 발화:
{user_message}

반환 JSON schema:
{{
  "intent": "absence_notice",
  "class_name": string 또는 null,
  "absence_date": string 또는 null,
  "absence_reason": string 또는 null,
  "user_name": string 또는 null,
  "user_action": string
}}

필드 기준:
- class_name: 수업명 또는 과목명. 예: 자료구조, 알고리즘, 운영체제. 없으면 null
- absence_date: 결석 날짜. 예: 오늘, 내일, 이번 주 수요일
- absence_reason: 결석 사유. 예: 몸이 좋지 않음, 병원 방문, 개인 사정, 가족 일정
- user_name: 학생 이름. 이름이 없으면 null
- user_action:
  - collecting_absence_info 상태 또는 greeting 상태:
    - 결석 정보를 말하면 "provide_absence_info"
    - 불명확하면 "unknown"
  - confirming_absence_info 상태:
    - 수집된 정보가 맞다고 확인하면 "confirm_info"
    - 수업명을 바꾸려 하면 "change_class_name"
    - 결석 날짜를 바꾸려 하면 "change_absence_date"
    - 결석 사유를 바꾸려 하면 "change_absence_reason"
    - 이름을 바꾸려 하면 "change_user_name"
    - 불명확하면 "unknown"
  - absence_noted 상태:
    - 감사/확인/마무리 발화이면 "go_closing"
    - 불명확하면 "unknown"
  - closing 상태:
    - 감사/확인/마무리 발화이면 "end_call"
    - 불명확하면 "unknown"

주의:
- JSON 객체만 출력하세요.
- markdown 코드블록을 사용하지 마세요.
- 모르는 값은 null로 두세요.
- user_action은 반드시 위 목록 중 하나로 작성하세요.
"""


def _normalize_absence_analysis_result(
    parsed: dict[str, Any],
    *,
    conversation_state: str,
) -> dict[str, Any]:
    require_exact_keys(parsed, DEFAULT_ABSENCE_STRUCTURED_RESULT)
    result = DEFAULT_ABSENCE_STRUCTURED_RESULT.copy()

    if parsed.get("intent") != "absence_notice":
        raise ValueError("intent must be absence_notice")

    for key in ["class_name", "absence_date", "absence_reason", "user_name"]:
        result[key] = optional_string(parsed, key)

    result["user_action"] = allowed_string_for_state(
        parsed,
        "user_action",
        conversation_state=conversation_state,
        allowed_by_state=PROFESSOR_ABSENCE_ACTIONS_BY_STATE,
    )

    validate_action_field_delta(
        {key: result[key] for key in PROFESSOR_ABSENCE_FIELD_NAMES},
        user_action=result["user_action"],
        contract=PROFESSOR_ABSENCE_ACTION_FIELD_CONTRACT,
    )

    return result
