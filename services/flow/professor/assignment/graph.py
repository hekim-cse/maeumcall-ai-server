from __future__ import annotations

from typing import Dict

from langgraph.graph import StateGraph, START, END

from services.flow.professor.assignment.state import ProfessorAssignmentState


def professor_assignment_greeting_node(state: ProfessorAssignmentState) -> Dict:
    """
    교수님 과제 문의 LangGraph 최소 진입 확인용 노드이다.

    이후 과제명, 질문 내용, 학생 이름 수집 흐름으로 확장한다.
    """
    professor_name = state.get("professor_name") or "교수님"

    return {
        "intent": "assignment_inquiry",
        "professor_name": professor_name,
        "conversation_state": "collecting_assignment_info",
        "ai_message": (
            f"네, {professor_name}입니다. "
            "과제와 관련해 어떤 부분이 궁금한지 말씀해주시겠습니까?"
        ),
        "recommended_replies": [
            "과제 제출 형식을 여쭤보고 싶습니다.",
            "과제 제출 기한을 확인하고 싶습니다.",
            "김개굴 학생입니다. 과제 관련해서 질문드리고 싶습니다.",
        ],
        "should_end_call": False,
    }


def build_professor_assignment_graph():
    builder = StateGraph(ProfessorAssignmentState)

    builder.add_node("professor_assignment_greeting", professor_assignment_greeting_node)

    builder.add_edge(START, "professor_assignment_greeting")
    builder.add_edge("professor_assignment_greeting", END)

    return builder.compile()


professor_assignment_graph = build_professor_assignment_graph()
