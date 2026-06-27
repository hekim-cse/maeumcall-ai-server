import pytest
from services.flow.professor.absence.graph import professor_absence_graph


pytestmark = pytest.mark.integration
def test_professor_absence_integration_real_hf():
    result = professor_absence_graph.invoke(
        {
            "user_message": "김개굴 학생인데 오늘 자료구조 수업은 몸이 좋지 않아서 결석한다고 전달드리고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] in [
        "confirming_absence_info",
        "collecting_absence_info",
    ]
    assert result.get("class_name") is not None
    assert result.get("absence_date") is not None
    assert result.get("absence_reason") is not None
    assert result.get("user_name") is not None
    assert result.get("ai_message")
