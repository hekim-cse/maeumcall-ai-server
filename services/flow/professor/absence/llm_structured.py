from __future__ import annotations

import json
from typing import Any, Dict

from llm.huggingface_provider import complete_hf_messages


DEFAULT_ABSENCE_STRUCTURED_RESULT: Dict[str, Any] = {
    "intent": "absence_notice",
    "class_name": None,
    "absence_date": None,
    "absence_reason": None,
    "user_name": None,
    "user_action": "unknown",
}


def analyze_professor_absence_user_message(
    conversation_state: str,
    user_message: str,
) -> Dict[str, Any]:
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

    try:
        raw = complete_hf_messages(
            [
                {
                    "role": "system",
                    "content": (
                        "너는 전화 시뮬레이션 서버의 대화 상태 분석기이다. "
                        "반드시 JSON 객체만 출력한다. 설명 문장, markdown, 코드블록은 출력하지 않는다."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
        )

        parsed = _parse_json_object(raw)
        return _normalize_absence_analysis_result(parsed)

    except Exception:
        return DEFAULT_ABSENCE_STRUCTURED_RESULT.copy()


def build_professor_absence_analysis_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    return f"""
다음은 학생이 교수님께 결석 사유를 전달하는 전화 시뮬레이션입니다.
사용자 발화를 분석해서 JSON 객체만 반환하세요.

현재 conversation_state:
{conversation_state}

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


def _parse_json_object(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("JSON object not found in LLM output")

    return json.loads(text[start : end + 1])


def _normalize_absence_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_ABSENCE_STRUCTURED_RESULT.copy()

    if not isinstance(parsed, dict):
        return result

    result["intent"] = "absence_notice"

    for key in ["class_name", "absence_date", "absence_reason", "user_name"]:
        value = parsed.get(key)
        if isinstance(value, str):
            value = value.strip() or None
        else:
            value = None
        result[key] = value

    user_action = parsed.get("user_action")
    allowed_actions = {
        "provide_absence_info",
        "confirm_info",
        "change_absence_date",
        "change_absence_reason",
        "change_user_name",
        "go_closing",
        "end_call",
        "unknown",
    }

    if user_action in allowed_actions:
        result["user_action"] = user_action
    else:
        result["user_action"] = "unknown"

    return result
