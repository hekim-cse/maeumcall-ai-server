from __future__ import annotations

import json
from typing import Any, Dict

from llm.huggingface_provider import complete_hf_messages


DEFAULT_HAIR_SALON_STRUCTURED_RESULT: Dict[str, Any] = {
    "intent": "reservation",
    "date": None,
    "time": None,
    "service_type": None,
    "designer": None,
    "user_name": None,
    "user_action": "unknown",
    "selected_time": None,
}


def analyze_hair_salon_reservation_user_message(
    conversation_state: str,
    user_message: str,
) -> Dict[str, Any]:
    """
    미용실 예약 사용자 발화를 structured output으로 분석한다.

    기존 정규식/키워드 기반 extractor와 action parser를 대체한다.
    """
    prompt = build_hair_salon_structured_prompt(conversation_state, user_message)

    try:
        raw = complete_hf_messages(
            [
                {
                    "role": "system",
                    "content": (
                        "너는 미용실 예약 통화 시뮬레이션 서버의 정보 추출기이다. "
                        "반드시 JSON 객체만 반환한다. 설명 문장, markdown, 코드블록은 출력하지 않는다."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
        )

        parsed = _parse_json_object(raw)
        return _normalize_hair_salon_analysis_result(parsed)

    except Exception:
        return DEFAULT_HAIR_SALON_STRUCTURED_RESULT.copy()


def build_hair_salon_structured_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    return f"""
현재 대화 상태: {conversation_state}
사용자 발화: {user_message}

사용자 발화에서 미용실 예약에 필요한 정보를 JSON으로 추출해라.

반환 JSON schema:
{{
  "intent": "reservation",
  "date": string | null,
  "time": string | null,
  "service_type": string | null,
  "designer": string | null,
  "user_name": string | null,
  "user_action": string,
  "selected_time": string | null
}}

필드 설명:
- date: 예약 날짜. 예: "오늘", "내일", "모레", "이번 주말", "6월 10일"
- time: 예약 희망 시간. 예: "오후 2시", "저녁 6시", "가장 빠른 시간"
- service_type: 시술 종류. 예: "커트", "펌", "염색", "다운펌", "볼륨매직", "클리닉"
- designer: 디자이너 이름 또는 "가능한 디자이너"
  - 사용자가 "아무나", "상관없어요", "가능한 선생님"처럼 말하면 "가능한 디자이너"로 반환한다.
- user_name: 예약자 이름
- selected_time: 예약 불가 상태에서 사용자가 고른 대안 시간. 예: "오후 3시"

user_action 허용값:
- continue_collecting: 예약 정보를 추가로 제공하는 경우
- confirm: 확인 상태에서 예약 정보가 맞다고 하는 경우
- change_date: 날짜를 바꾸려는 경우
- change_time: 시간을 바꾸려는 경우
- change_service_type: 시술 종류를 바꾸려는 경우
- change_designer: 디자이너를 바꾸려는 경우
- change_user_name: 예약자 이름을 바꾸려는 경우
- change_info: 어떤 정보를 바꾸려 하지만 항목이 불명확한 경우
- confirm_reservation: 예약 가능 안내 후 예약 확정을 요청하는 경우
- ask_other_time: 다른 시간대를 요청하는 경우
- select_alternative_time: 예약 불가 안내 후 제안된 대안 시간을 선택하는 경우
- go_closing: 예약 완료 후 감사/확인 인사를 하는 경우
- end_call: 마무리 상태에서 통화를 종료해도 되는 경우
- unknown: 판단 불가

상태별 판단 기준:
- confirming_info에서 "네, 맞습니다"는 confirm
- confirming_info에서 "시간 바꿀게요"는 change_time
- confirming_info에서 "시술 변경할게요"는 change_service_type
- confirming_info에서 "디자이너 바꿀게요"는 change_designer
- reservation_available에서 "네, 예약해주세요"는 confirm_reservation
- reservation_available에서 "다른 시간 가능할까요"는 ask_other_time
- reservation_unavailable에서 "오후 3시로 할게요"는 select_alternative_time, selected_time은 "오후 3시"
- reservation_confirmed에서 "네, 감사합니다"는 go_closing
- closing에서 "네, 감사합니다"는 end_call

주의:
- 값이 없으면 null로 반환한다.
- user_action은 반드시 허용값 중 하나만 사용한다.
- JSON 객체만 반환한다.
"""


def _parse_json_object(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("JSON object not found")

    return json.loads(text[start : end + 1])


def _normalize_hair_salon_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_HAIR_SALON_STRUCTURED_RESULT.copy()

    if not isinstance(parsed, dict):
        return result

    result["intent"] = "reservation"

    for key in [
        "date",
        "time",
        "service_type",
        "designer",
        "user_name",
        "selected_time",
    ]:
        value = parsed.get(key)
        if isinstance(value, str):
            value = value.strip() or None
        else:
            value = None
        result[key] = value

    user_action = parsed.get("user_action")
    allowed_actions = {
        "continue_collecting",
        "confirm",
        "change_date",
        "change_time",
        "change_service_type",
        "change_designer",
        "change_user_name",
        "change_info",
        "confirm_reservation",
        "ask_other_time",
        "select_alternative_time",
        "go_closing",
        "end_call",
        "unknown",
    }

    if user_action in allowed_actions:
        result["user_action"] = user_action
    else:
        result["user_action"] = "unknown"

    return result
