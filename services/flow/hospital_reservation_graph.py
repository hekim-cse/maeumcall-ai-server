from __future__ import annotations

from typing import TypedDict, Optional, Dict, List, Any

from langgraph.graph import StateGraph, START, END

from llm.huggingface_provider import complete_hf_messages
from services.flow.hospital_reservation_extractor import extract_hospital_reservation_info
from services.flow.hospital_reservation_replies import get_recommended_replies
from services.flow.hospital_reservation_availability import resolve_hospital_availability
from services.flow.hospital_reservation_action_parser import parse_hospital_reservation_action
from services.flow.hospital_reservation_validator import validate_hospital_reservation_message
from services.flow.reservation_time_utils import (
    resolve_final_reservation_time,
    format_time_options,
    is_time_in_options,
)


class HospitalReservationState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    intent: Optional[str]
    department: Optional[str]
    date: Optional[str]
    time: Optional[str]
    user_name: Optional[str]
    phone_number: Optional[str]
    
    user_action: Optional[str]
    selected_time: Optional[str]

    availability_status: Optional[str]
    availability_reason: Optional[str]
    available_time: Optional[str]
    alternative_times: List[str]
    availability_message_hint: Optional[str]
    reservation_confirmed: Optional[bool]
    simulation_result: Optional[Dict[str, Any]]

    ai_message: Optional[str]
    last_ai_message: Optional[str]

    history: List[Dict[str, str]]

    recommended_replies: List[str]
    should_end_call: bool


def choose_message(candidates: List[str], state: dict) -> str:
    """
    fallback 후보 중 직전 ai_message와 다른 첫 번째 문장을 선택한다.
    random을 사용하지 않아 테스트 재현성을 유지한다.
    """
    last_ai_message = state.get("last_ai_message")

    for message in candidates:
        if message != last_ai_message:
            return message

    return candidates[0] if candidates else ""



def clear_reservation_lookup_fields() -> Dict[str, Any]:
    """
    날짜/시간/진료과 변경처럼 예약 조건이 바뀌는 경우,
    이전 예약 가능 여부 조회 결과를 초기화한다.

    예:
    - 이전 상태: reservation_unavailable
    - 이전 대안 시간: 오후 4시, 오후 5시
    - 사용자: 다른 날짜로 확인해주세요.

    이때 이전 날짜의 조회 결과가 새 날짜 흐름에 남지 않도록 비운다.
    """
    return {
        "availability_status": None,
        "availability_reason": None,
        "available_time": None,
        "alternative_times": [],
        "availability_message_hint": None,
        "reservation_confirmed": None,
        "selected_time": None,
        "simulation_result": None,
    }

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




def format_history_for_prompt(history: List[Dict[str, str]], max_turns: int = 6) -> str:
    """
    최근 대화 기록을 LLM prompt에 넣기 좋은 문자열로 변환한다.
    너무 긴 history는 최근 max_turns개만 사용한다.
    """
    if not history:
        return "없음"

    recent_history = history[-max_turns:]

    lines = []
    for item in recent_history:
        role = item.get("role", "")
        content = item.get("content", "")

        if not content:
            continue

        if role == "user":
            lines.append(f"사용자: {content}")
        elif role in ["assistant", "ai"]:
            lines.append(f"AI: {content}")

    return "\n".join(lines) if lines else "없음"


def build_state_rules(conversation_state: str) -> str:
    common_rules = """
- 병원 접수 직원의 응답 한 문장만 출력한다.
- JSON, markdown, 따옴표, assistant, user를 출력하지 않는다.
- 이미 확인된 정보는 다시 묻지 않는다.
- 질문은 짧게 끝낸다.
""".strip()

    if conversation_state == "confirming_info":
        return common_rules + "\n" + """
- 예약 가능 여부를 확정하지 않는다.
- 예약이 완료되었다고 말하지 않는다.
- 예약이 확인되었다고 말하지 않는다.
- "예약 가능합니다", "예약해드리겠습니다", "예약되었습니다"를 쓰지 않는다.
- 반드시 예약 의사가 맞는지 확인하는 질문만 한다.
- 반드시 "예약"이라는 단어를 포함한다.
- 반드시 "맞으실까요?", "맞을까요?", "확인해도 될까요?" 중 하나로 끝낸다.
""".strip()

    if conversation_state == "checking_availability":
        return common_rules + "\n" + """
- 예약 가능/불가능 결과를 아직 말하지 않는다.
- "확인해보겠습니다", "잠시만 기다려주세요"처럼 확인 중임을 안내한다.
""".strip()

    if conversation_state == "reservation_available":
        return common_rules + "\n" + """
- 서버 시뮬레이션 결과에 나온 가능 시간만 안내한다.
- 예약 가능 표현을 사용할 수 있다.
- 이 시간으로 진행할지 물어본다.
- 없는 시간이나 다른 결과를 지어내지 않는다.
""".strip()

    if conversation_state == "reservation_unavailable":
        return common_rules + "\n" + """
- 요청한 시간대 예약이 어렵다고 안내한다.
- 서버 시뮬레이션 결과에 나온 대안 시간만 제시한다.
- 없는 대안 시간을 지어내지 않는다.
""".strip()

    if conversation_state == "suggest_alternative":
        return common_rules + "\n" + """
- 서버 시뮬레이션 결과에 있는 대안 시간만 제시한다.
- 사용자가 말한 시간이 대안 목록에 없으면 그 시간은 언급하지 않는다.
- "외에도", "그 시간도", "해당 시간도" 같은 표현을 쓰지 않는다.
- 사용자가 선택할 수 있게 묻는다.
""".strip()

    if conversation_state == "reservation_confirmed":
        return common_rules + "\n" + """
- 예약 완료 표현을 사용할 수 있다.
- 서버 상태에 있는 날짜, 시간, 진료과만 사용한다.
- 짧게 마무리한다.
- 같은 의미를 반복하지 않는다.
- "예약되었습니다"와 "예약이 완료되었습니다"를 한 문장 안에서 동시에 쓰지 않는다.
""".strip()

    if conversation_state == "closing":
        return common_rules + "\n" + """
- 예약 내용을 다시 길게 반복하지 않는다.
- 추가 문의가 없으면 통화를 마무리하겠다고 짧게 안내한다.
- "정상적으로 접수되었습니다"처럼 예약 완료 내용을 다시 확정하지 않는다.
""".strip()

    return common_rules


def build_ai_message_prompt(state: HospitalReservationState) -> str:
    """
    Kanana가 ai_message를 직접 생성하기 위한 기본 prompt를 만든다.
    history와 last_ai_message를 함께 넣어서 같은 표현 반복을 줄인다.
    """
    conversation_state = state.get("conversation_state") or "asking_purpose"
    user_message = state.get("user_message", "") or ""

    department = state.get("department") or "없음"
    date = state.get("date") or "없음"
    time = state.get("time") or "없음"

    history = state.get("history") or []
    history_text = format_history_for_prompt(history)
    last_ai_message = state.get("last_ai_message") or "없음"

    if conversation_state == "asking_department":
        task = (
            "사용자는 날짜와 시간대를 말했지만 진료과를 말하지 않았다. "
            "예약 가능 여부를 말하지 말고, 원하시는 진료과만 부드럽게 물어봐라."
        )
    elif conversation_state == "asking_date":
        task = (
            "사용자는 진료과를 말했지만 날짜를 말하지 않았다. "
            "예약 날짜만 부드럽게 물어봐라."
        )
    elif conversation_state == "asking_time":
        task = (
            "사용자는 진료과와 날짜를 말했지만 시간을 말하지 않았다. "
            "시간대만 부드럽게 물어봐라."
        )
    elif conversation_state == "confirming_info":
        task = (
            f"{date} {time} {department} 진료 예약을 원하는지 확인하는 질문을 해라. "
            "예약 가능 여부를 조회하거나 확정하지 말고, 사용자의 의사가 맞는지만 물어봐라. "
            "반드시 아래 의미의 확인 질문만 작성해라: "
            f"'{date} {time} {department} 진료 예약을 원하시는 것이 맞으실까요?'"
        )
    elif conversation_state == "closing":
        task = "통화를 자연스럽게 마무리해라."
    elif conversation_state == "checking_availability":
        task = (
            "사용자가 예약 정보가 맞다고 확인했다. "
            "예약 가능 여부를 확인해보겠다고 말하고 잠시 기다려달라고 안내해라. "
            "예약 가능/불가능 결과를 아직 말하지 마라."
        )
    elif conversation_state == "reservation_available":
        final_time = resolve_final_reservation_time(state) or time
        availability_message_hint = state.get("availability_message_hint") or ""
        task = (
            f"서버 시뮬레이션 결과는 다음과 같다: {availability_message_hint} "
            f"{date} {final_time} {department} 진료 예약이 가능하다고 안내하고, "
            "이 시간으로 진행할지 물어봐라."
        )
    elif conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or []
        alternatives_text = format_time_options(alternatives)
        availability_message_hint = state.get("availability_message_hint") or ""
        task = (
            f"서버 시뮬레이션 결과는 다음과 같다: {availability_message_hint} "
            f"요청한 예약은 어렵다고 안내하고, 대안 시간 {alternatives_text} 중 괜찮은 시간이 있는지 물어봐라."
        )
    elif conversation_state == "suggest_alternative":
        alternatives = state.get("alternative_times") or []
        alternatives_text = format_time_options(alternatives)
        task = (
            f"대안 시간은 {alternatives_text}이다. "
            "사용자에게 가능한 대안 시간 중 선택할 수 있도록 부드럽게 안내해라."
        )
    elif conversation_state == "reservation_confirmed":
        final_time = resolve_final_reservation_time(state) or time
        task = (
            f"{date} {final_time} {department} 진료 예약이 완료되었다고 한 문장으로 안내해라. "
            "같은 의미를 반복하지 말고, 예약 완료 표현은 한 번만 사용해라."
        )
    else:

        task = "현재 상태에 맞는 병원 접수 직원 응답을 한 문장으로 작성해라."

    state_rules = build_state_rules(conversation_state)

    return f"""
너는 한국 병원 접수 직원이다.

현재 상태:
{conversation_state}

확인된 정보:
- 진료과: {department}
- 날짜: {date}
- 시간: {time}

최근 대화:
{history_text}

직전 AI 응답:
{last_ai_message}

현재 사용자 발화:
{user_message}

해야 할 일:
{task}

규칙:
{state_rules}
""".strip()



def build_retry_prompt(state: HospitalReservationState, rejected_message: str) -> str:
    """
    LLM 응답이 현재 상태에 맞지 않을 때,
    fallback으로 바로 가지 않고 한 번 더 재생성을 요청하기 위한 prompt이다.
    """
    conversation_state = state.get("conversation_state") or "asking_purpose"

    department = state.get("department") or "없음"
    date = state.get("date") or "없음"
    time = state.get("time") or "없음"

    history = state.get("history") or []
    history_text = format_history_for_prompt(history)
    last_ai_message = state.get("last_ai_message") or "없음"
    user_message = state.get("user_message", "") or ""

    if conversation_state == "confirming_info":
        task = (
            f"이미 확인된 정보는 진료과={department}, 날짜={date}, 시간={time}이다. "
            "새로운 정보를 묻지 말고, 이 예약 내용을 사용자가 원하는 것이 맞는지 확인하는 질문만 작성해라. "
            "예약이 완료되었거나 확인되었다고 말하지 마라. "
            "반드시 다음 형식과 같은 의미의 확인 질문 한 문장만 작성해라: "
            f"{date} {time} {department} 진료 예약을 원하시는 것이 맞으실까요?" 
        )
    elif conversation_state == "asking_department":
        task = "진료과만 물어봐라. 날짜, 시간, 연락처, 성함은 묻지 마라."
    elif conversation_state == "asking_date":
        task = "예약 날짜만 물어봐라. 진료과, 시간, 연락처, 성함은 묻지 마라."
    elif conversation_state == "asking_time":
        task = "예약 시간대만 물어봐라. 진료과, 날짜, 연락처, 성함은 묻지 마라."
    elif conversation_state == "reservation_confirmed":
        final_time = resolve_final_reservation_time(state) or time
        task = (
            f"{date} {final_time} {department} 진료 예약이 완료되었다고 한 문장으로 안내해라. "
            "같은 의미를 반복하지 말고, 예약 완료 표현은 한 번만 사용해라."
        )
    elif conversation_state == "closing":
        task = "통화를 마무리하는 문장만 작성해라."
    else:
        task = "현재 상태에 맞는 병원 접수 직원 응답을 한 문장으로 작성해라."
    state_rules = build_state_rules(conversation_state)
    
    return f"""
방금 생성한 응답은 현재 대화 상태에 맞지 않았다.

부적절했던 응답:
{rejected_message}

현재 상태:
{conversation_state}

확인된 정보:
- 진료과: {department}
- 날짜: {date}
- 시간: {time}

최근 대화:
{history_text}

직전 AI 응답:
{last_ai_message}

현재 사용자 발화:
{user_message}

다시 작성해야 할 일:
{task}

규칙:
{state_rules}
""".strip()


def clean_ai_message(text: str) -> str:
    """
    LLM 출력에서 코드블록, JSON 조각, 라벨, 위험 표현을 제거하거나 실패 처리한다.
    """
    text = (text or "").strip()

    text = text.replace("```json", "").replace("```", "").strip()

    invalid_tokens = [
        "{",
        "}",
        "[",
        "]",
        "etiquetteTip",
        "recommendedReplies",
        "conversationState",
        "shouldEndCall",
        "scenarioState",
        "response",
    ]

    if any(token in text for token in invalid_tokens):
        return ""

    for label in ["assistant", "user", "system"]:
        if text.lower().startswith(label):
            text = text[len(label):].strip(":： \n")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        text = lines[0]

    text = text.strip().strip('"').strip("'").strip()

    banned_phrases = [
        "바로 안내해드리겠습니다",
        "정상적으로 잡혀",
    ]

    if any(phrase in text for phrase in banned_phrases):
        return ""

    if len(text) < 8:
        return ""

    return text


def fallback_ai_message(conversation_state: str, state: dict = None) -> str:
    """
    LLM 1차 생성과 retry가 모두 실패했을 때 사용하는 최후 안전 응답이다.
    """
    state = state or {}

    department = state.get("department") or "선택하신 진료과"
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간대"

    if conversation_state == "asking_department":
        if date != "원하시는 날짜" and time != "원하시는 시간대":
            candidates = [
                f"네, {date} {time} 진료 예약을 원하시는군요. 원하시는 진료과를 말씀해주시겠어요?",
                f"네, {date} {time} 예약 문의로 확인했습니다. 진료받으실 과를 알려주시겠어요?",
                f"네, 확인해드리겠습니다. {date} {time}에 진료받으실 과를 말씀해주시겠어요?",
                f"네, {date} {time} 진료 예약 확인을 위해 원하시는 진료과를 알려주시겠어요?",
            ]
            return choose_message(candidates, state)

        candidates = [
            "네, 확인해드리겠습니다. 원하시는 진료과를 말씀해주시겠어요?",
            "네, 진료 예약을 원하시는군요. 진료받으실 과를 알려주시겠어요?",
            "네, 확인 도와드리겠습니다. 원하시는 진료과가 있으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_department":
        if date != "원하시는 날짜" and time != "원하시는 시간대":
            candidates = [
                f"네, {date} {time} 진료 예약을 원하시는군요. 원하시는 진료과를 말씀해주시겠어요?",
                f"네, {date} {time} 예약 문의로 확인했습니다. 진료받으실 과를 알려주시겠어요?",
                f"네, 확인해드리겠습니다. {date} {time}에 진료받으실 과를 말씀해주시겠어요?",
            ]
            return choose_message(candidates, state)

        candidates = [
            "네, 확인해드리겠습니다. 원하시는 진료과를 말씀해주시겠어요?",
            "네, 진료 예약을 원하시는군요. 진료받으실 과를 알려주시겠어요?",
            "네, 확인 도와드리겠습니다. 원하시는 진료과가 있으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_date":
        candidates = [
            "네, 확인해드리겠습니다. 원하시는 예약 날짜를 말씀해주시겠어요?",
            f"네, {department} 진료 예약을 원하시는군요. 희망하시는 날짜가 있으실까요?",
            "네, 진료 예약을 위해 방문을 원하시는 날짜를 알려주시겠어요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_time":
        if date != "원하시는 날짜":
            candidates = [
                f"네, {date} 예약으로 확인했습니다. 원하시는 시간대를 말씀해주시겠어요?",
                f"네, {date}에 진료를 원하시는군요. 편하신 시간대가 있으실까요?",
                f"네, 확인해드리겠습니다. {date} 중 원하시는 시간대를 알려주시겠어요?",
            ]
            return choose_message(candidates, state)

        candidates = [
            "네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?",
            "네, 예약을 위해 희망하시는 시간대를 알려주시겠어요?",
            "네, 편하신 시간대가 있으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "confirming_info":
        candidates = [
            f"말씀해주신 내용으로 확인해드리겠습니다. {date} {time} {department} 진료 예약을 원하시는 것이 맞으실까요?",
            f"확인하겠습니다. {date} {time} {department} 진료 예약을 원하시는 내용이 맞으실까요?",
            f"{date} {time} {department} 진료 예약을 원하시는 것으로 확인해도 될까요?",
        ]
        return choose_message(candidates, state)
    
    if conversation_state == "asking_time":
        candidates = [
            "네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?",
            f"네, {date} 예약으로 확인했습니다. 편하신 시간대가 있으실까요?",
            f"네, {date}에 진료를 원하시는군요. 원하시는 시간을 알려주시겠어요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "checking_availability":
        candidates = [
            "네, 확인해보겠습니다. 잠시만 기다려주시겠어요?",
            "네, 예약 가능 여부를 확인해보겠습니다. 잠시만 기다려주세요.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_available":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"확인 결과, {date} {final_time}에 {department} 진료 예약이 가능합니다. 이 시간으로 진행해드릴까요?",
            f"{date} {final_time} {department} 진료 예약이 가능합니다. 이 시간으로 예약을 진행할까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or ["다른 시간대"]
        alternatives_text = format_time_options(alternatives)
        candidates = [
            f"확인 결과, {date} {time}에는 예약이 어렵습니다. 대신 {alternatives_text} 시간대는 가능한데 괜찮으실까요?",
            f"요청하신 시간대는 예약이 어렵습니다. 대신 {alternatives_text} 중 가능한 시간이 있으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "suggest_alternative":
        alternatives = state.get("alternative_times") or ["다른 시간대"]
        alternatives_text = format_time_options(alternatives)
        candidates = [
            f"현재 안내 가능한 시간은 {alternatives_text}입니다. 이 중에서 괜찮으신 시간을 선택해주시겠어요?",
            f"가능한 대안 시간은 {alternatives_text}입니다. 어떤 시간이 괜찮으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_confirmed":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"네, {date} {final_time} {department} 진료 예약이 완료되었습니다.",
            f"{date} {final_time} {department} 진료 예약으로 완료되었습니다.",
        ]
        return choose_message(candidates, state)
    

    if conversation_state == "closing":
        candidates = [
            "네, 확인 감사합니다. 추가로 궁금하신 점이 없으시면 통화 마무리 도와드리겠습니다.",
            "네, 알겠습니다. 더 문의하실 내용이 없으시면 통화 마무리하겠습니다.",
            "네, 확인했습니다. 다른 문의가 없으시면 통화 마무리 도와드리겠습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "END":
        candidates = [
            "네, 감사합니다. 좋은 하루 보내세요.",
            "네, 감사합니다. 편안한 하루 보내세요.",
            "네, 문의해주셔서 감사합니다. 좋은 하루 되세요.",
        ]
        return choose_message(candidates, state)

    candidates = [
        "네, 확인해드리겠습니다. 어떤 진료를 원하시는지 말씀해주시겠어요?",
        "네, 문의 내용 확인하겠습니다. 어떤 진료 예약을 원하시나요?",
        "네, 확인 도와드리겠습니다. 원하시는 내용을 조금 더 말씀해주시겠어요?",
    ]
    return choose_message(candidates, state)






def build_template_ai_message(conversation_state: str, state: dict = None) -> str:
    """
    정형 상태에서 의도적으로 사용하는 template 응답을 생성한다.

    이 함수는 LLM 실패 대응용 fallback이 아니라,
    서버 상태값을 기반으로 정해진 상태 응답을 안정적으로 생성하기 위한 함수이다.
    """
    state = state or {}

    department = state.get("department") or "선택하신 진료과"
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간대"

    if conversation_state == "asking_time":
        candidates = [
            "네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?",
            f"네, {date} 예약으로 확인했습니다. 편하신 시간대가 있으실까요?",
            f"네, {date}에 진료를 원하시는군요. 원하시는 시간을 알려주시겠어요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "checking_availability":
        candidates = [
            "네, 확인해보겠습니다. 잠시만 기다려주시겠어요?",
            "네, 예약 가능 여부를 확인해보겠습니다. 잠시만 기다려주세요.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_available":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"확인 결과, {date} {final_time}에 {department} 진료 예약이 가능합니다. 이 시간으로 진행해드릴까요?",
            f"{date} {final_time} {department} 진료 예약이 가능합니다. 이 시간으로 예약을 진행할까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_confirmed":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"네, {date} {final_time} {department} 진료 예약이 완료되었습니다.",
            f"{date} {final_time} {department} 진료 예약으로 완료되었습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "closing":
        candidates = [
            "네, 확인 감사합니다. 추가로 궁금하신 점이 없으시면 통화 마무리 도와드리겠습니다.",
            "네, 알겠습니다. 더 문의하실 내용이 없으시면 통화 마무리하겠습니다.",
            "네, 확인했습니다. 다른 문의가 없으시면 통화 마무리 도와드리겠습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "END":
        candidates = [
            "네, 감사합니다. 좋은 하루 보내세요.",
            "네, 감사합니다. 편안한 하루 보내세요.",
            "네, 문의해주셔서 감사합니다. 좋은 하루 되세요.",
        ]
        return choose_message(candidates, state)

    return fallback_ai_message(conversation_state, state)

def should_use_template_first(conversation_state: str) -> bool:
    """
    LLM 호출 없이 정형 응답으로 충분한 상태인지 판단한다.

    이 상태들은 응답 문장이 거의 고정되어 있어
    Kanana 호출보다 fallback/template 응답을 우선 사용하는 것이 안정적이다.
    """
    return conversation_state in {
        "asking_department",
        "asking_date",
        "asking_time",
        "checking_availability",
        "reservation_available",
        "reservation_confirmed",
        "closing",
        "END",
    }

def generate_ai_message_node(state: HospitalReservationState) -> Dict:
    """
    ai_message 생성 노드이다.

    우선순위:
    1. 정형 응답으로 충분한 상태는 template/fallback 우선 사용
    2. 그 외 상태는 LLM 1차 응답
    3. LLM retry 응답
    4. fallback 응답
    """
    conversation_state = state.get("conversation_state") or "asking_purpose"

    if should_use_template_first(conversation_state):
        ai_message = build_template_ai_message(conversation_state, state)
        result = {
            "ai_message": ai_message,
            "last_ai_message": ai_message,
        }

        if conversation_state == "END":
            result["should_end_call"] = True

        print(f"[AI message source] template-first: {ai_message}")
        return result

    prompt = build_ai_message_prompt(state)

    raw_ai_message = complete_hf_messages(
        messages=[{"role": "user", "content": prompt}],
        max_new_tokens=45,
        do_sample=True,
        temperature=0.35,
        top_p=0.85,
        repetition_penalty=1.08,
    )

    print(f"[HF raw ai_message] {raw_ai_message}")

    ai_message = clean_ai_message(raw_ai_message)

    if ai_message and validate_hospital_reservation_message(ai_message, state):
        print(f"[AI message source] hf: {ai_message}")
        return {
            "ai_message": ai_message,
            "last_ai_message": ai_message,
        }

    if ai_message:
        print(f"[AI message rejected] {ai_message}")
    else:
        print("[AI message rejected] empty or invalid output")

    retry_prompt = build_retry_prompt(
        state=state,
        rejected_message=ai_message or raw_ai_message or "",
    )

    retry_raw_ai_message = complete_hf_messages(
        messages=[{"role": "user", "content": retry_prompt}],
        max_new_tokens=40,
        do_sample=False,
        # temperature=0.25,
        # top_p=0.8,
        repetition_penalty=1.08,
    )

    print(f"[HF retry raw ai_message] {retry_raw_ai_message}")

    retry_ai_message = clean_ai_message(retry_raw_ai_message)

    if retry_ai_message and validate_hospital_reservation_message(retry_ai_message, state):
        print(f"[AI message source] hf/retry: {retry_ai_message}")
        return {
            "ai_message": retry_ai_message,
            "last_ai_message": retry_ai_message,
        }

    if retry_ai_message:
        print(f"[AI retry rejected] {retry_ai_message}")
    else:
        print("[AI retry rejected] empty or invalid output")

    fallback_message = fallback_ai_message(
        state.get("conversation_state") or "asking_purpose",
        state,
    )

    print(f"[AI message source] fallback: {fallback_message}")

    return {
        "ai_message": fallback_message,
        "last_ai_message": fallback_message,
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

def route_after_decide(state: HospitalReservationState) -> str:
    conversation_state = state.get("conversation_state")

    if conversation_state == "reservation_lookup":
        return "check_availability"

    return "generate_ai_message"


def build_hospital_reservation_graph():
    builder = StateGraph(HospitalReservationState)

    builder.add_node("extract_info", extract_info_node)
    builder.add_node("parse_user_action", parse_user_action_node)
    builder.add_node("decide_next_state", decide_next_state_node)
    builder.add_node("check_availability", check_availability_node)
    builder.add_node("generate_ai_message", generate_ai_message_node)
    builder.add_node("attach_recommended_replies", attach_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "parse_user_action")
    builder.add_edge("parse_user_action", "decide_next_state")

    builder.add_conditional_edges(
        "decide_next_state",
        route_after_decide,
        {
            "check_availability": "check_availability",
            "generate_ai_message": "generate_ai_message",
        },
    )

    builder.add_edge("check_availability", "generate_ai_message")
    builder.add_edge("generate_ai_message", "attach_recommended_replies")
    builder.add_edge("attach_recommended_replies", END)

    return builder.compile()

hospital_reservation_graph = build_hospital_reservation_graph()
