import pytest
from services.flow.reservation.study_room.graph import study_room_reservation_graph


pytestmark = pytest.mark.graph_flow
def _patch_study_room_analysis(monkeypatch):
    def fake_analyze(conversation_state: str, user_message: str):
        if conversation_state == "closing":
            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": None,
                "user_name": None,
                "user_action": "end_call",
                "selected_time": None,
            }

        if conversation_state == "reservation_confirmed":
            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": None,
                "user_name": None,
                "user_action": "go_closing",
                "selected_time": None,
            }

        if conversation_state == "reservation_available":
            if "다른" in user_message or "변경" in user_message:
                return {
                    "intent": "reservation",
                    "date": None,
                    "start_time": None,
                    "duration": None,
                    "party_size": None,
                    "user_name": None,
                    "user_action": "ask_other_time",
                    "selected_time": None,
                }

            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": None,
                "user_name": None,
                "user_action": "confirm_reservation",
                "selected_time": None,
            }

        if conversation_state == "reservation_unavailable":
            if "오후 3시" in user_message:
                return {
                    "intent": "reservation",
                    "date": None,
                    "start_time": None,
                    "duration": None,
                    "party_size": None,
                    "user_name": None,
                    "user_action": "select_alternative_time",
                    "selected_time": "오후 3시",
                }

            if "오후 5시" in user_message:
                return {
                    "intent": "reservation",
                    "date": None,
                    "start_time": None,
                    "duration": None,
                    "party_size": None,
                    "user_name": None,
                    "user_action": "select_alternative_time",
                    "selected_time": "오후 5시",
                }

            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": None,
                "user_name": None,
                "user_action": "unknown",
                "selected_time": None,
            }

        if conversation_state == "confirming_info":
            if "시작" in user_message or "시간" in user_message and "변경" in user_message:
                return {
                    "intent": "reservation",
                    "date": None,
                    "start_time": None,
                    "duration": None,
                    "party_size": None,
                    "user_name": None,
                    "user_action": "change_start_time",
                    "selected_time": None,
                }

            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": None,
                "user_name": None,
                "user_action": "confirm",
                "selected_time": None,
            }

        if "김개굴" in user_message and "4명" in user_message:
            return {
                "intent": "reservation",
                "date": "내일" if "내일" in user_message else None,
                "start_time": "오후 2시" if "두 시" in user_message or "2시" in user_message else None,
                "duration": "2시간" if "두 시간" in user_message or "2시간" in user_message else None,
                "party_size": "4명",
                "user_name": "김개굴",
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if "내일" in user_message:
            return {
                "intent": "reservation",
                "date": "내일",
                "start_time": "오후 2시",
                "duration": "2시간",
                "party_size": "4명" if "4명" in user_message else None,
                "user_name": None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if "4명" in user_message and "김개굴" in user_message:
            return {
                "intent": "reservation",
                "date": None,
                "start_time": None,
                "duration": None,
                "party_size": "4명",
                "user_name": "김개굴",
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        return {
            "intent": "reservation",
            "date": None,
            "start_time": None,
            "duration": None,
            "party_size": None,
            "user_name": None,
            "user_action": "unknown",
            "selected_time": None,
        }

    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.analyze_study_room_reservation_user_message",
        fake_analyze,
    )


def test_study_room_reservation_full_info_moves_to_confirming_info(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 4명 김개굴 이름으로 예약하고 싶어요.",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"
    assert result["conversation_state"] == "confirming_info"


def test_study_room_reservation_missing_user_name_keeps_collecting_info(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 4명 예약 가능할까요?",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] is None
    assert result["conversation_state"] == "collecting_reservation_info"


def test_study_room_reservation_partial_info_is_preserved(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    first = study_room_reservation_graph.invoke(
        {
            "user_message": "내일 오후 두 시부터 두 시간 예약 가능할까요?",
            "conversation_state": "greeting",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    second = study_room_reservation_graph.invoke(
        {
            **first,
            "user_message": "4명이고 김개굴 이름으로 예약해주세요.",
        }
    )

    assert second["date"] == "내일"
    assert second["start_time"] == "오후 2시"
    assert second["duration"] == "2시간"
    assert second["party_size"] == "4명"
    assert second["user_name"] == "김개굴"
    assert second["conversation_state"] == "confirming_info"


def test_study_room_reservation_confirm_checks_availability_available(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["availability_status"] == "available"


def test_study_room_reservation_confirm_checks_availability_unavailable(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["availability_status"] == "unavailable"


def test_study_room_reservation_available_confirm_completes_reservation(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 예약해주세요.",
            "conversation_state": "reservation_available",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "오후 3시",
            "alternative_times": [],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert result["selected_time"] == "오후 3시"


def test_study_room_reservation_unavailable_selects_alternative_time(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "오후 3시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 1시", "오후 3시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["start_time"] == "오후 3시"
    assert result["selected_time"] == "오후 3시"


def test_study_room_reservation_unavailable_rejects_out_of_option_time(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "오후 5시로 할게요.",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 1시", "오후 3시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["selected_time"] is None


def test_study_room_reservation_confirmed_moves_to_closing(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "reservation_confirmed",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 3시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "selected_time": "오후 3시",
            "reservation_confirmed": True,
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"


def test_study_room_reservation_closing_moves_to_end(monkeypatch):
    _patch_study_room_analysis(monkeypatch)

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "closing",
            "service_name": "마음스터디룸",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True

def test_study_room_reservation_change_party_size_clears_lookup_fields(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.analyze_study_room_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "start_time": None,
            "duration": None,
            "party_size": None,
            "user_name": None,
            "user_action": "change_party_size",
            "selected_time": None,
        },
    )
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.generate_study_room_ai_message",
        lambda state: "테스트 응답",
    )

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "인원을 바꾸고 싶습니다.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "available",
            "availability_reason": None,
            "available_time": "오후 2시",
            "alternative_times": ["오후 1시", "오후 3시"],
            "availability_message_hint": "내일 오후 2시부터 2시간 예약이 가능합니다.",
            "selected_time": "오후 2시",
            "reservation_confirmed": True,
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_reservation_info"
    assert result["party_size"] is None
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["user_name"] == "김개굴"
    assert result["selected_time"] is None
    assert result["availability_status"] is None
    assert result["alternative_times"] == []
    assert result["reservation_confirmed"] is False


def test_study_room_reservation_change_user_name_resets_user_name_only(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.analyze_study_room_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "start_time": None,
            "duration": None,
            "party_size": None,
            "user_name": None,
            "user_action": "change_user_name",
            "selected_time": None,
        },
    )
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.generate_study_room_ai_message",
        lambda state: "테스트 응답",
    )

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "예약자 이름을 바꿀게요.",
            "conversation_state": "confirming_info",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "available",
            "available_time": "오후 2시",
            "alternative_times": [],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "collecting_reservation_info"
    assert result["user_name"] is None
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"


def test_study_room_reservation_unavailable_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.analyze_study_room_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "date": None,
            "start_time": None,
            "duration": None,
            "party_size": None,
            "user_name": None,
            "user_action": "unknown",
            "selected_time": None,
        },
    )
    monkeypatch.setattr(
        "services.flow.reservation.study_room.nodes.generate_study_room_ai_message",
        lambda state: "테스트 응답",
    )

    result = study_room_reservation_graph.invoke(
        {
            "user_message": "음...",
            "conversation_state": "reservation_unavailable",
            "service_name": "마음스터디룸",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 1시", "오후 3시"],
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["selected_time"] is None

