import pytest
from services.flow.professor.assignment.graph import professor_assignment_graph


pytestmark = pytest.mark.integration
def test_professor_assignment_integration_real_hf():
    result = professor_assignment_graph.invoke(
        {
            "user_message": "자료구조 과제 제출 형식이 어떻게 되는지 김개굴 학생이 여쭤보고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] in [
        "answering_assignment_question",
        "collecting_assignment_info",
    ]
    assert result.get("assignment_topic") is not None
    assert result.get("user_name") is not None
    assert result.get("ai_message")
