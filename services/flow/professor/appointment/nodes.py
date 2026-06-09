from __future__ import annotations

from typing import Dict

from services.flow.professor.appointment.state import ProfessorAppointmentState
from services.flow.professor.appointment.extractor import extract_professor_appointment_info
from services.flow.professor.appointment.generation import generate_professor_appointment_ai_message
from services.flow.professor.appointment.policy import get_missing_professor_appointment_fields
from services.flow.professor.appointment.replies import get_professor_appointment_recommended_replies


def extract_professor_appointment_info_node(state: ProfessorAppointmentState) -> Dict:
    """
    사용자 발화에서 교수님 면담 예약 정보를 추출한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_professor_appointment_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent") or "appointment_booking",
        "professor_name": state.get("professor_name") or "교수님",
        "appointment_purpose": (
            extracted.get("appointment_purpose") or state.get("appointment_purpose")
        ),
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
        "user_name": extracted.get("user_name") or state.get("user_name"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
        "recommended_replies": state.get("recommended_replies") or [],
        "should_end_call": state.get("should_end_call", False),
    }


def decide_professor_appointment_state_node(state: ProfessorAppointmentState) -> Dict:
    """
    교수님 면담 예약 상태를 결정한다.
    """
    current_state = state.get("conversation_state") or "greeting"

    missing_fields = get_missing_professor_appointment_fields(state)

    if missing_fields:
        return {
            "missing_fields": missing_fields,
            "conversation_state": "collecting_appointment_info",
        }

    return {
        "missing_fields": [],
        "conversation_state": "confirming_info",
        "user_action": "confirm_info_ready",
    }


def generate_professor_appointment_response_node(state: ProfessorAppointmentState) -> Dict:
    """
    교수님 면담 예약 응답 생성 노드이다.

    LLM 응답을 우선 사용하고, 상태나 말투 기준에 맞지 않으면 fallback한다.
    """
    ai_message = generate_professor_appointment_ai_message(state)

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


def attach_professor_appointment_recommended_replies_node(
    state: ProfessorAppointmentState,
) -> Dict:
    """
    현재 상태에 맞는 추천 답변을 붙인다.
    """
    conversation_state = state.get("conversation_state") or "collecting_appointment_info"

    return {
        "recommended_replies": get_professor_appointment_recommended_replies(
            conversation_state
        ),
    }
