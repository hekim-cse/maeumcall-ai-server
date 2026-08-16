from routes.chat_routes import chat
from schemas.chat_models import ChatRequest


def _patch_appointment_analysis(monkeypatch):
    def fake_analyze(conversation_state: str, user_message: str):
        if "진로 상담" in user_message:
            return {
                "intent": "appointment_booking",
                "appointment_purpose": "진로 상담",
                "date": "이번 주 수요일",
                "time": "오후 3시",
                "user_name": "김개굴" if "김개굴" in user_message else None,
                "user_action": "provide_appointment_info",
            }
        return {
            "intent": "appointment_booking",
            "appointment_purpose": None,
            "date": None,
            "time": None,
            "user_name": None,
            "user_action": "unknown",
        }

    monkeypatch.setattr(
        "services.flow.professor.appointment.nodes.analyze_professor_appointment_user_message",
        fake_analyze,
    )


def test_chat_route_handles_professor_appointment_with_graph(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

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
    _patch_appointment_analysis(monkeypatch)

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
    _patch_appointment_analysis(monkeypatch)

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


def test_chat_route_professor_appointment_uses_formal_response_policy(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

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
