from services.flow.professor.appointment.graph import professor_appointment_graph


def _patch_appointment_analysis(monkeypatch):
    def fake_analyze(conversation_state: str, user_message: str):
        if conversation_state == "closing":
            return {
                "intent": "appointment_booking",
                "appointment_purpose": None,
                "date": None,
                "time": None,
                "user_name": None,
                "user_action": "end_call",
            }

        if conversation_state == "appointment_confirmed":
            return {
                "intent": "appointment_booking",
                "appointment_purpose": None,
                "date": None,
                "time": None,
                "user_name": None,
                "user_action": "go_closing",
            }

        if conversation_state == "confirming_info":
            if "시간" in user_message and ("변경" in user_message or "수정" in user_message):
                return {
                    "intent": "appointment_booking",
                    "appointment_purpose": None,
                    "date": None,
                    "time": None,
                    "user_name": None,
                    "user_action": "change_time",
                }

            if "목적" in user_message or "내용" in user_message:
                return {
                    "intent": "appointment_booking",
                    "appointment_purpose": None,
                    "date": None,
                    "time": None,
                    "user_name": None,
                    "user_action": "change_purpose",
                }

            if "날짜" in user_message:
                return {
                    "intent": "appointment_booking",
                    "appointment_purpose": None,
                    "date": None,
                    "time": None,
                    "user_name": None,
                    "user_action": "change_date",
                }

            if "이름" in user_message or "성함" in user_message:
                return {
                    "intent": "appointment_booking",
                    "appointment_purpose": None,
                    "date": None,
                    "time": None,
                    "user_name": None,
                    "user_action": "change_user_name",
                }

            return {
                "intent": "appointment_booking",
                "appointment_purpose": None,
                "date": None,
                "time": None,
                "user_name": None,
                "user_action": "confirm_info",
            }

        if "김개굴" in user_message and "진로 상담" in user_message:
            return {
                "intent": "appointment_booking",
                "appointment_purpose": "진로 상담",
                "date": "이번 주 수요일",
                "time": "오후 3시",
                "user_name": "김개굴",
                "user_action": "provide_appointment_info",
            }

        if "진로 상담" in user_message:
            return {
                "intent": "appointment_booking",
                "appointment_purpose": "진로 상담",
                "date": "이번 주 수요일",
                "time": "오후 3시",
                "user_name": None,
                "user_action": "provide_appointment_info",
            }

        if "김개굴" in user_message:
            return {
                "intent": "appointment_booking",
                "appointment_purpose": None,
                "date": None,
                "time": None,
                "user_name": "김개굴",
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


def test_professor_appointment_full_info_moves_to_confirming_info(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "김개굴 학생, 이번 주 수요일 오후 3시에 진로 상담 관련 면담을 희망하시는 것으로 확인했습니다. 맞습니까?",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 진로 상담 관련해서 이번 주 수요일 오후 3시에 면담 가능할까요?",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["appointment_purpose"] == "진로 상담"
    assert result["date"] == "이번 주 수요일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"


def test_professor_appointment_missing_user_name_keeps_collecting_info(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "이번 주 수요일 오후 3시, 진로 상담 관련 면담으로 확인했습니다. 성함을 말씀해주시겠습니까?",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "진로 상담 관련해서 이번 주 수요일 오후 3시에 면담 가능할까요?",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["appointment_purpose"] == "진로 상담"
    assert result["date"] == "이번 주 수요일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] is None
    assert result["missing_fields"] == ["user_name"]
    assert result["conversation_state"] == "collecting_appointment_info"


def test_professor_appointment_partial_info_is_preserved(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "확인했습니다. 부족한 정보를 말씀해주시겠습니까?",
    )

    first = professor_appointment_graph.invoke(
        {
            "user_message": "진로 상담 관련해서 이번 주 수요일 오후 3시에 면담 가능할까요?",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    second = professor_appointment_graph.invoke(
        {
            **first,
            "user_message": "김개굴 학생입니다.",
        }
    )

    assert second["appointment_purpose"] == "진로 상담"
    assert second["date"] == "이번 주 수요일"
    assert second["time"] == "오후 3시"
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "confirming_info"


def test_professor_appointment_casual_llm_response_falls_back(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "응 좋아. 그때 보자.",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "김개굴 학생입니다. 진로 상담 관련해서 이번 주 수요일 오후 3시에 면담 가능할까요?",
            "conversation_state": "greeting",
            "professor_name": "교수님",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "confirming_info"
    assert "응" not in result["ai_message"]
    assert "좋아" not in result["ai_message"]
    assert "확인" in result["ai_message"] or "맞습니까" in result["ai_message"]


def test_professor_appointment_confirm_moves_to_confirmed(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "알겠습니다. 김개굴 학생의 진로 상담 관련 면담 요청은 이번 주 수요일 오후 3시로 확인해두겠습니다.",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "professor_name": "교수님",
            "appointment_purpose": "진로 상담",
            "date": "이번 주 수요일",
            "time": "오후 3시",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "appointment_confirmed"
    assert result["should_end_call"] is False


def test_professor_appointment_change_time_resets_time(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "희망하시는 시간을 말씀해주시겠습니까?",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "시간을 변경하고 싶습니다.",
            "conversation_state": "confirming_info",
            "professor_name": "교수님",
            "appointment_purpose": "진로 상담",
            "date": "이번 주 수요일",
            "time": "오후 3시",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_appointment_info"
    assert result["time"] is None
    assert result["appointment_purpose"] == "진로 상담"
    assert result["date"] == "이번 주 수요일"
    assert result["user_name"] == "김개굴"


def test_professor_appointment_change_purpose_resets_purpose(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "면담을 희망하시는 구체적인 목적을 말씀해주시겠습니까?",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "면담 목적을 다시 말씀드리겠습니다.",
            "conversation_state": "confirming_info",
            "professor_name": "교수님",
            "appointment_purpose": "진로 상담",
            "date": "이번 주 수요일",
            "time": "오후 3시",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_appointment_info"
    assert result["appointment_purpose"] is None
    assert result["date"] == "이번 주 수요일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] == "김개굴"


def test_professor_appointment_confirmed_moves_to_closing(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "네, 확인했습니다. 추가로 필요한 사항이 있으면 다시 말씀해주시기 바랍니다.",
    )

    result = professor_appointment_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "appointment_confirmed",
            "professor_name": "교수님",
            "appointment_purpose": "진로 상담",
            "date": "이번 주 수요일",
            "time": "오후 3시",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert result["should_end_call"] is False


def test_professor_appointment_closing_moves_to_end(monkeypatch):
    _patch_appointment_analysis(monkeypatch)

    monkeypatch.setattr(
        "services.flow.professor.appointment.generation.complete_professor_appointment_ai_message",
        lambda prompt: "네, 알겠습니다.",
    )

    result = professor_appointment_graph.invoke(
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
