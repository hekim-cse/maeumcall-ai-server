from services.flow import hospital_reservation_graph as graph_module


def _invoke(state: dict, monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "complete_hf_messages",
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
    assert state["time"] == "오후"


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
    from services.flow import hospital_reservation_graph as graph_module

    monkeypatch.setattr(
        graph_module,
        "complete_hf_messages",
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
