import pytest

from services.flow.professor.absence import nodes as professor_absence_nodes
from services.flow.professor.absence.graph import professor_absence_graph
from services.flow.professor.appointment import nodes as professor_appointment_nodes
from services.flow.professor.appointment.graph import professor_appointment_graph
from services.flow.reservation.hair_salon import nodes as hair_salon_nodes
from services.flow.reservation.hair_salon.graph import hair_salon_reservation_graph
from services.flow.reservation.hospital import nodes as hospital_nodes
from services.flow.reservation.hospital.graph import hospital_reservation_graph
from services.flow.reservation.restaurant import nodes as restaurant_nodes
from services.flow.reservation.restaurant.graph import restaurant_reservation_graph
from services.flow.reservation.study_room import nodes as study_room_nodes
from services.flow.reservation.study_room.graph import study_room_reservation_graph

pytestmark = pytest.mark.graph_flow


INLINE_CHANGE_CASES = (
    (
        restaurant_nodes,
        "analyze_restaurant_reservation_user_message",
        restaurant_reservation_graph,
        {
            "intent": "reservation",
            "date": "내일",
            "time": "오후 6시",
            "party_size": "2명",
            "user_name": "김개굴",
            "conversation_state": "confirming_info",
        },
        {
            "intent": "reservation",
            "date": "모레",
            "time": None,
            "party_size": None,
            "user_name": None,
            "selected_time": None,
            "user_action": "change_date",
        },
        "date",
        "모레",
        "confirming_info",
    ),
    (
        hair_salon_nodes,
        "analyze_hair_salon_reservation_user_message",
        hair_salon_reservation_graph,
        {
            "intent": "reservation",
            "date": "내일",
            "time": "오후 3시",
            "service_type": "커트",
            "designer": "수진",
            "user_name": "김개굴",
            "conversation_state": "confirming_info",
        },
        {
            "intent": "reservation",
            "date": None,
            "time": "오후 5시",
            "service_type": None,
            "designer": None,
            "user_name": None,
            "selected_time": None,
            "user_action": "change_time",
        },
        "time",
        "오후 5시",
        "confirming_info",
    ),
    (
        study_room_nodes,
        "analyze_study_room_reservation_user_message",
        study_room_reservation_graph,
        {
            "intent": "reservation",
            "date": "내일",
            "start_time": "오후 2시",
            "duration": "2시간",
            "party_size": "4명",
            "user_name": "김개굴",
            "conversation_state": "confirming_info",
        },
        {
            "intent": "reservation",
            "date": None,
            "start_time": None,
            "duration": "3시간",
            "party_size": None,
            "user_name": None,
            "selected_time": None,
            "user_action": "change_duration",
        },
        "duration",
        "3시간",
        "confirming_info",
    ),
    (
        hospital_nodes,
        "analyze_hospital_reservation_user_message",
        hospital_reservation_graph,
        {
            "intent": "reservation",
            "department": "내과",
            "date": "내일",
            "time": "오후 2시",
            "user_name": "김개굴",
            "conversation_state": "confirming_info",
        },
        {
            "intent": "reservation",
            "department": "피부과",
            "date": None,
            "time": None,
            "user_name": None,
            "selected_time": None,
            "user_action": "change_department",
        },
        "department",
        "피부과",
        "confirming_info",
    ),
    (
        professor_appointment_nodes,
        "analyze_professor_appointment_user_message",
        professor_appointment_graph,
        {
            "intent": "appointment_booking",
            "appointment_purpose": "진로 상담",
            "date": "내일",
            "time": "오후 3시",
            "user_name": "김개굴",
            "conversation_state": "confirming_info",
        },
        {
            "intent": "appointment_booking",
            "appointment_purpose": None,
            "date": None,
            "time": "오후 5시",
            "user_name": None,
            "user_action": "change_time",
        },
        "time",
        "오후 5시",
        "confirming_info",
    ),
    (
        professor_absence_nodes,
        "analyze_professor_absence_user_message",
        professor_absence_graph,
        {
            "intent": "absence_notice",
            "class_name": "자료구조",
            "absence_date": "오늘",
            "absence_reason": "몸이 좋지 않음",
            "user_name": "김개굴",
            "conversation_state": "confirming_absence_info",
        },
        {
            "intent": "absence_notice",
            "class_name": None,
            "absence_date": None,
            "absence_reason": "병원 진료",
            "user_name": None,
            "user_action": "change_absence_reason",
        },
        "absence_reason",
        "병원 진료",
        "confirming_absence_info",
    ),
)


@pytest.mark.parametrize(
    ("nodes_module", "analyzer_name", "graph", "state", "analysis", "field", "value", "next_state"),
    INLINE_CHANGE_CASES,
)
def test_inline_change_replaces_value_and_returns_to_confirmation(
    monkeypatch,
    nodes_module,
    analyzer_name,
    graph,
    state,
    analysis,
    field,
    value,
    next_state,
):
    monkeypatch.setattr(nodes_module, analyzer_name, lambda *args, **kwargs: analysis)

    result = graph.invoke(
        {
            **state,
            "user_message": "새 값으로 바꿔주세요.",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result[field] == value
    assert result["conversation_state"] == next_state


@pytest.mark.parametrize(
    ("case", "collecting_state"),
    zip(
        INLINE_CHANGE_CASES,
        (
            "collecting_reservation_info",
            "collecting_reservation_info",
            "collecting_reservation_info",
            "asking_department",
            "collecting_appointment_info",
            "collecting_absence_info",
        ),
        strict=True,
    ),
)
def test_change_request_without_replacement_reopens_only_the_target_field(
    monkeypatch,
    case,
    collecting_state,
):
    nodes_module, analyzer_name, graph, state, analysis, field, _, _ = case
    analysis_without_value = {**analysis, field: None}
    monkeypatch.setattr(
        nodes_module,
        analyzer_name,
        lambda *args, **kwargs: analysis_without_value,
    )

    result = graph.invoke(
        {
            **state,
            "user_message": "그 항목을 바꾸고 싶어요.",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result[field] is None
    assert result["conversation_state"] == collecting_state


@pytest.mark.parametrize(
    "nodes_module",
    (hospital_nodes, restaurant_nodes, hair_salon_nodes, study_room_nodes),
)
def test_new_availability_lookup_clears_previous_alternative_selection(
    monkeypatch,
    nodes_module,
):
    resolver_name = next(
        name
        for name in (
            "resolve_restaurant_availability",
            "resolve_hair_salon_availability",
            "resolve_study_room_availability",
            "resolve_hospital_availability",
        )
        if hasattr(nodes_module, name)
    )
    check_name = next(
        name
        for name in (
            "check_restaurant_availability_node",
            "check_hair_salon_availability_node",
            "check_study_room_availability_node",
            "check_availability_node",
        )
        if hasattr(nodes_module, name)
    )
    monkeypatch.setattr(
        nodes_module,
        resolver_name,
        lambda state: {
            "availability_status": "unavailable",
            "availability_reason": "requested_time_full",
            "available_time": None,
            "alternative_times": ["오후 5시"],
            "availability_message_hint": "오후 5시는 가능합니다.",
            "reservation_confirmed": False,
        },
    )

    result = getattr(nodes_module, check_name)({"selected_time": "오후 4시"})

    assert result["conversation_state"] == "reservation_unavailable"
    assert result["selected_time"] is None


def test_hospital_decide_node_fails_closed_for_unvalidated_alternative():
    with pytest.raises(RuntimeError, match="validated alternative selection"):
        hospital_nodes.decide_next_state_node(
            {
                "conversation_state": "reservation_unavailable",
                "user_action": "select_alternative_time",
                "selected_time": "오 후 4 시",
                "alternative_times": ["오후 4시"],
            }
        )
