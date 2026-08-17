from routes.chat_routes import chat
from schemas.chat_models import ChatRequest


def _absence_state(conversation_state: str) -> dict:
    return {
        "intent": "absence_notice",
        "scenario_key": "교수님:결석 사유 전달",
        "state_version": 2,
        "professor_name": "교수님",
        "class_name": "자료구조",
        "absence_date": "오늘",
        "absence_reason": "몸이 좋지 않음",
        "user_name": "김개굴",
        "conversation_state": conversation_state,
        "missing_fields": [],
        "last_ai_message": "결석 사유를 확인했습니다.",
        "user_action": "provide_absence_info",
    }


def _patch_absence_analysis(monkeypatch):
    def fake_analyze(conversation_state: str, user_message: str):
        if conversation_state == "closing":
            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": None,
                "absence_reason": None,
                "user_name": None,
                "user_action": "end_call",
            }

        if conversation_state == "absence_noted":
            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": None,
                "absence_reason": None,
                "user_name": None,
                "user_action": "go_closing",
            }

        if conversation_state == "confirming_absence_info":
            if "사유" in user_message or "이유" in user_message:
                return {
                    "intent": "absence_notice",
                    "class_name": None,
                    "absence_date": None,
                    "absence_reason": None,
                    "user_name": None,
                    "user_action": "change_absence_reason",
                }

            if "날짜" in user_message:
                return {
                    "intent": "absence_notice",
                    "class_name": None,
                    "absence_date": None,
                    "absence_reason": None,
                    "user_name": None,
                    "user_action": "change_absence_date",
                }

            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": None,
                "absence_reason": None,
                "user_name": None,
                "user_action": "confirm_info",
            }

        if "김개굴" in user_message and "오늘" in user_message:
            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": "오늘",
                "absence_reason": "몸이 좋지 않음",
                "user_name": "김개굴",
                "user_action": "provide_absence_info",
            }

        if "오늘" in user_message:
            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": "오늘",
                "absence_reason": "몸이 좋지 않음",
                "user_name": None,
                "user_action": "provide_absence_info",
            }

        return {
            "intent": "absence_notice",
            "class_name": None,
            "absence_date": None,
            "absence_reason": None,
            "user_name": None,
            "user_action": "unknown",
        }

    monkeypatch.setattr(
        "services.flow.professor.absence.nodes.analyze_professor_absence_user_message",
        lambda conversation_state, user_message: {
            **fake_analyze(conversation_state, user_message),
            "class_name": "자료구조",
        },
    )


def test_chat_route_handles_professor_absence_with_graph(monkeypatch):
    _patch_absence_analysis(monkeypatch)


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
    _patch_absence_analysis(monkeypatch)


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
    assert result.scenarioState["absence_date"] == "오늘"
    assert result.scenarioState["absence_reason"] == "몸이 좋지 않음"
    assert result.scenarioState["user_name"] == "김개굴"


def test_chat_route_professor_absence_missing_user_name_keeps_collecting(monkeypatch):
    _patch_absence_analysis(monkeypatch)


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
    _patch_absence_analysis(monkeypatch)


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
    _patch_absence_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 맞습니다.",
        conversationState="confirming_absence_info",
        scenarioState=_absence_state("confirming_absence_info"),
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "absence_noted"
    assert result.shouldEndCall is False


def test_chat_route_professor_absence_change_reason_resets_reason(monkeypatch):
    _patch_absence_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="결석 사유를 다시 말씀드리겠습니다.",
        conversationState="confirming_absence_info",
        scenarioState=_absence_state("confirming_absence_info"),
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "collecting_absence_info"
    assert result.scenarioState["absence_date"] == "오늘"
    assert result.scenarioState["absence_reason"] is None
    assert result.scenarioState["user_name"] == "김개굴"


def test_chat_route_professor_absence_noted_moves_to_closing(monkeypatch):
    _patch_absence_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 감사합니다.",
        conversationState="absence_noted",
        scenarioState=_absence_state("absence_noted"),
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "closing"
    assert result.shouldEndCall is False


def test_chat_route_professor_absence_closing_moves_to_end(monkeypatch):
    _patch_absence_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="결석 사유 전달",
        description="교수님께 결석 사유를 전달하는 상황",
        userMessage="네, 감사합니다.",
        conversationState="closing",
        scenarioState=_absence_state("closing"),
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "END"
    assert result.shouldEndCall is True
