import pytest
from services.flow.reservation.restaurant.graph import restaurant_reservation_graph


pytestmark = pytest.mark.integration
def test_restaurant_reservation_integration_real_hf():
    result = restaurant_reservation_graph.invoke(
        {
            "user_message": "오늘 저녁 7시에 2명 예약하고 싶고 이름은 김개굴입니다.",
            "conversation_state": "greeting",
            "service_name": "마음식당",
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
    assert result.get("party_size") is not None
    assert result.get("user_name") is not None
    assert result.get("ai_message")
