from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.professor.absence.state import ProfessorAbsenceState


def professor_absence_greeting_node(state: ProfessorAbsenceState) -> Dict:
    """
    교수님 결석 사유 전달 LangGraph 최소 진입 확인용 노드이다.

    이후 수업명, 결석 날짜, 결석 사유, 학생 이름 수집 흐름으로 확장한다.
    """
    professor_name = state.get("professor_name") or "교수님"

    return {
        "intent": "absence_notice",
        "professor_name": professor_name,
        "conversation_state": "collecting_absence_info",
        "ai_message": (
            f"네, {professor_name}입니다. "
            "결석 사유 전달과 관련해서 어떤 사유인지 말씀해주시겠습니까?"
        ),
        "recommended_replies": [
            "오늘 수업에 결석하게 되어 연락드렸습니다.",
            "몸이 좋지 않아 병원에 가게 되었습니다.",
            "김개굴 학생입니다. 결석 사유를 말씀드리려고 연락드렸습니다.",
        ],
        "should_end_call": False,
    }


def build_professor_absence_graph():
    builder = StateGraph(ProfessorAbsenceState)

    builder.add_node("professor_absence_greeting", professor_absence_greeting_node)

    builder.add_edge(START, "professor_absence_greeting")
    builder.add_edge("professor_absence_greeting", END)

    return builder.compile()


professor_absence_graph = build_professor_absence_graph()
