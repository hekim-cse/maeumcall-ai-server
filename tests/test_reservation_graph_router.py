import pytest
from schemas.chat_models import ChatRequest
from services.flow.reservation.router import complete_reservation_graph_if_supported


pytestmark = pytest.mark.unit
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


def test_reservation_graph_router_handles_hospital_reservation():
    """
    예약 / 병원 예약은 병원 예약 LangGraph가 처리해야 한다.
    """
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


