from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.professor.appointment.state import ProfessorAppointmentState


def professor_appointment_greeting_node(state: ProfessorAppointmentState) -> Dict:
    """
    교수님 면담 예약 LangGraph 최소 진입 확인용 노드이다.

    이후 면담 목적, 날짜, 시간, 학생 이름 수집 흐름으로 확장한다.
    """
    professor_name = state.get("professor_name") or "교수님"

    return {
        "intent": "appointment_booking",
        "professor_name": professor_name,
        "conversation_state": "collecting_appointment_info",
        "ai_message": (
            f"네, {professor_name}입니다. "
            "면담 예약을 원하시는군요. 어떤 내용으로 면담을 희망하시는지 말씀해주시겠어요?"
        ),
        "recommended_replies": [
            "진로 상담 관련해서 면담을 요청드리고 싶습니다.",
            "과제 관련해서 면담 가능하실지 여쭤보고 싶습니다.",
            "이번 주 수요일 오후에 면담 가능하실까요?",
        ],
        "should_end_call": False,
    }


def build_professor_appointment_graph():
    builder = StateGraph(ProfessorAppointmentState)

    builder.add_node("professor_appointment_greeting", professor_appointment_greeting_node)

    builder.add_edge(START, "professor_appointment_greeting")
    builder.add_edge("professor_appointment_greeting", END)

    return builder.compile()


professor_appointment_graph = build_professor_appointment_graph()
