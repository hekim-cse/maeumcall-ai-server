from routes.chat_routes import chat
from schemas.chat_models import ChatRequest


def test_chat_route_handles_professor_absence_with_graph(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "결석하게 되는 날짜를 말씀해주시겠습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="결석 사유를 말씀드리려고 연락드렸습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.response
    assert result.conversationState == "collecting_absence_info"
    assert result.shouldEndCall is False
    assert result.scenarioState["intent"] == "absence_notice"
    assert result.scenarioState["conversation_state"] == "collecting_absence_info"
    assert result.recommendedReplies


def test_chat_route_professor_absence_full_info_moves_to_confirming(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "김개굴 학생, 오늘 운영체제 수업 결석 사유가 몸이 좋지 않음으로 확인했습니다. 맞습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="김개굴 학생입니다. 오늘 운영체제 수업에 몸이 좋지 않아 결석하게 되어 연락드렸습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "confirming_absence_info"
    assert result.scenarioState["class_name"] == "운영체제"
    assert result.scenarioState["absence_date"] == "오늘"
    assert result.scenarioState["absence_reason"] == "몸이 좋지 않음"
    assert result.scenarioState["user_name"] == "김개굴"
    assert "결석" in result.response or "확인" in result.response


def test_chat_route_professor_absence_missing_user_name_keeps_collecting(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "오늘 결석 사유는 확인했습니다. 성함을 말씀해주시겠습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="오늘 몸이 좋지 않아 결석하게 되었습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "collecting_absence_info"
    assert result.scenarioState["absence_date"] == "오늘"
    assert result.scenarioState["absence_reason"] == "몸이 좋지 않음"
    assert result.scenarioState["user_name"] is None
    assert result.scenarioState["missing_fields"] == ["user_name"]


def test_chat_route_professor_absence_casual_llm_response_falls_back(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "응 좋아. 알아서 해.",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="김개굴 학생입니다. 오늘 몸이 좋지 않아 결석하게 되었습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "confirming_absence_info"
    assert "응" not in result.response
    assert "좋아" not in result.response
    assert "알아서 해" not in result.response
    assert "결석" in result.response or "확인" in result.response


def test_chat_route_professor_absence_confirm_moves_to_noted(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "알겠습니다. 김개굴 학생의 오늘 결석 사유는 참고하도록 하겠습니다.",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 맞습니다.",
        conversationState="confirming_absence_info",
        scenarioState={
            "intent": "absence_notice",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "conversation_state": "confirming_absence_info",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "absence_noted"
    assert result.shouldEndCall is False


def test_chat_route_professor_absence_change_reason_resets_reason(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "결석 사유를 말씀해주시겠습니까?",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="결석 사유를 다시 말씀드리겠습니다.",
        conversationState="confirming_absence_info",
        scenarioState={
            "intent": "absence_notice",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "conversation_state": "confirming_absence_info",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "collecting_absence_info"
    assert result.scenarioState["absence_date"] == "오늘"
    assert result.scenarioState["absence_reason"] is None
    assert result.scenarioState["user_name"] == "김개굴"


def test_chat_route_professor_absence_noted_moves_to_closing(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "네, 확인했습니다. 추후 필요한 사항이 있으면 다시 말씀하시기 바랍니다.",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 감사합니다.",
        conversationState="absence_noted",
        scenarioState={
            "intent": "absence_notice",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "conversation_state": "absence_noted",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "closing"
    assert result.shouldEndCall is False


def test_chat_route_professor_absence_closing_moves_to_end(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "네, 알겠습니다.",
    )

    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 감사합니다.",
        conversationState="closing",
        scenarioState={
            "intent": "absence_notice",
            "professor_name": "교수님",
            "conversation_state": "closing",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "END"
    assert result.shouldEndCall is True
