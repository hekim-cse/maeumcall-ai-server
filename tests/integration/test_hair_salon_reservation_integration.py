import pytest
from services.flow.reservation.hair_salon.graph import hair_salon_reservation_graph


pytestmark = pytest.mark.integration
def test_hair_salon_reservation_integration_real_hf():
    result = hair_salon_reservation_graph.invoke(
        {
            "user_message": "내일 오후 4시에 커트 예약하고 싶고 수진 디자이너로 부탁드리며 이름은 김개굴입니다.",
            "conversation_state": "greeting",
            "service_name": "마음헤어",
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
    assert result.get("time") is not None
    assert result.get("service_type") is not None
    assert result.get("designer") is not None or result["conversation_state"] == "collecting_reservation_info"
    assert result.get("user_name") is not None
    assert result.get("ai_message")
