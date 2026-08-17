from routes.chat_routes import chat
from schemas.chat_models import ChatRequest


def _patch_assignment_analysis(monkeypatch):
    def fake_analyze(conversation_state: str, user_message: str):
        if conversation_state == "closing":
            return {
                "intent": "assignment_inquiry",
                "assignment_topic": None,
                "question": None,
                "user_name": None,
                "user_action": "end_call",
            }

        if conversation_state == "answering_assignment_question":
            return {
                "intent": "assignment_inquiry",
                "assignment_topic": None,
                "question": None,
                "user_name": None,
                "user_action": "go_closing",
            }

        if "김개굴" in user_message and "제출 형식" in user_message:
            return {
                "intent": "assignment_inquiry",
                "assignment_topic": "제출 형식",
                "question": "과제 제출 형식을 여쭤보고 싶습니다.",
                "user_name": "김개굴",
                "user_action": "provide_assignment_info",
            }

        if "제출 형식" in user_message:
            return {
                "intent": "assignment_inquiry",
                "assignment_topic": "제출 형식",
                "question": "과제 제출 형식을 여쭤보고 싶습니다.",
                "user_name": None,
                "user_action": "provide_assignment_info",
            }

        return {
            "intent": "assignment_inquiry",
            "assignment_topic": None,
            "question": None,
            "user_name": None,
            "user_action": "unknown",
        }

    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.analyze_professor_assignment_user_message",
        lambda conversation_state, user_message: {
            "course_name": "자료구조",
            **fake_analyze(conversation_state, user_message),
        },
    )


def test_chat_route_handles_professor_assignment_with_graph(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="과제 문의드리고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.response
    assert result.conversationState == "collecting_assignment_info"
    assert result.shouldEndCall is False
    assert result.scenarioState["intent"] == "assignment_inquiry"
    assert result.scenarioState["conversation_state"] == "collecting_assignment_info"
    assert result.recommendedReplies


def test_chat_route_professor_assignment_full_info_moves_to_answering(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "answering_assignment_question"
    assert result.scenarioState["assignment_topic"] == "제출 형식"
    assert result.scenarioState["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result.scenarioState["user_name"] == "김개굴"
    assert "과제" in result.response or "제출" in result.response


def test_chat_route_professor_assignment_missing_user_name_keeps_collecting(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="과제 제출 형식을 여쭤보고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "collecting_assignment_info"
    assert result.scenarioState["assignment_topic"] == "제출 형식"
    assert result.scenarioState["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result.scenarioState["user_name"] is None
    assert result.scenarioState["missing_fields"] == ["user_name"]


def test_chat_route_professor_assignment_casual_llm_response_falls_back(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
        conversationState="greeting",
        scenarioState={},
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "answering_assignment_question"
    assert "응" not in result.response
    assert "좋아" not in result.response
    assert "알아서 해" not in result.response
    assert "과제" in result.response or "확인" in result.response


def test_chat_route_professor_assignment_answering_moves_to_closing(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="네, 알겠습니다.",
        conversationState="answering_assignment_question",
        scenarioState={
            "intent": "assignment_inquiry",
            "scenario_key": "교수님:과제 문의",
            "state_version": 2,
            "professor_name": "교수님",
            "assignment_topic": "제출 형식",
            "question": "과제 제출 형식을 여쭤보고 싶습니다.",
            "user_name": "김개굴",
            "conversation_state": "answering_assignment_question",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "closing"
    assert result.shouldEndCall is False


def test_chat_route_professor_assignment_closing_moves_to_end(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    req = ChatRequest(
        category="교수님",
        title="과제 문의",
        description="교수님께 과제 관련 내용을 문의하는 상황",
        userMessage="네, 감사합니다.",
        conversationState="closing",
        scenarioState={
            "intent": "assignment_inquiry",
            "scenario_key": "교수님:과제 문의",
            "state_version": 2,
            "professor_name": "교수님",
            "conversation_state": "closing",
        },
        history=[],
    )

    result = chat(req)

    assert result.conversationState == "END"
    assert result.shouldEndCall is True
