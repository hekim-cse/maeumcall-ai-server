from __future__ import annotations

from typing import Any, Dict

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    allowed_string,
    complete_validated_json,
    optional_string,
)


DEFAULT_RESTAURANT_STRUCTURED_RESULT = {
    "intent": "reservation",
    "date": None,
    "time": None,
    "party_size": None,
    "user_name": None,
    "user_action": "unknown",
    "selected_time": None,
}


def analyze_restaurant_reservation_user_message(
    conversation_state: str,
    user_message: str,
) -> Dict[str, Any]:
    """
    식당 예약 사용자 발화를 structured output으로 분석한다.
    """
    prompt = f"""
너는 식당 예약 전화 시뮬레이션 서버의 대화 분석기이다.

현재 conversation_state:
{conversation_state}

사용자 발화:
{user_message}

아래 JSON 형식으로만 응답해라.
설명 문장, markdown, 코드블록은 출력하지 마라.

{{
  "intent": "reservation",
  "date": string 또는 null,
  "time": string 또는 null,
  "party_size": string 또는 null,
  "user_name": string 또는 null,
  "user_action": string,
  "selected_time": string 또는 null
}}

필드 설명:
- date: 예약 날짜. 예: "오늘", "내일", "모레", "이번 주말", "6월 10일"
- time: 예약 시간. 예: "오후 7시", "저녁 8시", "19시"
- party_size: 예약 인원. 예: "2명", "4명"
- user_name: 예약자 이름
- selected_time: 예약 불가 상태에서 사용자가 선택한 대안 시간
- user_action은 아래 중 하나만 사용한다.

가능한 user_action:
- continue_collecting
- confirm
- change_date
- change_time
- change_party_size
- change_user_name
- change_info
- confirm_reservation
- ask_other_time
- select_alternative_time
- go_closing
- end_call
- unknown

상태별 판단 기준:
- collecting_reservation_info 또는 greeting: 예약 정보를 말하면 continue_collecting
- confirming_info: 정보가 맞다고 하면 confirm, 날짜/시간/인원/이름 변경 요청이면 해당 change 액션
- reservation_available: 예약 진행/확정이면 confirm_reservation, 다른 시간 요청이면 ask_other_time
- reservation_unavailable: 제안 시간 선택이면 select_alternative_time, selected_time에 선택 시간을 넣는다
- reservation_confirmed: 감사/확인/마무리 응답이면 go_closing
- closing: 더 할 말 없거나 감사 인사면 end_call
"""

    return complete_validated_json(
        [
            {
                "role": "system",
                "content": "너는 사용자 발화를 JSON으로만 분석하는 분류기이다.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        completion=complete_hf_json,
        validator=_normalize_restaurant_analysis_result,
        operation="restaurant_extraction",
    )


def _normalize_restaurant_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_RESTAURANT_STRUCTURED_RESULT.copy()

    if parsed.get("intent") != "reservation":
        raise ValueError("intent must be reservation")

    for key in ["date", "time", "party_size", "user_name", "selected_time"]:
        result[key] = optional_string(parsed, key)

    allowed_actions = {
        "continue_collecting",
        "confirm",
        "change_date",
        "change_time",
        "change_party_size",
        "change_user_name",
        "change_info",
        "confirm_reservation",
        "ask_other_time",
        "select_alternative_time",
        "go_closing",
        "end_call",
        "unknown",
    }

    result["user_action"] = allowed_string(parsed, "user_action", allowed_actions)

    return result
