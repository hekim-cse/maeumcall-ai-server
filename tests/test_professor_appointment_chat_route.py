from routes.chat_routes import chat
from schemas.chat_models import ChatRequest


def test_chat_route_handles_professor_appointment_with_graph(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "면담을 희망하시는 구체적인 목적을 말씀해주시겠습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="면담 예약",
        description="교수님께 면담을 요청하는 상황",
        userMessage="면담 예약하고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.response
    assert result.conversationState == "collecting_appointment_info"
    assert result.shouldEndCall is False
    assert result.scenarioState["intent"] == "appointment_booking"
    assert result.scenarioState["conversation_state"] == "collecting_appointment_info"
    assert result.recommendedReplies


def test_chat_route_professor_appointment_preserves_partial_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "이번 주 수요일 오후 3시 진로 상담 면담으로 확인했습니다. 성함을 말씀해주시겠습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="면담 예약",
        description="교수님께 면담을 요청하는 상황",
        userMessage="진로 상담 관련해서 이번 주 수요일 오후 3시에 가능하실까요?",
        conversationState="collecting_appointment_info",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "collecting_appointment_info"
    assert result.scenarioState["appointment_purpose"] == "진로 상담"
    assert result.scenarioState["date"] == "이번 주 수요일"
    assert result.scenarioState["time"] == "오후 3시"
    assert result.scenarioState["user_name"] is None
    assert "user_name" in result.scenarioState["missing_fields"]


def test_chat_route_professor_appointment_full_info_moves_to_confirming(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "김개굴 학생, 이번 주 수요일 오후 3시에 진로 상담 관련 면담을 희망하시는 것으로 확인했습니다. 맞습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="면담 예약",
        description="교수님께 면담을 요청하는 상황",
        userMessage="진로 상담 관련해서 이번 주 수요일 오후 3시에 김개굴 학생입니다. 면담 가능할까요?",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "confirming_info"
    assert result.scenarioState["appointment_purpose"] == "진로 상담"
    assert result.scenarioState["date"] == "이번 주 수요일"
    assert result.scenarioState["time"] == "오후 3시"
    assert result.scenarioState["user_name"] == "김개굴"
    assert "확인" in result.response or "맞" in result.response


def test_chat_route_professor_appointment_casual_llm_response_falls_back(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "응 좋아. 그때 보자.",
    )

    req = ChatRequest(
        category="교수님",
        title="면담 예약",
        description="교수님께 면담을 요청하는 상황",
        userMessage="진로 상담 관련해서 이번 주 수요일 오후 3시에 김개굴 학생입니다. 면담 가능할까요?",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "confirming_info"
    assert "응" not in result.response
    assert "좋아" not in result.response
    assert "확인" in result.response or "맞습니까" in result.response


def test_chat_route_professor_assignment_still_uses_general_flow(monkeypatch):
    monkeypatch.setattr(
        "routes.chat_routes.complete",
        lambda req, timeout_s: "과제 제출 형식은 PDF로 제출하면 됩니다.",
    )

    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 제출 형식을 문의하는 상황",
        userMessage="과제 제출 형식을 여쭤보려고 합니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.response
    assert result.conversationState is None or result.conversationState == "greeting"
