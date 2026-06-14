from services.flow.professor.absence.graph import professor_absence_graph


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
            if "날짜" in user_message and ("수정" in user_message or "변경" in user_message):
                return {
                    "intent": "absence_notice",
                    "class_name": None,
                    "absence_date": None,
                    "absence_reason": None,
                    "user_name": None,
                    "user_action": "change_absence_date",
                }

            if "사유" in user_message or "이유" in user_message:
                return {
                    "intent": "absence_notice",
                    "class_name": None,
                    "absence_date": None,
                    "absence_reason": None,
                    "user_name": None,
                    "user_action": "change_absence_reason",
                }

            if "이름" in user_message or "성함" in user_message:
                return {
                    "intent": "absence_notice",
                    "class_name": None,
                    "absence_date": None,
                    "absence_reason": None,
                    "user_name": None,
                    "user_action": "change_user_name",
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

        if "김개굴" in user_message:
            return {
                "intent": "absence_notice",
                "class_name": None,
                "absence_date": None,
                "absence_reason": None,
                "user_name": "김개굴",
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
        fake_analyze,
    )


def test_professor_absence_full_info_moves_to_confirming(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "김개굴 학생, 오늘 결석 사유가 몸이 좋지 않음인 것으로 확인했습니다. 맞습니까?",
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

    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_absence_info"


def test_professor_absence_missing_user_name_keeps_collecting(monkeypatch):
    _patch_absence_analysis(monkeypatch)

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
    assert result["missing_fields"] == ["user_name"]
    assert result["conversation_state"] == "collecting_absence_info"


def test_professor_absence_partial_info_is_preserved(monkeypatch):
    _patch_absence_analysis(monkeypatch)

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
    _patch_absence_analysis(monkeypatch)

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


def test_professor_absence_confirm_moves_to_noted(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "알겠습니다. 김개굴 학생의 오늘 결석 사유는 참고하도록 하겠습니다.",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_absence_info",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "absence_noted"
    assert result["should_end_call"] is False


def test_professor_absence_change_date_resets_date(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "결석하게 되는 날짜를 말씀해주시겠습니까?",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "결석 날짜를 수정하고 싶습니다.",
            "conversation_state": "confirming_absence_info",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_absence_info"
    assert result["absence_date"] is None
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] == "김개굴"


def test_professor_absence_change_reason_resets_reason(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "결석 사유를 말씀해주시겠습니까?",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "결석 사유를 다시 말씀드리겠습니다.",
            "conversation_state": "confirming_absence_info",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_absence_info"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] is None
    assert result["user_name"] == "김개굴"


def test_professor_absence_noted_moves_to_closing(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "네, 확인했습니다. 추후 필요한 사항이 있으면 다시 말씀하시기 바랍니다.",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "absence_noted",
            "professor_name": "교수님",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False


def test_professor_absence_closing_moves_to_end(monkeypatch):
    _patch_absence_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.absence.generation.complete_professor_absence_ai_message",
        lambda prompt: "네, 알겠습니다.",
    )

    result = professor_absence_graph.invoke(
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

def test_professor_absence_change_user_name_resets_user_name_only(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.nodes.analyze_professor_absence_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "class_name": None,
            "absence_date": None,
            "absence_reason": None,
            "user_name": None,
            "user_action": "change_user_name",
        },
    )
    monkeypatch.setattr(
        "services.flow.professor.absence.nodes.generate_professor_absence_ai_message",
        lambda state: "테스트 응답",
    )

    result = professor_absence_graph.invoke(
        {
            "user_message": "이름을 다시 말씀드릴게요.",
            "conversation_state": "confirming_absence_info",
            "professor_name": "교수님",
            "class_name": "자료구조",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_absence_info"
    assert result["user_name"] is None
    assert result["class_name"] == "자료구조"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"


def test_professor_absence_closing_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.professor.absence.nodes.analyze_professor_absence_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "class_name": None,
            "absence_date": None,
            "absence_reason": None,
            "user_name": None,
            "user_action": "unknown",
        },
    )
    monkeypatch.setattr(
        "services.flow.professor.absence.nodes.generate_professor_absence_ai_message",
        lambda state: "테스트 응답",
    )

    result = professor_absence_graph.invoke(
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

