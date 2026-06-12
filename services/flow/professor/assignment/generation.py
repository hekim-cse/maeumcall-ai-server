from __future__ import annotations

from typing import Dict

from services.flow.professor.assignment.llm_client import (
    complete_professor_assignment_ai_message,
)
from services.flow.professor.assignment.templates import (
    build_professor_assignment_template_message,
)
from services.flow.professor.assignment.validator import (
    is_valid_professor_assignment_response,
)


def build_professor_assignment_generation_prompt(state: Dict) -> str:
    """
    교수님 과제 문의 응답 생성을 위한 프롬프트를 구성한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_assignment_info"
    missing_fields = state.get("missing_fields") or []

    return f"""
현재 시나리오: 교수님 과제 문의
현재 대화 상태: {conversation_state}

현재까지 확인된 정보:
- 교수님 호칭: {state.get("professor_name") or "교수님"}
- 과제 주제/유형: {state.get("assignment_topic") or "미확인"}
- 질문 내용: {state.get("question") or "미확인"}
- 학생 이름: {state.get("user_name") or "미확인"}
- 부족한 정보: {", ".join(missing_fields) if missing_fields else "없음"}

사용자 발화:
{state.get("user_message") or ""}

응답 규칙:
- 한국어로 답한다.
- 교수님이 학생에게 답하는 말투로 작성한다.
- 공손하지만 살짝 딱딱한 톤을 유지한다.
- 반말, 농담, 가벼운 표현을 사용하지 않는다.
- 부족한 정보가 있으면 가장 먼저 필요한 정보 하나만 질문한다.
- 질문 정보가 충분하면 과제 문의에 대해 짧게 안내한다.
- 1문장 또는 2문장으로 짧게 답한다.
"""


def generate_professor_assignment_ai_message(state: Dict) -> str:
    """
    교수님 과제 문의 ai_message를 생성한다.

    원칙:
    - LLM 응답을 우선 사용한다.
    - 상태 의미나 말투 기준에 맞지 않으면 template fallback을 사용한다.
    """
    conversation_state = state.get("conversation_state") or "collecting_assignment_info"
    fallback = build_professor_assignment_template_message(conversation_state, state)

    try:
        prompt = build_professor_assignment_generation_prompt(state)
        ai_message = complete_professor_assignment_ai_message(prompt)

        if is_valid_professor_assignment_response(conversation_state, ai_message):
            return ai_message

        return fallback

    except Exception:
        return fallback
