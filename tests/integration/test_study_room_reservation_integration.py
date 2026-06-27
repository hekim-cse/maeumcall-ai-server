import pytest
from services.flow.reservation.study_room.graph import study_room_reservation_graph


pytestmark = pytest.mark.integration
def test_study_room_reservation_integration_real_hf():
    result = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 2시부터 2시간 동안 4명이 쓸 스터디룸 예약하고 싶고 이름은 김개굴입니다.",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] in [
        "confirming_info",
        "collecting_reservation_info",
    ]
    assert result.get("date") is not None
    assert result.get("start_time") is not None
    assert result.get("duration") is not None
    assert result.get("party_size") is not None
    assert result.get("user_name") is not None
    assert result.get("ai_message")
