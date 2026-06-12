from services.flow.professor.assignment.graph import professor_assignment_graph


def test_professor_assignment_full_info_moves_to_answering(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "김개굴 학생, 과제 제출 형식 관련 문의로 확인했습니다. 제출 형식은 공지된 기준을 확인하시기 바랍니다.",
    )

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
    assert result["question"] is not None
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "answering_assignment_question"
    assert "과제" in result["ai_message"] or "제출" in result["ai_message"]


def test_professor_assignment_missing_user_name_keeps_collecting(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "과제 제출 형식 관련 문의 내용은 확인했습니다. 성함을 말씀해주시겠습니까?",
    )

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
    assert result["question"] is not None
    assert result["user_name"] is None
    assert result["conversation_state"] == "collecting_assignment_info"
    assert result["missing_fields"] == ["user_name"]
    assert "성함" in result["ai_message"] or "이름" in result["ai_message"]


def test_professor_assignment_partial_info_is_preserved(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "확인했습니다. 부족한 정보를 말씀해주시겠습니까?",
    )

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
    assert second["question"] is not None
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "answering_assignment_question"


def test_professor_assignment_casual_llm_response_falls_back(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "응 좋아. 과제는 알아서 해.",
    )

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
    assert "확인" in result["ai_message"] or "과제" in result["ai_message"]


def test_professor_assignment_answering_moves_to_closing(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "네, 확인했습니다. 추가로 궁금한 점이 있으면 다시 말씀하시기 바랍니다.",
    )

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
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "어떤 과제와 관련된 문의인지 말씀해주시겠습니까?",
    )

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
    assert result["should_end_call"] is False


def test_professor_assignment_closing_moves_to_end(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.assignment.generation.complete_professor_assignment_ai_message",
        lambda prompt: "네, 알겠습니다.",
    )

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
