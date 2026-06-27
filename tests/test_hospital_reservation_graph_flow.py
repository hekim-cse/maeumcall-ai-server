import pytest
from services.flow.reservation.hospital import graph as graph_module
from services.flow.reservation.hospital import generation as generation_module


pytestmark = pytest.mark.graph_flow

def _patch_hospital_analysis(monkeypatch):
    def fake_analyze(conversation_state, user_message):
        if conversation_state in ["greeting", "collecting_reservation_info"]:
            if "내일" in user_message and "오후" in user_message:
                return {
                    "intent": "reservation",
                    "department": None,
                    "date": "내일",
                    "time": "오후",
                    "user_action": "continue_collecting",
                    "selected_time": None,
                }

            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if conversation_state == "asking_department":
            return {
                "intent": "reservation",
                "department": "내과" if "내과" in user_message else None,
                "date": None,
                "time": None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if conversation_state == "asking_date":
            return {
                "intent": "reservation",
                "department": None,
                "date": "모레" if "모레" in user_message else None,
                "time": None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if conversation_state == "asking_time":
            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": "오후 3시" if "오후 3시" in user_message else None,
                "user_action": "continue_collecting",
                "selected_time": None,
            }

        if conversation_state == "confirming_info":
            if "시간" in user_message and ("바꾸" in user_message or "다시" in user_message):
                user_action = "change_time"
            elif "날짜" in user_message or "다른 날짜" in user_message:
                user_action = "change_date"
            elif "진료과" in user_message or "과를" in user_message:
                user_action = "change_department"
            elif "네" in user_message or "맞습니다" in user_message:
                user_action = "confirm_reservation_info"
            else:
                user_action = "unknown"

            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": user_action,
                "selected_time": None,
            }

        if conversation_state == "checking_availability":
            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": "lookup_availability",
                "selected_time": None,
            }

        if conversation_state == "reservation_available":
            if "다른 시간" in user_message or "그 시간 말고" in user_message:
                user_action = "ask_other_time"
            elif "예약" in user_message or "그 시간" in user_message or "네" in user_message:
                user_action = "confirm_available_time"
            else:
                user_action = "unknown"

            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": user_action,
                "selected_time": None,
            }

        if conversation_state == "reservation_unavailable":
            if "다른 날짜" in user_message or "날짜" in user_message:
                user_action = "change_date"
                selected_time = None
            elif "다른 시간" in user_message or "가능할까요" in user_message:
                user_action = "ask_other_time"
                selected_time = None
            elif "오후 4시" in user_message:
                user_action = "select_alternative_time"
                selected_time = "오후 4시"
            elif "오후 5시" in user_message:
                user_action = "select_alternative_time"
                selected_time = "오후 5시"
            else:
                user_action = "unknown"
                selected_time = None

            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": user_action,
                "selected_time": selected_time,
            }

        if conversation_state == "suggest_alternative":
            if "오후 4시" in user_message:
                user_action = "select_alternative_time"
                selected_time = "오후 4시"
            elif "오후 5시" in user_message:
                user_action = "select_alternative_time"
                selected_time = "오후 5시"
            elif "다른 날짜" in user_message or "날짜" in user_message:
                user_action = "change_date"
                selected_time = None
            elif "다른 시간" in user_message:
                user_action = "ask_other_time"
                selected_time = None
            else:
                user_action = "unknown"
                selected_time = None

            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": user_action,
                "selected_time": selected_time,
            }

        if conversation_state == "reservation_confirmed":
            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": "go_closing",
                "selected_time": None,
            }

        if conversation_state == "closing":
            return {
                "intent": "reservation",
                "department": None,
                "date": None,
                "time": None,
                "user_action": "end_call",
                "selected_time": None,
            }

        return {
            "intent": "reservation",
            "department": None,
            "date": None,
            "time": None,
            "user_action": "unknown",
            "selected_time": None,
        }

    monkeypatch.setattr(
        "services.flow.reservation.hospital.nodes.analyze_hospital_reservation_user_message",
        fake_analyze,
    )


def _invoke(state: dict, monkeypatch):
    _patch_hospital_analysis(monkeypatch)
    monkeypatch.setattr(
        generation_module,
        "complete_hospital_ai_message",
        lambda *args, **kwargs: "",
    )

    return graph_module.hospital_reservation_graph.invoke(state)


def test_available_reservation_full_flow(monkeypatch):
    state = _invoke(
        {
            "user_message": "저기... 내일 오후에 진료 예약 가능할까요?",
            "conversation_state": "greeting",
            "history": [],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "asking_department"
    assert state["intent"] == "reservation"
    assert state["date"] == "내일"
    assert state["time"] == "오후"

    state = _invoke(
        {
            **state,
            "user_message": "내과 진료를 예약하고 싶습니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "confirming_info"
    assert state["department"] == "내과"

    state = _invoke(
        {
            **state,
            "user_message": "네, 맞습니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "checking_availability"
    assert state["user_action"] == "confirm_reservation_info"

    state = _invoke(
        {
            **state,
            "user_message": "네, 기다리겠습니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "reservation_available"
    assert state["availability_status"] == "available"
    assert state["available_time"] == "오후 3시"

    state = _invoke(
        {
            **state,
            "user_message": "네, 그 시간으로 예약하고 싶습니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "reservation_confirmed"
    assert state["reservation_confirmed"] is True
    assert state["selected_time"] == "오후 3시"

    state = _invoke(
        {
            **state,
            "user_message": "네, 감사합니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "closing"

    state = _invoke(
        {
            **state,
            "user_message": "네, 감사합니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "END"
    assert state["should_end_call"] is True


def test_unavailable_reservation_alternative_time_flow(monkeypatch):
    base_state = {
        "intent": "reservation",
        "department": "내과",
        "date": "내일",
        "time": "오후",
        "conversation_state": "checking_availability",
        "simulation_result": {
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
        },
        "history": [],
    }

    state = _invoke(
        {
            **base_state,
            "user_message": "네, 기다리겠습니다.",
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "reservation_unavailable"
    assert state["availability_status"] == "unavailable"
    assert state["alternative_times"] == ["오후 4시", "오후 5시"]

    state = _invoke(
        {
            **state,
            "user_message": "다른 시간도 가능할까요?",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "suggest_alternative"
    assert state["user_action"] == "ask_other_time"

    state = _invoke(
        {
            **state,
            "user_message": "오후 4시로 하겠습니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "reservation_confirmed"
    assert state["reservation_confirmed"] is True
    assert state["selected_time"] == "오후 4시"

    state = _invoke(
        {
            **state,
            "user_message": "네, 감사합니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "closing"

    state = _invoke(
        {
            **state,
            "user_message": "네, 감사합니다.",
            "history": [
                {"role": "assistant", "content": state["ai_message"]},
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "END"
    assert state["should_end_call"] is True


def test_invalid_alternative_time_does_not_confirm(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "suggest_alternative",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다. 대신 오후 4시 또는 오후 5시 시간대는 가능합니다.",
            "user_message": "오후 7시로 하겠습니다.",
            "history": [
                {
                    "role": "assistant",
                    "content": "오후 4시와 오후 5시 중에서 원하시는 시간을 선택해 주시겠어요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "suggest_alternative"
    assert state.get("selected_time") is None
    assert state.get("reservation_confirmed") is None
    assert state["time"] == "오후"


# =========================
# 8차 보강 통합 테스트 케이스
# =========================

def test_confirming_info_change_time_flow(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "confirming_info",
            "user_message": "시간을 바꾸고 싶어요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "asking_time"
    assert state["user_action"] == "change_time"
    assert state["department"] == "내과"
    assert state["date"] == "내일"


def test_confirming_info_change_date_flow(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "confirming_info",
            "user_message": "날짜를 다시 정하고 싶어요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "asking_date"
    assert state["user_action"] == "change_date"
    assert state["department"] == "내과"
    assert state.get("time") is None


def test_confirming_info_change_department_flow(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "confirming_info",
            "user_message": "진료과를 바꾸고 싶어요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "asking_department"
    assert state["user_action"] == "change_department"
    assert state["date"] == "내일"
    assert state["time"] == "오후"


def test_reservation_available_ask_other_time_flow(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "reservation_available",
            "availability_status": "available",
            "available_time": "오후 3시",
            "alternative_times": [],
            "availability_message_hint": "내일 오후 3시에 내과 진료 예약이 가능합니다.",
            "user_message": "그 시간 말고 다른 시간으로요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후 3시에 내과 진료 예약이 가능합니다. 이 시간으로 진행하시겠습니까?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "suggest_alternative"
    assert state["user_action"] == "ask_other_time"
    assert state["reservation_confirmed"] is None


def test_reservation_unavailable_change_date_flow(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "reservation_unavailable",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다. 대신 오후 4시 또는 오후 5시 시간대는 가능합니다.",
            "user_message": "다른 날짜로 확인해주세요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후에는 예약이 모두 차 있어 대안으로 오후 4시 또는 오후 5시 시간대를 추천드립니다.",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "asking_date"
    assert state["user_action"] == "change_date"
    assert state["reservation_confirmed"] is None


def test_confirming_info_unknown_keeps_state(monkeypatch):
    monkeypatch.setattr(
        "services.flow.reservation.hospital.nodes.analyze_hospital_reservation_user_message",
        lambda conversation_state, user_message: {
            "intent": None,
            "department": None,
            "date": None,
            "time": None,
            "user_action": "unknown",
            "selected_time": None,
        },
    )

    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "confirming_info",
            "user_message": "음...",
            "history": [
                {
                    "role": "assistant",
                    "content": "내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "confirming_info"
    assert state["user_action"] == "unknown"
    assert state["reservation_confirmed"] is None


def test_suggest_alternative_unknown_keeps_state(monkeypatch):
    state = _invoke(
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "conversation_state": "suggest_alternative",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다. 대신 오후 4시 또는 오후 5시 시간대는 가능합니다.",
            "user_message": "음... 잘 모르겠어요.",
            "history": [
                {
                    "role": "assistant",
                    "content": "오후 4시와 오후 5시 중에서 원하시는 시간을 선택해 주시겠어요?",
                },
            ],
        },
        monkeypatch,
    )

    assert state["conversation_state"] == "suggest_alternative"
    assert state["user_action"] == "unknown"
    assert state["reservation_confirmed"] is None


def test_reservation_unavailable_change_date_clears_lookup_fields(monkeypatch):
    """
    reservation_unavailable 상태에서 사용자가 다른 날짜를 요청하면
    asking_date로 전이하면서 이전 예약 조회 결과를 초기화해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    monkeypatch.setattr(
        generation_module,
        "complete_hospital_ai_message",
        lambda *args, **kwargs: "원하시는 예약 날짜를 말씀해주시겠어요?",
    )

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "다른 날짜로 확인해주세요.",
            "conversation_state": "reservation_unavailable",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다. 대신 오후 4시 또는 오후 5시 시간대는 가능합니다.",
            "selected_time": "오후 4시",
            "reservation_confirmed": True,
            "simulation_result": {
                "availability_status": "unavailable",
                "availability_reason": "requested_time_full",
                "available_time": None,
                "alternative_times": ["오후 4시", "오후 5시"],
            },
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_date"
    assert result.get("availability_status") is None
    assert result.get("availability_reason") is None
    assert result.get("available_time") is None
    assert result.get("alternative_times") == []
    assert result.get("availability_message_hint") is None
    assert result.get("selected_time") is None
    assert result.get("reservation_confirmed") is None
    assert result.get("simulation_result") is None
    assert result.get("should_end_call") is False


def test_reservation_unavailable_change_date_clears_time_too(monkeypatch):
    """
    reservation_unavailable 상태에서 다른 날짜를 요청하면
    이전 시간 조건도 초기화해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    monkeypatch.setattr(
        generation_module,
        "complete_hospital_ai_message",
        lambda *args, **kwargs: "원하시는 예약 날짜를 말씀해주시겠어요?",
    )

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "다른 날짜로 확인해주세요.",
            "conversation_state": "reservation_unavailable",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다.",
            "selected_time": "오후 4시",
            "reservation_confirmed": True,
            "simulation_result": {
                "availability_status": "unavailable",
                "availability_reason": "requested_time_full",
                "available_time": None,
                "alternative_times": ["오후 4시", "오후 5시"],
            },
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_date"
    assert result.get("time") is None
    assert result.get("availability_status") is None
    assert result.get("alternative_times") == []
    assert result.get("selected_time") is None
    assert result.get("reservation_confirmed") is None


def test_asking_date_after_change_date_moves_to_asking_time(monkeypatch):
    """
    날짜 변경 이후 새 날짜를 입력하면
    time이 초기화된 상태이므로 asking_time으로 이동해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    monkeypatch.setattr(
        generation_module,
        "complete_hospital_ai_message",
        lambda *args, **kwargs: "네, 모레 예약으로 확인했습니다. 원하시는 시간대를 말씀해주시겠어요?",
    )

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "모레로 확인해주세요.",
            "conversation_state": "asking_date",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_time"
    assert result.get("date") == "모레"
    assert result.get("time") is None
    assert result.get("should_end_call") is False


def test_checking_availability_uses_template_first_without_llm(monkeypatch):
    """
    checking_availability 상태는 정형 안내 문장으로 충분하므로
    LLM을 호출하지 않고 template/fallback 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("checking_availability 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 맞습니다.",
            "conversation_state": "confirming_info",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "user_action": "confirm_reservation_info",
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "checking_availability"
    assert "확인" in result["ai_message"]
    assert result["should_end_call"] is False


def test_closing_uses_template_first_without_llm(monkeypatch):
    """
    closing 상태는 통화 마무리 정형 문장으로 충분하므로
    LLM을 호출하지 않고 template/fallback 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("closing 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "reservation_confirmed",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "selected_time": "오후 3시",
            "reservation_confirmed": True,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "closing"
    assert "마무리" in result["ai_message"] or "문의" in result["ai_message"]
    assert result["should_end_call"] is False


def test_end_uses_template_first_without_llm(monkeypatch):
    """
    END 상태는 최종 종료 문장으로 충분하므로
    LLM을 호출하지 않고 template/fallback 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("END 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 감사합니다.",
            "conversation_state": "closing",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "selected_time": "오후 3시",
            "reservation_confirmed": True,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "END"
    assert result["should_end_call"] is True
    assert "감사" in result["ai_message"] or "좋은 하루" in result["ai_message"]


def test_reservation_confirmed_uses_template_first_without_llm(monkeypatch):
    """
    reservation_confirmed 상태는 예약 완료 정형 문장으로 충분하므로
    LLM을 호출하지 않고 template/fallback 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("reservation_confirmed 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "오후 4시로 하겠습니다.",
            "conversation_state": "suggest_alternative",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": "내일 오후에는 예약이 모두 차 있습니다. 대신 오후 4시 또는 오후 5시 시간대는 가능합니다.",
            "selected_time": None,
            "reservation_confirmed": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert result["selected_time"] == "오후 4시"
    assert "예약" in result["ai_message"]
    assert "완료" in result["ai_message"] or "예약되었습니다" in result["ai_message"]


def test_reservation_confirmed_template_uses_selected_time_first(monkeypatch):
    """
    reservation_confirmed template 응답은 selected_time을 우선 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("reservation_confirmed 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 그 시간으로 예약하고 싶습니다.",
            "conversation_state": "reservation_available",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "available",
            "availability_reason": None,
            "available_time": "오후 3시",
            "alternative_times": [],
            "availability_message_hint": "내일 오후 3시에 내과 진료 예약이 가능합니다.",
            "selected_time": None,
            "reservation_confirmed": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_confirmed"
    assert result["reservation_confirmed"] is True
    assert result["selected_time"] == "오후 3시"
    assert "오후 3시" in result["ai_message"]
    assert "내과" in result["ai_message"]
    assert "예약" in result["ai_message"]


def test_reservation_available_uses_template_first_without_llm(monkeypatch):
    """
    reservation_available 상태는 예약 가능 안내 정형 문장으로 충분하므로
    LLM을 호출하지 않고 template/fallback 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("reservation_available 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 기다리겠습니다.",
            "conversation_state": "checking_availability",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "simulation_result": {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": "오후 3시",
                "alternative_times": [],
            },
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert result["availability_status"] == "available"
    assert result["available_time"] == "오후 3시"
    assert "오후 3시" in result["ai_message"]
    assert "내과" in result["ai_message"]
    assert "예약" in result["ai_message"]
    assert "가능" in result["ai_message"]


def test_reservation_available_template_keeps_recommended_replies(monkeypatch):
    """
    reservation_available 상태에서 template-first 응답을 사용하더라도
    recommended_replies는 기존처럼 유지되어야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("reservation_available 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "네, 기다리겠습니다.",
            "conversation_state": "checking_availability",
            "intent": "reservation",
            "department": "피부과",
            "date": "모레",
            "time": "오전",
            "simulation_result": {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": "오전 10시",
                "alternative_times": [],
            },
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "reservation_available"
    assert "오전 10시" in result["ai_message"]
    assert "피부과" in result["ai_message"]
    assert result.get("recommended_replies")
    assert "네, 그 시간으로 예약하고 싶습니다." in result["recommended_replies"]


def test_template_message_builder_uses_server_state_values():
    """
    template 응답 생성 함수는 서버 상태값을 기반으로 정형 응답을 만들어야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "reservation_available",
        {
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "available_time": "오후 3시",
        },
    )

    assert "내일" in message
    assert "오후 3시" in message
    assert "내과" in message
    assert "예약" in message
    assert "가능" in message


def test_template_message_builder_handles_all_template_states():
    """
    template 응답 생성 함수는 template-first 대상 상태를 직접 처리해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    base_state = {
        "department": "내과",
        "date": "내일",
        "time": "오후",
        "available_time": "오후 3시",
        "selected_time": "오후 3시",
    }

    checking_message = graph_module.build_template_ai_message(
        "checking_availability",
        base_state,
    )
    assert "확인" in checking_message
    assert "기다" in checking_message or "잠시" in checking_message

    available_message = graph_module.build_template_ai_message(
        "reservation_available",
        base_state,
    )
    assert "내일" in available_message
    assert "오후 3시" in available_message
    assert "내과" in available_message
    assert "가능" in available_message

    confirmed_message = graph_module.build_template_ai_message(
        "reservation_confirmed",
        base_state,
    )
    assert "내일" in confirmed_message
    assert "오후 3시" in confirmed_message
    assert "내과" in confirmed_message
    assert "예약" in confirmed_message

    closing_message = graph_module.build_template_ai_message(
        "closing",
        base_state,
    )
    assert "마무리" in closing_message or "문의" in closing_message

    end_message = graph_module.build_template_ai_message(
        "END",
        base_state,
    )
    assert "감사" in end_message or "좋은 하루" in end_message


def test_asking_date_uses_template_first_without_llm(monkeypatch):
    """
    asking_date 상태는 날짜를 묻는 정형 질문으로 충분하므로
    LLM을 호출하지 않고 template 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("asking_date 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "내과 진료를 예약하고 싶습니다.",
            "conversation_state": "asking_department",
            "intent": "reservation",
            "department": "내과",
            "date": None,
            "time": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_date"
    assert result["department"] == "내과"
    assert "날짜" in result["ai_message"] or "언제" in result["ai_message"] or "방문" in result["ai_message"]
    assert "시간" not in result["ai_message"]
    assert "연락처" not in result["ai_message"]
    assert result["should_end_call"] is False


def test_template_message_builder_handles_asking_date():
    """
    template 응답 생성 함수는 asking_date 상태에서 날짜 질문만 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "asking_date",
        {
            "department": "내과",
            "date": None,
            "time": None,
        },
    )

    assert "날짜" in message or "언제" in message or "방문" in message
    assert "시간" not in message
    assert "연락처" not in message


def test_asking_time_uses_template_first_without_llm(monkeypatch):
    """
    asking_time 상태는 시간을 묻는 정형 질문으로 충분하므로
    LLM을 호출하지 않고 template 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("asking_time 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "내일로 해주세요.",
            "conversation_state": "asking_date",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_time"
    assert result["department"] == "내과"
    assert result["date"] == "내일"
    assert "시간" in result["ai_message"] or "시간대" in result["ai_message"]
    assert "연락처" not in result["ai_message"]
    assert "성함" not in result["ai_message"]
    assert result["should_end_call"] is False


def test_template_message_builder_handles_asking_time():
    """
    template 응답 생성 함수는 asking_time 상태에서 시간 질문만 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "asking_time",
        {
            "department": "내과",
            "date": "내일",
            "time": None,
        },
    )

    assert "시간" in message or "시간대" in message
    assert "연락처" not in message
    assert "성함" not in message


def test_asking_department_uses_template_first_without_llm(monkeypatch):
    """
    asking_department 상태는 진료과를 묻는 정형 질문으로 충분하므로
    LLM을 호출하지 않고 template 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("asking_department 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "저기... 내일 오후에 진료 예약 가능할까요?",
            "conversation_state": "greeting",
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "asking_department"
    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후"
    assert "진료과" in result["ai_message"] or "과를" in result["ai_message"] or "진료받으실 과" in result["ai_message"] or "어느 과" in result["ai_message"] or "과 진료" in result["ai_message"]
    assert "연락처" not in result["ai_message"]
    assert "성함" not in result["ai_message"]
    assert result["should_end_call"] is False


def test_template_message_builder_handles_asking_department():
    """
    template 응답 생성 함수는 asking_department 상태에서 진료과 질문만 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "asking_department",
        {
            "date": "내일",
            "time": "오후",
            "department": None,
        },
    )

    assert "진료과" in message or "과를" in message or "진료받으실 과" in message or "어느 과" in message or "과 진료" in message
    assert "연락처" not in message
    assert "성함" not in message


def test_confirming_info_recommended_replies_do_not_include_name_or_phone(monkeypatch):
    """
    현재 MVP에서는 성함/연락처를 수집하지 않으므로
    confirming_info 추천 답변에 성함/연락처 관련 문구가 포함되면 안 된다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    monkeypatch.setattr(
        generation_module,
        "complete_hospital_ai_message",
        lambda *args, **kwargs: "내일 오후 3시 내과 진료 예약을 원하시는 것이 맞으실까요?",
    )

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "오후 3시로 하고 싶습니다.",
            "conversation_state": "asking_time",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "confirming_info"

    recommended_replies = result.get("recommended_replies") or []
    joined_replies = " ".join(recommended_replies)

    assert recommended_replies
    assert "연락처" not in joined_replies
    assert "성함" not in joined_replies
    assert "네, 맞습니다." in recommended_replies
    assert any("시간" in reply for reply in recommended_replies)
    assert any("날짜" in reply or "진료과" in reply for reply in recommended_replies)


def test_confirming_info_uses_template_first_without_llm(monkeypatch):
    """
    confirming_info 상태는 예약 정보 확인 정형 문장으로 충분하므로
    LLM을 호출하지 않고 template 응답을 사용해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    def fail_if_llm_called(*args, **kwargs):
        raise AssertionError("confirming_info 상태에서는 LLM을 호출하면 안 됩니다.")

    monkeypatch.setattr(generation_module, "complete_hospital_ai_message", fail_if_llm_called)

    result = graph_module.hospital_reservation_graph.invoke(
        {
            "user_message": "오후 3시로 하고 싶습니다.",
            "conversation_state": "asking_time",
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": None,
            "history": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == "confirming_info"
    assert result["department"] == "내과"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert "내일" in result["ai_message"]
    assert "오후 3시" in result["ai_message"]
    assert "내과" in result["ai_message"]
    assert "맞으실까요" in result["ai_message"] or "확인" in result["ai_message"] or "맞으세요" in result["ai_message"] or "될까요" in result["ai_message"]
    assert result["should_end_call"] is False


def test_template_message_builder_handles_confirming_info():
    """
    template 응답 생성 함수는 confirming_info 상태에서
    서버 상태값 기반 예약 확인 문장을 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "confirming_info",
        {
            "department": "내과",
            "date": "내일",
            "time": "오후 3시",
            "selected_time": "오후 3시",
        },
    )

    assert "내일" in message
    assert "오후 3시" in message
    assert "내과" in message
    assert "예약" in message or "진료" in message
    assert "맞으실까요" in message or "확인" in message or "맞으세요" in message or "될까요" in message


def test_template_message_builder_handles_reservation_unavailable_with_alternatives():
    """
    reservation_unavailable template 응답은 대안 시간이 있으면
    alternative_times 기반 안내 문장을 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "reservation_unavailable",
        {
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "alternative_times": ["오후 4시", "오후 5시"],
            "availability_message_hint": None,
        },
    )

    assert "내일" in message
    assert "오후" in message
    assert "예약" in message
    assert "어렵" in message or "차" in message
    assert "오후 4시" in message
    assert "오후 5시" in message
    assert "가능" in message


def test_template_message_builder_handles_reservation_unavailable_without_alternatives():
    """
    reservation_unavailable template 응답은 대안 시간이 없으면
    다른 날짜나 시간을 요청하는 안내 문장을 생성해야 한다.
    """
    from services.flow.reservation.hospital import graph as graph_module

    message = graph_module.build_template_ai_message(
        "reservation_unavailable",
        {
            "department": "내과",
            "date": "내일",
            "time": "오후",
            "availability_status": "unavailable",
            "availability_reason": "no_available_slot",
            "alternative_times": [],
            "availability_message_hint": None,
        },
    )

    assert "내일" in message
    assert "오후" in message
    assert "예약" in message
    assert "어렵" in message or "차" in message
    assert "다른 날짜" in message or "다른 시간" in message
