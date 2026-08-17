from __future__ import annotations

from typing import Any

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    allowed_string,
    complete_validated_json,
    optional_string,
)

DEFAULT_STUDY_ROOM_STRUCTURED_RESULT: dict[str, Any] = {
    "intent": "reservation",
    "date": None,
    "start_time": None,
    "duration": None,
    "party_size": None,
    "user_name": None,
    "user_action": "unknown",
    "selected_time": None,
}
STUDY_ROOM_USER_ACTIONS = frozenset(
    {
        "continue_collecting",
        "confirm",
        "change_date",
        "change_start_time",
        "change_duration",
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
)


def analyze_study_room_reservation_user_message(
    conversation_state: str,
    user_message: str,
) -> dict[str, Any]:
    """
    스터디룸 예약 사용자 발화를 LLM structured output으로 분석한다.

    분석 대상:
    - date
    - start_time
    - duration
    - party_size
    - user_name
    - user_action
    - selected_time
    """
    prompt = build_study_room_reservation_analysis_prompt(
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
        validator=_normalize_study_room_analysis_result,
        operation="study_room_extraction",
    )


def build_study_room_reservation_analysis_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    return f"""
다음은 사용자가 스터디룸 예약 전화를 연습하는 시뮬레이션입니다.
사용자 발화를 분석해서 JSON 객체만 반환하세요.

현재 conversation_state:
{conversation_state}

사용자 발화:
{user_message}

반환 JSON schema:
{{
  "intent": "reservation",
  "date": string 또는 null,
  "start_time": string 또는 null,
  "duration": string 또는 null,
  "party_size": string 또는 null,
  "user_name": string 또는 null,
  "user_action": string,
  "selected_time": string 또는 null
}}

필드 기준:
- date: 이용 날짜. 예: 오늘, 내일, 모레, 이번 주말, 6월 20일
- start_time: 시작 시간. 예: 오후 2시, 오전 10시, 7시
- duration: 이용 시간. 예: 2시간, 3시간
- party_size: 이용 인원. 예: 2명, 4명
- user_name: 예약자 이름. 이름이 없으면 null
- selected_time: 대체 시간 선택 발화에서 선택한 시간. 예: 오후 3시. 없으면 null
- user_action:
  - greeting 또는 collecting_reservation_info 상태:
    - 예약 정보를 말하면 "continue_collecting"
    - 불명확하면 "unknown"
  - confirming_info 상태:
    - 정보가 맞다고 확인하면 "confirm"
    - 날짜를 바꾸려 하면 "change_date"
    - 시작 시간을 바꾸려 하면 "change_start_time"
    - 이용 시간을 바꾸려 하면 "change_duration"
    - 인원을 바꾸려 하면 "change_party_size"
    - 예약자 이름을 바꾸려 하면 "change_user_name"
    - 전체 정보가 틀렸다고 하면 "change_info"
    - 불명확하면 "unknown"
  - reservation_available 상태:
    - 예약 확정을 원하면 "confirm_reservation"
    - 다른 시간을 원하면 "ask_other_time"
    - 날짜 변경을 원하면 "change_date"
    - 불명확하면 "unknown"
  - reservation_unavailable 상태:
    - 제안된 대체 시간을 선택하면 "select_alternative_time"
    - 다른 시간을 원하면 "ask_other_time"
    - 날짜 변경을 원하면 "change_date"
    - 불명확하면 "unknown"
  - reservation_confirmed 상태:
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


def _normalize_study_room_analysis_result(parsed: dict[str, Any]) -> dict[str, Any]:
    result = DEFAULT_STUDY_ROOM_STRUCTURED_RESULT.copy()

    if parsed.get("intent") != "reservation":
        raise ValueError("intent must be reservation")

    for key in [
        "date",
        "start_time",
        "duration",
        "party_size",
        "user_name",
        "selected_time",
    ]:
        result[key] = optional_string(parsed, key)

    result["user_action"] = allowed_string(parsed, "user_action", STUDY_ROOM_USER_ACTIONS)

    return result
