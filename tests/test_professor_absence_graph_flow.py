from services.flow.professor.absence.graph import professor_absence_graph


def test_professor_absence_full_info_moves_to_confirming(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "김개굴 학생, 오늘 운영체제 수업 결석 사유가 몸이 좋지 않음으로 확인했습니다. 맞습니까?",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 오늘 운영체제 수업에 몸이 좋지 않아 결석하게 되어 연락드렸습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["class_name"] == "운영체제"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_absence_info"
    assert "결석" in result["ai_message"] or "확인" in result["ai_message"]


def test_professor_absence_missing_user_name_keeps_collecting(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "오늘 결석 사유는 확인했습니다. 성함을 말씀해주시겠습니까?",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "오늘 몸이 좋지 않아 결석하게 되었습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] is None
    assert result["conversation_state"] == "collecting_absence_info"
    assert result["missing_fields"] == ["user_name"]
    assert "성함" in result["ai_message"] or "이름" in result["ai_message"]


def test_professor_absence_partial_info_is_preserved(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "확인했습니다. 부족한 정보를 말씀해주시겠습니까?",
    )

    first = professor_absence_graph.invoke(
        {
            "user_message": "오늘 몸이 좋지 않아 결석하게 되었습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    second = professor_absence_graph.invoke(
        {
            **first,
            "user_message": "김개굴 학생입니다.",
        }
    )

    assert second["absence_date"] == "오늘"
    assert second["absence_reason"] == "몸이 좋지 않음"
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "confirming_absence_info"


def test_professor_absence_casual_llm_response_falls_back(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "응 좋아. 알아서 해.",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 오늘 몸이 좋지 않아 결석하게 되었습니다.",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "confirming_absence_info"
    assert "응" not in result["ai_message"]
    assert "좋아" not in result["ai_message"]
    assert "알아서 해" not in result["ai_message"]
    assert "결석" in result["ai_message"] or "확인" in result["ai_message"]
