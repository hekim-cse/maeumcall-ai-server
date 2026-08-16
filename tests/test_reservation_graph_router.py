import pytest
from schemas.chat_models import ChatRequest
from services.flow.reservation.router import complete_reservation_graph_if_supported


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _mock_structured_analysis(monkeypatch):
    reservation_result = {
        "intent": "reservation",
        "date": None,
        "time": None,
        "user_action": "continue_collecting",
        "selected_time": None,
    }
    monkeypatch.setattr(
        "services.flow.reservation.restaurant.nodes.analyze_restaurant_reservation_user_message",
        lambda conversation_state, user_message: {
            **reservation_result,
            "party_size": None,
            "user_name": None,
        },
    )
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.analyze_study_room_reservation_user_message",
        lambda conversation_state, user_message: {
            **reservation_result,
            "start_time": None,
            "duration": None,
            "party_size": None,
            "user_name": None,
        },
    )
    monkeypatch.setattr(
        "services.flow.reservation.hair_salon.nodes.analyze_hair_salon_reservation_user_message",
        lambda conversation_state, user_message: {
            **reservation_result,
            "service_type": None,
            "designer": None,
            "user_name": None,
        },
    )


def make_request(title: str) -> ChatRequest:
    return ChatRequest(
        category="예약",
        title=title,
        description=f"{title} 전화 상황",
        userMessage="예약하고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )


def test_reservation_graph_router_handles_hospital_reservation(monkeypatch):
    """
    예약 / 병원 예약은 병원 예약 LangGraph가 처리해야 한다.
    """
    monkeypatch.setattr(
        "services.flow.reservation.hospital.nodes.analyze_hospital_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": "reservation",
            "department": None,
            "date": None,
            "time": None,
            "user_action": "continue_collecting",
            "selected_time": None,
        },
    )

    req = make_request("병원 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "asking_department"
    assert result.scenarioState is not None


def test_reservation_graph_router_handles_restaurant_reservation():
    """
    예약 / 식당 예약은 식당 예약 LangGraph로 처리되어야 한다.
    """
    req = make_request("식당 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_reservation_info"
    assert result.shouldEndCall is False
    assert "예약" in result.response


def test_reservation_graph_router_handles_study_room_reservation():
    """
    예약 / 스터디룸 예약은 스터디룸 예약 LangGraph로 처리되어야 한다.
    """
    req = make_request("스터디룸 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_reservation_info"
    assert result.shouldEndCall is False
    assert "스터디룸" in result.response or "예약" in result.response


def test_reservation_graph_router_handles_hair_salon_reservation():
    """
    예약 / 미용실 예약은 미용실 예약 LangGraph로 처리되어야 한다.
    """
    req = make_request("미용실 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_reservation_info"
    assert result.shouldEndCall is False
    assert "미용실" in result.response or "예약" in result.response

