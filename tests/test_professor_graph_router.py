from schemas.chat_models import ChatRequest
from services.flow.professor.router import complete_professor_graph_if_supported


def make_request(title: str, category: str = "교수님", user_message: str = "") -> ChatRequest:
    return ChatRequest(
        category=category,
        title=title,
        description="",
        userMessage=user_message or "문의드리고 싶습니다.",
    )


def test_professor_graph_router_handles_appointment_booking():
    req = make_request("면담 예약", user_message="면담 예약하고 싶습니다.")

    result = complete_professor_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_appointment_info"
    assert result.shouldEndCall is False
    assert "면담" in result.response or "예약" in result.response


def test_professor_graph_router_handles_assignment_inquiry():
    req = make_request("과제 문의", user_message="과제 제출 형식을 여쭤보고 싶습니다.")

    result = complete_professor_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_assignment_info"
    assert result.shouldEndCall is False
    assert "과제" in result.response or "궁금" in result.response


def test_professor_graph_router_handles_absence_notice():
    req = make_request("결석 사유 전달", user_message="오늘 수업에 결석하게 되어 연락드렸습니다.")

    result = complete_professor_graph_if_supported(req)

    assert result is not None
    assert result.conversationState == "collecting_absence_info"
    assert result.shouldEndCall is False
    assert "결석" in result.response or "사유" in result.response


def test_professor_graph_router_ignores_non_professor_category():
    req = make_request("결석 사유 전달", category="회사", user_message="오늘 결석 사유를 전달드립니다.")

    result = complete_professor_graph_if_supported(req)

    assert result is None
