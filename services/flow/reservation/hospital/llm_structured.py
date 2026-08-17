from __future__ import annotations

from typing import Any

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    allowed_string,
    complete_validated_json,
    optional_string,
)

DEFAULT_HOSPITAL_STRUCTURED_RESULT: dict[str, Any] = {
    "intent": None,
    "department": None,
    "date": None,
    "time": None,
    "user_name": None,
    "user_action": "unknown",
    "selected_time": None,
}
HOSPITAL_USER_ACTIONS = frozenset(
    {
        "continue_collecting",
        "confirm_reservation_info",
        "change_department",
        "change_date",
        "change_time",
        "change_user_name",
        "lookup_availability",
        "confirm_available_time",
        "ask_other_time",
        "select_alternative_time",
        "go_closing",
        "end_call",
        "unknown",
    }
)


def analyze_hospital_reservation_user_message(
    conversation_state: str,
    user_message: str,
) -> dict[str, Any]:
    """
    병원 예약 사용자 발화를 structured output(JSON)으로 분석한다.

    분석 대상:
    - intent: reservation 또는 None
    - department: 진료과
    - date: 예약 날짜
    - time: 예약 시간
    - user_name: 예약자 이름
    - user_action: 현재 상태에서 사용자의 행동
    - selected_time: 대안 시간 선택값
    """
    messages = [
        {
            "role": "system",
            "content": _build_system_prompt(),
        },
        {
            "role": "user",
            "content": _build_user_prompt(conversation_state, user_message),
        },
    ]

    return complete_validated_json(
        messages,
        completion=complete_hf_json,
        validator=_normalize_hospital_analysis_result,
        operation="hospital_extraction",
    )


def _build_system_prompt() -> str:
    return """
너는 병원 예약 전화 상황의 사용자 발화를 분석하는 JSON parser이다.

반드시 JSON 객체 하나만 출력한다.
markdown, 설명, 코드블록, 따옴표 밖 문장은 출력하지 않는다.

출력 형식:
{
  "intent": "reservation" | null,
  "department": string | null,
  "date": string | null,
  "time": string | null,
  "user_name": string | null,
  "user_action": string,
  "selected_time": string | null
}

필드 규칙:
- intent는 병원 진료 예약 의도가 있으면 "reservation", 아니면 null이다.
- department는 내과, 피부과, 정형외과, 이비인후과 같은 진료과이다.
- date는 오늘, 내일, 모레, 다음 주 월요일, 6월 10일 같은 예약 날짜이다.
- time은 오전, 오후, 오전 10시, 오후 3시 같은 시간 표현이다.
- user_name은 예약자 이름이며 발화에 없으면 null이다.
- selected_time은 사용자가 대안 시간 중 하나를 고른 경우에만 채운다.
- 알 수 없는 값은 null로 둔다.

conversation_state별 user_action 규칙:

1) confirming_info
- 예약 정보가 맞다고 확인하면 "confirm_reservation_info"
- 진료과를 바꾸려 하면 "change_department"
- 날짜를 바꾸려 하면 "change_date"
- 시간을 바꾸려 하면 "change_time"
- 예약자 이름을 바꾸려 하면 "change_user_name"
- 알 수 없으면 "unknown"

2) checking_availability
- 예약 가능 여부 확인을 기다리거나 진행하면 "lookup_availability"

3) reservation_available
- 안내된 가능 시간으로 예약하겠다고 하면 "confirm_available_time"
- 다른 시간/다른 시간대를 물으면 "ask_other_time"
- 알 수 없으면 "unknown"

4) reservation_unavailable
- 다른 날짜를 원하면 "change_date"
- 다른 시간이나 가능한 시간을 물으면 "ask_other_time"
- 특정 대안 시간을 고르면 "select_alternative_time"
- 알 수 없으면 "unknown"

5) suggest_alternative
- 특정 대안 시간을 고르면 "select_alternative_time"
- 다른 날짜를 원하면 "change_date"
- 다른 시간을 더 물으면 "ask_other_time"
- 알 수 없으면 "unknown"

6) reservation_confirmed
- 감사 인사나 마무리 응답이면 "go_closing"

7) closing
- 감사 인사나 더 이상 문의가 없다는 응답이면 "end_call"

그 외 상태:
- 예약 정보를 말하는 중이면 "unknown" 또는 "continue_collecting"
""".strip()


def _build_user_prompt(conversation_state: str, user_message: str) -> str:
    return f"""
conversation_state: {conversation_state}
user_message: {user_message}

위 발화를 JSON으로 분석해라.
""".strip()


def _normalize_hospital_analysis_result(parsed: dict[str, Any]) -> dict[str, Any]:
    if "intent" not in parsed:
        raise ValueError("intent is required")
    intent = parsed.get("intent")
    if intent not in {"reservation", None}:
        raise ValueError("intent must be reservation or null")

    result = DEFAULT_HOSPITAL_STRUCTURED_RESULT.copy()
    result["intent"] = intent

    for key in ["department", "date", "time", "user_name", "selected_time"]:
        result[key] = optional_string(parsed, key)

    result["user_action"] = allowed_string(parsed, "user_action", HOSPITAL_USER_ACTIONS)

    return result
