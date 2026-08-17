import pytest
from services.flow.professor.assignment.graph import professor_assignment_graph


pytestmark = pytest.mark.graph_flow
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
            if "추가" in user_message or "하나 더" in user_message:
                return {
                    "intent": "assignment_inquiry",
                    "assignment_topic": None,
                    "question": None,
                    "user_name": None,
                    "user_action": "ask_follow_up",
                }

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

        if "김개굴" in user_message:
            return {
                "intent": "assignment_inquiry",
                "assignment_topic": None,
                "question": None,
                "user_name": "김개굴",
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


def test_professor_assignment_full_info_moves_to_answering(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["assignment_topic"] == "제출 형식"
    assert result["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "answering_assignment_question"


def test_professor_assignment_missing_user_name_keeps_collecting(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "과제 제출 형식을 여쭤보고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["assignment_topic"] == "제출 형식"
    assert result["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert result["user_name"] is None
    assert result["missing_fields"] == ["user_name"]
    assert result["conversation_state"] == "collecting_assignment_info"


def test_professor_assignment_missing_course_name_keeps_collecting(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.analyze_professor_assignment_user_message",
        lambda conversation_state, user_message: {
            "intent": "assignment_inquiry",
            "course_name": None,
            "assignment_topic": "제출 형식",
            "question": "과제 제출 형식을 여쭤보고 싶습니다.",
            "user_name": "김개굴",
            "user_action": "provide_assignment_info",
        },
    )
    result = professor_assignment_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 과제 제출 형식을 문의드립니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["missing_fields"] == ["course_name"]
    assert result["conversation_state"] == "collecting_assignment_info"
    assert "어떤 수업" in result["ai_message"]


def test_professor_assignment_partial_info_is_preserved(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    first = professor_assignment_graph.invoke(
        {
            "user_message": "과제 제출 형식을 여쭤보고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    second = professor_assignment_graph.invoke(
        {
            **first,
            "user_message": "김개굴 학생입니다.",
        }
    )

    assert second["assignment_topic"] == "제출 형식"
    assert second["question"] == "과제 제출 형식을 여쭤보고 싶습니다."
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "answering_assignment_question"


def test_professor_assignment_casual_llm_response_falls_back(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "answering_assignment_question"
    assert "응" not in result["ai_message"]
    assert "좋아" not in result["ai_message"]
    assert "알아서 해" not in result["ai_message"]
    assert "확인" in result["ai_message"] or "과제" in result["ai_message"]


def test_professor_assignment_answering_moves_to_closing(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "네, 알겠습니다.",
            "conversation_state": "answering_assignment_question",
            "professor_name": "교수님",
            "assignment_topic": "제출 형식",
            "question": "과제 제출 형식을 여쭤보고 싶습니다.",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False


def test_professor_assignment_answering_follow_up_resets_question(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "추가로 하나 더 여쭤봐도 될까요?",
            "conversation_state": "answering_assignment_question",
            "professor_name": "교수님",
            "assignment_topic": "제출 형식",
            "question": "과제 제출 형식을 여쭤보고 싶습니다.",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_assignment_info"
    assert result["assignment_topic"] is None
    assert result["question"] is None
    assert result["user_name"] == "김개굴"


def test_professor_assignment_closing_moves_to_end(monkeypatch):
    _patch_assignment_analysis(monkeypatch)


    result = professor_assignment_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "closing",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True

def test_professor_assignment_answering_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.analyze_professor_assignment_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "course_name": None,
            "assignment_topic": None,
            "user_name": None,
            "user_action": "unknown",
        },
    )
    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.generate_professor_assignment_ai_message",
        lambda state: "테스트 응답",
    )

    result = professor_assignment_graph.invoke(
        {
            "user_message": "음...",
            "conversation_state": "answering_assignment",
            "professor_name": "교수님",
            "course_name": "자료구조",
            "assignment_topic": "제출 기한",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_assignment_info"
    assert result["course_name"] == "자료구조"
    assert result["assignment_topic"] == "제출 기한"
    assert result["user_name"] == "김개굴"


def test_professor_assignment_closing_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.analyze_professor_assignment_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "course_name": None,
            "assignment_topic": None,
            "user_name": None,
            "user_action": "unknown",
        },
    )
    monkeypatch.setattr(
        "services.flow.professor.assignment.nodes.generate_professor_assignment_ai_message",
        lambda state: "테스트 응답",
    )

    result = professor_assignment_graph.invoke(
        {
            "user_message": "음...",
            "conversation_state": "closing",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False
