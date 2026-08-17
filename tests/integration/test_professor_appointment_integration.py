import pytest

from services.flow.professor.appointment.graph import professor_appointment_graph

pytestmark = pytest.mark.integration


def test_professor_appointment_integration_real_hf():
    result = professor_appointment_graph.invoke(
        {
            "user_message": "김개굴 학생인데 내일 오후 3시에 진로 상담으로 면담 예약하고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] in [
        "confirming_info",
        "collecting_appointment_info",
    ]
    assert result.get("appointment_purpose") is not None
    assert result.get("date") is not None
    assert result.get("time") is not None
    assert result.get("user_name") is not None
    assert result.get("ai_message")
