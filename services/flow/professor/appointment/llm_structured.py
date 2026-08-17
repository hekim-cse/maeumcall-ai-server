from __future__ import annotations

from typing import Any, Dict

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    allowed_string,
    complete_validated_json,
    optional_string,
)


DEFAULT_APPOINTMENT_STRUCTURED_RESULT: Dict[str, Any] = {
    "intent": "appointment_booking",
    "appointment_purpose": None,
    "date": None,
    "time": None,
    "user_name": None,
    "user_action": "unknown",
}


def analyze_professor_appointment_user_message(
    conversation_state: str,
    user_message: str,
) -> Dict[str, Any]:
    """
    교수님 면담 예약 사용자 발화를 LLM structured output으로 분석한다.

    분석 대상:
    - appointment_purpose: 면담 목적
    - date: 희망 날짜
    - time: 희망 시간
    - user_name: 학생 이름
    - user_action: 현재 상태에서 사용자의 행동 의도
    """
    prompt = build_professor_appointment_analysis_prompt(
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
        validator=_normalize_appointment_analysis_result,
        operation="professor_appointment_extraction",
    )


def build_professor_appointment_analysis_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    return f"""
다음은 학생이 교수님께 면담 예약을 요청하는 전화 시뮬레이션입니다.
사용자 발화를 분석해서 JSON 객체만 반환하세요.

현재 conversation_state:
{conversation_state}

사용자 발화:
{user_message}

반환 JSON schema:
{{
  "intent": "appointment_booking",
  "appointment_purpose": string 또는 null,
  "date": string 또는 null,
  "time": string 또는 null,
  "user_name": string 또는 null,
  "user_action": string
}}

필드 기준:
- appointment_purpose: 면담 목적. 예: 진로 상담, 과제, 수업, 상담
- date: 희망 날짜. 예: 오늘, 내일, 이번 주 수요일, 다음 주 월요일
- time: 희망 시간. 예: 오후 3시, 오전 10시
- user_name: 학생 이름. 이름이 없으면 null
- user_action:
  - collecting_appointment_info 상태 또는 greeting 상태:
    - 면담 예약 정보를 말하면 "provide_appointment_info"
    - 불명확하면 "unknown"
  - confirming_info 상태:
    - 수집된 정보가 맞다고 확인하면 "confirm_info"
    - 면담 목적을 바꾸려 하면 "change_purpose"
    - 날짜를 바꾸려 하면 "change_date"
    - 시간을 바꾸려 하면 "change_time"
    - 이름을 바꾸려 하면 "change_user_name"
    - 불명확하면 "unknown"
  - appointment_confirmed 상태:
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


def _normalize_appointment_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_APPOINTMENT_STRUCTURED_RESULT.copy()

    if parsed.get("intent") != "appointment_booking":
        raise ValueError("intent must be appointment_booking")

    for key in ["appointment_purpose", "date", "time", "user_name"]:
        result[key] = optional_string(parsed, key)

    allowed_actions = {
        "provide_appointment_info",
        "confirm_info",
        "change_purpose",
        "change_date",
        "change_time",
        "change_user_name",
        "go_closing",
        "end_call",
        "unknown",
    }

    result["user_action"] = allowed_string(parsed, "user_action", allowed_actions)

    return result
