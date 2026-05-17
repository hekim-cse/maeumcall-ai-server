from __future__ import annotations

import random
from typing import TypedDict, Optional, Dict, List

from langgraph.graph import StateGraph, START, END

from llm.huggingface_provider import complete_hf_messages
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
    last_ai_message: Optional[str]

    recommended_replies: List[str]
    should_end_call: bool


def choose_message(candidates: List[str], state: dict) -> str:
    """
    직전 ai_message와 같은 문장을 피해서 후보 중 하나를 선택한다.
    Flutter가 scenarioState.last_ai_message를 다음 요청에 다시 보내주면
    같은 상태에서 같은 응답이 반복되는 문제를 줄일 수 있다.
    """
    last_ai_message = state.get("last_ai_message")

    filtered = [
        message for message in candidates
        if message != last_ai_message
    ]

    if not filtered:
        filtered = candidates

    return random.choice(filtered)


def extract_info_node(state: HospitalReservationState) -> Dict:
    user_message = state.get("user_message", "") or ""
    extracted = extract_hospital_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent"),
        "department": extracted.get("department") or state.get("department"),
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
        "last_ai_message": state.get("last_ai_message"),
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

    department = state.get("department") or "없음"
    date = state.get("date") or "없음"
    time = state.get("time") or "없음"

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
        task = f"{date} {time} {department} 진료 예약을 원하는지 확인해라."
    elif conversation_state == "closing":
        task = "통화를 자연스럽게 마무리해라."
    else:
        task = "사용자의 전화 목적을 부드럽게 확인해라."

    return f"""
너는 한국 병원 접수 직원이다.

현재 상태: {conversation_state}

확인된 정보:
- 진료과: {department}
- 날짜: {date}
- 시간: {time}

사용자 발화:
{user_message}

해야 할 일:
{task}

규칙:
- 병원 접수 직원의 응답 한 문장만 출력한다.
- JSON, markdown, 따옴표, assistant, user를 출력하지 않는다.
- 이미 확인된 정보는 다시 묻지 않는다.
- 현재 상태에서 부족한 정보 하나만 묻는다.
- 예약 가능 여부를 확정하지 않는다.
- "예약 가능합니다", "예약해드리겠습니다", "예약되었습니다"를 쓰지 않는다.
- "알려주시면 더 정확히 안내해드릴 수 있습니다" 같은 긴 안내문을 쓰지 않는다.
- 질문은 짧게 끝낸다.
""".strip()


def clean_ai_message(text: str) -> str:
    text = (text or "").strip()

    # 코드블록 제거
    text = text.replace("```json", "").replace("```", "").strip()

    # JSON/응답 필드가 섞이면 실패 처리
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

    # assistant/user/system 라벨 제거
    for label in ["assistant", "user", "system"]:
        if text.lower().startswith(label):
            text = text[len(label):].strip(":： \n")

    # 여러 줄이면 첫 번째 줄만 사용
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        text = lines[0]

    # 앞뒤 따옴표 제거
    text = text.strip().strip('"').strip("'").strip()

    # 정말 위험한 표현만 금지한다.
    # 너무 넓게 막으면 LLM 응답이 계속 fallback으로 떨어진다.
    banned_phrases = [
        "예약 가능합니다",
        "예약해드리겠습니다",
        "예약되었습니다",
        "예약 완료",
        "예약이 완료",
    ]

    if any(phrase in text for phrase in banned_phrases):
        return ""

    # 너무 짧거나 깨진 문장 방지
    if len(text) < 8:
        return ""

    return text


def refine_ai_message_by_state(text: str, state: dict) -> str:
    """
    LLM이 생성한 문장을 상태별 목표에 맞게 보정한다.
    같은 상태에서 같은 문장이 반복되는 것을 줄이기 위해
    상태별 자연스러운 후보 문장 중 하나를 선택할 수 있다.
    """
    text = (text or "").strip()

    conversation_state = state.get("conversation_state") or "asking_purpose"
    department = state.get("department")
    date = state.get("date")
    time = state.get("time")

    if conversation_state == "asking_department":
        repeated_patterns = [
            "원하시는 진료과가 있으신가요?",
            "원하시는 진료과를 말씀해주시겠어요?",
            "어떤 진료과로 예약을 원하시나요?",
        ]

        too_verbose_patterns = [
            "알려주시면",
            "안내해드릴 수 있습니다",
            "더 정확히",
            "도와드릴 수 있습니다",
            "어떤 진료과로 예약을 원하시는지",
        ]

        should_replace = (
            text in repeated_patterns
            or any(pattern in text for pattern in too_verbose_patterns)
            or len(text) > 70
        )

        if should_replace:
            if date and time:
                candidates = [
                    f"네, {date} {time} 진료 예약을 원하시는군요. 원하시는 진료과를 말씀해주시겠어요?",
                    f"네, {date} {time} 예약 문의로 확인했습니다. 진료받으실 과를 알려주시겠어요?",
                    f"네, 확인해드리겠습니다. {date} {time}에 진료받으실 과를 말씀해주시겠어요?",
                    f"네, {date} {time} 진료 예약 확인을 위해 원하시는 진료과를 알려주시겠어요?",
                    f"네, {date} {time} 방문을 원하시는군요. 어느 진료과로 예약을 원하시나요?",
                ]
                return choose_message(candidates, state)

            candidates = [
                "네, 확인해드리겠습니다. 원하시는 진료과를 말씀해주시겠어요?",
                "네, 진료 예약을 원하시는군요. 진료받으실 과를 알려주시겠어요?",
                "네, 확인 도와드리겠습니다. 원하시는 진료과가 있으실까요?",
            ]
            return choose_message(candidates, state)

    if conversation_state == "asking_date":
        if len(text) > 70 or "시간" in text:
            if department:
                candidates = [
                    f"네, {department} 진료 예약을 원하시는군요. 원하시는 날짜를 말씀해주시겠어요?",
                    f"네, {department} 진료로 확인했습니다. 방문을 원하시는 날짜가 있으실까요?",
                    f"네, 확인해드리겠습니다. {department} 진료 예약 날짜를 말씀해주시겠어요?",
                ]
                return choose_message(candidates, state)

            candidates = [
                "네, 확인해드리겠습니다. 원하시는 예약 날짜를 말씀해주시겠어요?",
                "네, 진료 예약을 위해 방문을 원하시는 날짜를 알려주시겠어요?",
            ]
            return choose_message(candidates, state)

    if conversation_state == "asking_time":
        if len(text) > 70 or "진료과" in text or "날짜" in text:
            if date:
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
        safe_department = department or "선택하신 진료과"
        safe_date = date or "원하시는 날짜"
        safe_time = time or "원하시는 시간대"

        candidates = [
            f"말씀해주신 내용으로 확인해드리겠습니다. {safe_date} {safe_time} {safe_department} 진료 예약을 원하시는 것이 맞으실까요?",
            f"확인하겠습니다. {safe_date} {safe_time} {safe_department} 진료 예약으로 진행을 원하시는 것이 맞으실까요?",
            f"{safe_date} {safe_time} {safe_department} 진료 예약을 원하시는 내용으로 확인하면 될까요?",
        ]
        return choose_message(candidates, state)

    return text


def fallback_ai_message(conversation_state: str, state: dict = None) -> str:
    """
    LLM 호출이 실패하거나 금지 표현이 포함된 응답을 반환했을 때 사용하는 안전 응답이다.
    같은 상태에서도 너무 반복적으로 느껴지지 않도록 여러 후보 중 하나를 선택한다.
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
            f"{date} {time} {department} 진료 예약으로 확인하면 될까요?",
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


def generate_ai_message_node(state: HospitalReservationState) -> Dict:
    if state.get("conversation_state") == "END":
        ai_message = fallback_ai_message("END", state)
        return {
            "ai_message": ai_message,
            "should_end_call": True,
        }

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

    if ai_message:
        refined_message = refine_ai_message_by_state(ai_message, state)

        if refined_message != ai_message:
            print(f"[AI message source] hf/refined: {ai_message} -> {refined_message}")
        else:
            print(f"[AI message source] hf: {ai_message}")

        ai_message = refined_message

    if not ai_message:
        ai_message = fallback_ai_message(
            state.get("conversation_state") or "asking_purpose",
            state,
        )
        print(f"[AI message source] fallback: {ai_message}")

    return {
        "ai_message": ai_message,
        "last_ai_message": ai_message,
    }


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