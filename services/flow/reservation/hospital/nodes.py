from __future__ import annotations

from typing import Dict, Any

from services.flow.reservation.hospital.state import HospitalReservationState
from services.flow.reservation.hospital.extractor import extract_hospital_reservation_info
from services.flow.reservation.hospital.action_parser import parse_hospital_reservation_action
from services.flow.reservation.hospital.availability import resolve_hospital_availability
from services.flow.reservation.hospital.replies import get_recommended_replies
from services.flow.reservation.hospital.policy import clear_reservation_lookup_fields
from services.flow.reservation.common.time_utils import (
    resolve_final_reservation_time,
    is_time_in_options,
)


def extract_info_node(state: HospitalReservationState) -> Dict:
    """
    사용자 발화에서 병원 예약에 필요한 정보를 추출한다.
    새로 추출되지 않은 정보는 기존 state 값을 유지한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_hospital_reservation_info(user_message)

    current_state = state.get("conversation_state") or "greeting"

    next_time = extracted.get("time") or state.get("time")

    if current_state == "suggest_alternative":
        next_time = state.get("time")
    
    return {
        "intent": extracted.get("intent") or state.get("intent"),
        "department": extracted.get("department") or state.get("department"),
        "date": extracted.get("date") or state.get("date"),
        "time": next_time,
        "last_ai_message": state.get("last_ai_message"),
        
        "user_action": state.get("user_action"),
        "selected_time": state.get("selected_time"),

        "history": state.get("history") or [],
        "availability_status": state.get("availability_status"),
        "availability_reason": state.get("availability_reason"),
        "available_time": state.get("available_time"),
        "alternative_times": state.get("alternative_times") or [],
        "availability_message_hint": state.get("availability_message_hint"),
        "reservation_confirmed": state.get("reservation_confirmed"),
        "simulation_result": state.get("simulation_result"),
    }


def parse_user_action_node(state: HospitalReservationState) -> Dict:
    """
    사용자 발화를 user_action으로 변환한다.
    decide_next_state_node는 user_message가 아니라 user_action을 기준으로 상태를 전이한다.
    """
    parsed_action = parse_hospital_reservation_action(state)

    return {
        "user_action": parsed_action.get("user_action") or "unknown",
        "selected_time": parsed_action.get("selected_time") or state.get("selected_time"),
    }


def decide_next_state_node(state: HospitalReservationState) -> Dict:
    """
    현재까지 수집된 정보를 기준으로 다음 conversation_state를 결정한다.
    """
    current_state = state.get("conversation_state") or "greeting"
    user_action = state.get("user_action") or "unknown"

    if current_state == "closing":
        return {
            "conversation_state": "END",
            "should_end_call": True,
        }

    if current_state == "confirming_info":
        if user_action == "confirm_reservation_info":
            return {
                "conversation_state": "checking_availability",
                "should_end_call": False,
            }

        if user_action == "change_department":
            return {
                "conversation_state": "asking_department",
                "should_end_call": False,
            }

        if user_action == "change_date":
            return {
                "conversation_state": "asking_date",
                "time": None,
                "should_end_call": False,
                **clear_reservation_lookup_fields(),
            }

        if user_action == "change_time":
            return {
                "conversation_state": "asking_time",
                "should_end_call": False,
            }

        return {
            "conversation_state": "confirming_info",
            "should_end_call": False,
        }

    intent = state.get("intent")
    department = state.get("department")
    date = state.get("date")
    time = state.get("time")

    if current_state in ["greeting", "asking_purpose"]:
        if intent == "reservation":
            if not department:
                return {
                    "conversation_state": "asking_department",
                    "should_end_call": False,
                }
            if not date:
                return {
                    "conversation_state": "asking_date",
                    "should_end_call": False,
                }
            if not time:
                return {
                    "conversation_state": "asking_time",
                    "should_end_call": False,
                }
            return {
                "conversation_state": "confirming_info",
                "should_end_call": False,
            }

        return {
            "conversation_state": "asking_purpose",
            "should_end_call": False,
        }

    if current_state == "asking_department":
        if department:
            if not date:
                return {
                    "conversation_state": "asking_date",
                    "should_end_call": False,
                }
            if not time:
                return {
                    "conversation_state": "asking_time",
                    "should_end_call": False,
                }
            return {
                "conversation_state": "confirming_info",
                "should_end_call": False,
            }

        return {
            "conversation_state": "asking_department",
            "should_end_call": False,
        }

    if current_state == "asking_date":
        if date:
            if not time:
                return {
                    "conversation_state": "asking_time",
                    "should_end_call": False,
                }
            return {
                "conversation_state": "confirming_info",
                "should_end_call": False,
            }

        return {
            "conversation_state": "asking_date",
            "should_end_call": False,
        }

    if current_state == "asking_time":
        if time:
            return {
                "conversation_state": "confirming_info",
                "should_end_call": False,
            }

        return {
            "conversation_state": "asking_time",
            "should_end_call": False,
        }
    
    if current_state == "checking_availability":
        return {
            "conversation_state": "reservation_lookup",
            "should_end_call": False,
        }

    if current_state == "reservation_available":
        if user_action == "confirm_available_time":
            return {
                "conversation_state": "reservation_confirmed",
                "reservation_confirmed": True,
                "selected_time": state.get("available_time") or state.get("selected_time"),
                "should_end_call": False,
            }

        if user_action == "ask_other_time":
            return {
                "conversation_state": "suggest_alternative",
                "should_end_call": False,
            }

        return {
            "conversation_state": "reservation_available",
            "should_end_call": False,
        }

    if current_state == "reservation_unavailable":
        if user_action == "change_date":
            return {
                "conversation_state": "asking_date",
                "time": None,
                "should_end_call": False,
                **clear_reservation_lookup_fields(),
            }

        if user_action == "select_alternative_time":
            selected_time = state.get("selected_time")
            alternative_times = state.get("alternative_times") or []
            
            if is_time_in_options(selected_time, alternative_times):
                return {
                    "conversation_state": "reservation_confirmed",
                    "reservation_confirmed": True,
                    "selected_time": selected_time,
                    "should_end_call": False,
                }
            
            return {
                "conversation_state": "suggest_alternative",
                "selected_time": None,
                "should_end_call": False,
            }
            
        if user_action == "ask_other_time":
            return {
                "conversation_state": "suggest_alternative",
                "should_end_call": False,
            }

        return {
            "conversation_state": "reservation_unavailable",
            "should_end_call": False,
        }

    if current_state == "suggest_alternative":
        if user_action == "select_alternative_time":
            selected_time = state.get("selected_time")
            alternative_times = state.get("alternative_times") or []
            
            if is_time_in_options(selected_time, alternative_times):
                return {
                    "conversation_state": "reservation_confirmed",
                    "reservation_confirmed": True,
                    "selected_time": selected_time,
                    "should_end_call": False,
                }
            
            return {
                "conversation_state": "suggest_alternative",
                "selected_time": None,
                "should_end_call": False,
            }

        if user_action == "change_date":
            return {
                "conversation_state": "asking_date",
                "time": None,
                "should_end_call": False,
                **clear_reservation_lookup_fields(),
            }

        if user_action == "ask_other_time":
            return {
                "conversation_state": "suggest_alternative",
                "should_end_call": False,
            }

        return {
            "conversation_state": "suggest_alternative",
            "should_end_call": False,
        }

    if current_state == "reservation_confirmed":
        return {
            "conversation_state": "closing",
            "should_end_call": False,
        }

    return {
        "conversation_state": current_state,
        "should_end_call": False,
    }


def attach_recommended_replies_node(state: HospitalReservationState) -> Dict:
    conversation_state = state.get("conversation_state") or "asking_purpose"
    replies = get_recommended_replies(conversation_state)

    return {"recommended_replies": replies}


def check_availability_node(state: HospitalReservationState) -> Dict:
    """
    checking_availability 상태에서 예약 가능 여부를 결정한다.
    실제 API가 아니라 시뮬레이션 엔진 결과를 사용한다.
    """
    result = resolve_hospital_availability(state)

    next_state = (
        "reservation_available"
        if result.get("availability_status") == "available"
        else "reservation_unavailable"
    )

    return {
        **result,
        "conversation_state": next_state,
        "should_end_call": False,
    }
