import pytest

from services.flow.reservation.hospital.graph import hospital_reservation_graph

pytestmark = pytest.mark.integration


def test_hospital_reservation_integration_real_hf():
    result = hospital_reservation_graph.invoke(
        {
            "user_message": "내일 오후 3시에 내과 예약하고 싶은데 김개굴입니다.",
            "conversation_state": "greeting",
            "service_name": "마음병원",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] in [
        "confirming_info",
        "asking_department",
        "asking_date",
        "asking_time",
    ]
    assert result.get("intent") == "reservation" or result.get("intent") is not None
    assert (
        result.get("department") is not None or result["conversation_state"] == "asking_department"
    )
    assert result.get("ai_message")
