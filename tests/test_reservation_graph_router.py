from schemas.chat_models import ChatRequest
from services.flow.reservation.router import complete_reservation_graph_if_supported


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
    assert result.conversationState == "asking_date"
    assert result.shouldEndCall is False
    assert "예약" in result.response


def test_reservation_graph_router_ignores_study_room_reservation():
    """
    예약 / 스터디룸 예약은 아직 graph가 없으므로 기존 LLM/fallback 흐름으로 넘겨야 한다.
    """
    req = make_request("스터디룸 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is None


def test_reservation_graph_router_ignores_hair_salon_reservation():
    """
    예약 / 미용실 예약은 아직 graph가 없으므로 기존 LLM/fallback 흐름으로 넘겨야 한다.
    """
    req = make_request("미용실 예약")

    result = complete_reservation_graph_if_supported(req)

    assert result is None


