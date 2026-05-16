from __future__ import annotations

from typing import TypedDict, Optional, Dict, List

from langgraph.graph import StateGraph, START, END

from llm.client import complete_messages
from services.flow.hospital_reservation_extractor import extract_hospital_reservation_info
from services.flow.hospital_reservation_replies import get_recommended_replies


class HospitalReservationState(TypedDict, total=False):
    user_message: str
    conversation_state: str

    intent: Optional[str]
    department: Optional[str]
    date: Optional[str]
    time: Optional[str]
    user_name: Optional[str]
    phone_number: Optional[str]

    ai_message: Optional[str]
    recommended_replies: List[str]
    should_end_call: bool


def extract_info_node(state: HospitalReservationState) -> Dict:
    user_message = state.get("user_message", "") or ""
    extracted = extract_hospital_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent"),
        "department": extracted.get("department") or state.get("department"),
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
    }


def decide_next_state_node(state: HospitalReservationState) -> Dict:
    current_state = state.get("conversation_state") or "greeting"
    user_message = state.get("user_message", "") or ""

    if current_state == "closing":
        return {
            "conversation_state": "END",
            "should_end_call": True,
        }

    if current_state == "confirming_info":
        if any(word in user_message for word in ["네", "맞아요", "맞습니다", "확인", "좋아요"]):
            return {
                "conversation_state": "closing",
                "should_end_call": False,
            }

        if "진료과" in user_message or "과를" in user_message:
            return {"conversation_state": "asking_department", "should_end_call": False}

        if "날짜" in user_message or "요일" in user_message:
            return {"conversation_state": "asking_date", "should_end_call": False}

        if "시간" in user_message or "시" in user_message:
            return {"conversation_state": "asking_time", "should_end_call": False}

        return {"conversation_state": "confirming_info", "should_end_call": False}

    intent = state.get("intent")
    department = state.get("department")
    date = state.get("date")
    time = state.get("time")

    if current_state in ["greeting", "asking_purpose"]:
        if intent == "reservation":
            if not department:
                return {"conversation_state": "asking_department", "should_end_call": False}
            if not date:
                return {"conversation_state": "asking_date", "should_end_call": False}
            if not time:
                return {"conversation_state": "asking_time", "should_end_call": False}
            return {"conversation_state": "confirming_info", "should_end_call": False}

        return {"conversation_state": "asking_purpose", "should_end_call": False}

    if current_state == "asking_department":
        if department:
            if not date:
                return {"conversation_state": "asking_date", "should_end_call": False}
            if not time:
                return {"conversation_state": "asking_time", "should_end_call": False}
            return {"conversation_state": "confirming_info", "should_end_call": False}
        return {"conversation_state": "asking_department", "should_end_call": False}

    if current_state == "asking_date":
        if date:
            if not time:
                return {"conversation_state": "asking_time", "should_end_call": False}
            return {"conversation_state": "confirming_info", "should_end_call": False}
        return {"conversation_state": "asking_date", "should_end_call": False}

    if current_state == "asking_time":
        if time:
            return {"conversation_state": "confirming_info", "should_end_call": False}
        return {"conversation_state": "asking_time", "should_end_call": False}

    return {"conversation_state": current_state, "should_end_call": False}


def build_ai_message_prompt(state: HospitalReservationState) -> str:
    conversation_state = state.get("conversation_state") or "asking_purpose"
    user_message = state.get("user_message", "") or ""

    department = state.get("department") or "아직 없음"
    date = state.get("date") or "아직 없음"
    time = state.get("time") or "아직 없음"

    return f"""
너는 한국 병원 접수 직원 역할을 하는 통화 시뮬레이션 AI이다.

현재 대화 상태:
- {conversation_state}

현재까지 확인된 정보:
- 진료과: {department}
- 날짜: {date}
- 시간: {time}

사용자 발화:
{user_message}

응답 목표:
- 병원 접수 직원처럼 자연스럽고 공손하게 응답한다.
- 사용자의 요청을 먼저 받아준다.
- 현재 상태에서 필요한 다음 정보를 부드럽게 물어본다.
- 예약 가능 여부를 확정하지 않는다.
- 사용자를 압박하지 않는다.

금지 표현:
- 가능합니다
- 예약 가능합니다
- 예약해드리겠습니다
- 예약되었습니다
- 가능해요

출력 규칙:
- JSON을 출력하지 않는다.
- markdown 코드블록을 출력하지 않는다.
- 따옴표를 붙이지 않는다.
- assistant, user 같은 역할 이름을 출력하지 않는다.
- 설명을 붙이지 않는다.
- 병원 접수 직원의 응답 문장만 출력한다.
- 1문장 또는 아주 짧은 2문장만 출력한다.
""".strip()


def clean_ai_message(text: str) -> str:
    text = (text or "").strip()
    text = text.strip('"').strip("'").strip()
    text = text.replace("```", "").strip()

    for label in ["assistant", "user", "system"]:
        if text.lower().startswith(label):
            text = text[len(label):].strip(":： \n")

    return text


def fallback_ai_message(conversation_state: str) -> str:
    if conversation_state == "asking_department":
        return "네, 확인해드리겠습니다. 원하시는 진료과를 알려주시면 예약 가능 시간을 확인해드리겠습니다."
    if conversation_state == "asking_date":
        return "네, 확인해드리겠습니다. 원하시는 예약 날짜를 말씀해주시겠어요?"
    if conversation_state == "asking_time":
        return "네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?"
    if conversation_state == "confirming_info":
        return "말씀해주신 내용으로 확인해드리겠습니다. 예약 정보를 다시 확인해드릴까요?"
    if conversation_state == "closing":
        return "네, 확인 감사합니다. 추가로 궁금하신 점이 없으시면 통화 마무리 도와드리겠습니다."
    return "네, 확인해드리겠습니다. 어떤 진료를 원하시는지 말씀해주시겠어요?"


def generate_ai_message_node(state: HospitalReservationState) -> Dict:
    if state.get("conversation_state") == "END":
        return {
            "ai_message": "네, 감사합니다. 좋은 하루 보내세요.",
            "should_end_call": True,
        }

    prompt = build_ai_message_prompt(state)

    ai_message = complete_messages(
        messages=[{"role": "user", "content": prompt}],
        timeout_s=8,
    )

    ai_message = clean_ai_message(ai_message)

    if not ai_message:
        ai_message = fallback_ai_message(state.get("conversation_state") or "asking_purpose")

    return {"ai_message": ai_message}


def attach_recommended_replies_node(state: HospitalReservationState) -> Dict:
    conversation_state = state.get("conversation_state") or "asking_purpose"
    replies = get_recommended_replies(conversation_state)

    return {"recommended_replies": replies}


def build_hospital_reservation_graph():
    builder = StateGraph(HospitalReservationState)

    builder.add_node("extract_info", extract_info_node)
    builder.add_node("decide_next_state", decide_next_state_node)
    builder.add_node("generate_ai_message", generate_ai_message_node)
    builder.add_node("attach_recommended_replies", attach_recommended_replies_node)

    builder.add_edge(START, "extract_info")
    builder.add_edge("extract_info", "decide_next_state")
    builder.add_edge("decide_next_state", "generate_ai_message")
    builder.add_edge("generate_ai_message", "attach_recommended_replies")
    builder.add_edge("attach_recommended_replies", END)

    return builder.compile()


hospital_reservation_graph = build_hospital_reservation_graph()