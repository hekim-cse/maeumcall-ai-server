from __future__ import annotations

from typing import Any, Dict

from llm.huggingface_provider import complete_hf_json
from llm.structured_output import (
    allowed_string,
    complete_validated_json,
    optional_string,
)


DEFAULT_ASSIGNMENT_STRUCTURED_RESULT: Dict[str, Any] = {
    "intent": "assignment_inquiry",
    "assignment_topic": None,
    "question": None,
    "user_name": None,
    "user_action": "unknown",
}


def analyze_professor_assignment_user_message(
    conversation_state: str,
    user_message: str,
) -> Dict[str, Any]:
    """
    교수님 과제 문의 사용자 발화를 LLM structured output으로 분석한다.

    분석 대상:
    - assignment_topic: 과제 주제 또는 유형
    - question: 사용자의 과제 관련 질문
    - user_name: 학생 이름
    - user_action: 현재 상태에서 사용자의 행동 의도
    """
    prompt = build_professor_assignment_analysis_prompt(
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
        validator=_normalize_assignment_analysis_result,
        operation="professor_assignment_extraction",
    )


def build_professor_assignment_analysis_prompt(
    conversation_state: str,
    user_message: str,
) -> str:
    return f"""
다음은 교수님께 과제 관련 문의를 하는 전화 시뮬레이션입니다.
사용자 발화를 분석해서 JSON 객체만 반환하세요.

현재 conversation_state:
{conversation_state}

사용자 발화:
{user_message}

반환 JSON schema:
{{
  "intent": "assignment_inquiry",
  "assignment_topic": string 또는 null,
  "question": string 또는 null,
  "user_name": string 또는 null,
  "user_action": string
}}

필드 기준:
- assignment_topic: 과제 제출 형식, 제출 기한, 보고서, 발표, 팀플 등 문의 대상
- question: 사용자가 실제로 궁금해하는 질문 내용
- user_name: 학생 이름. 이름이 없으면 null
- user_action:
  - collecting_assignment_info 상태 또는 greeting 상태:
    - 과제 문의 정보를 말하면 "provide_assignment_info"
    - 불명확하면 "unknown"
  - answering_assignment_question 상태:
    - 추가 질문을 원하면 "ask_follow_up"
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


def _normalize_assignment_analysis_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_ASSIGNMENT_STRUCTURED_RESULT.copy()

    if parsed.get("intent") != "assignment_inquiry":
        raise ValueError("intent must be assignment_inquiry")

    for key in ["assignment_topic", "question", "user_name"]:
        result[key] = optional_string(parsed, key)

    allowed_actions = {
        "provide_assignment_info",
        "ask_follow_up",
        "go_closing",
        "end_call",
        "unknown",
    }

    result["user_action"] = allowed_string(parsed, "user_action", allowed_actions)

    return result
