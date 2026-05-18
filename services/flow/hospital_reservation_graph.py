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

    history: List[Dict[str, str]]

    recommended_replies: List[str]
    should_end_call: bool


def choose_message(candidates: List[str], state: dict) -> str:
    """
    직전 ai_message와 같은 문장을 피해서 후보 중 하나를 선택한다.
    fallback은 최후 안전장치로만 사용하지만,
    fallback이 사용될 경우에도 같은 문장이 반복되지 않도록 한다.
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
    """
    사용자 발화에서 병원 예약에 필요한 정보를 추출한다.
    새로 추출되지 않은 정보는 기존 state 값을 유지한다.
    """
    user_message = state.get("user_message", "") or ""
    extracted = extract_hospital_reservation_info(user_message)

    return {
        "intent": extracted.get("intent") or state.get("intent"),
        "department": extracted.get("department") or state.get("department"),
        "date": extracted.get("date") or state.get("date"),
        "time": extracted.get("time") or state.get("time"),
        "last_ai_message": state.get("last_ai_message"),
        "history": state.get("history") or [],
    }


def decide_next_state_node(state: HospitalReservationState) -> Dict:
    """
    현재까지 수집된 정보를 기준으로 다음 conversation_state를 결정한다.
    """
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
            return {
                "conversation_state": "asking_department",
                "should_end_call": False,
            }

        if "날짜" in user_message or "요일" in user_message:
            return {
                "conversation_state": "asking_date",
                "should_end_call": False,
            }

        if "시간" in user_message or "시" in user_message:
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
    else:
        task = "사용자의 전화 목적을 부드럽게 확인해라."

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
- 병원 접수 직원의 응답 한 문장만 출력한다.
- JSON, markdown, 따옴표, assistant, user를 출력하지 않는다.
- 이미 확인된 정보는 다시 묻지 않는다.
- 예약 가능 여부를 확정하지 않는다.
- 예약이 완료되었다고 말하지 않는다.
- 예약이 확인되었다고 말하지 않는다.
- "예약 가능합니다", "예약해드리겠습니다", "예약되었습니다"를 쓰지 않는다.
- "확인되었습니다", "예약이 확인되었습니다", "예약이 완료되었습니다"를 쓰지 않는다.
- "가능합니다", "가능하십니다", "예약 가능", "예약이 가능"을 절대 쓰지 않는다.
- "가능하신지", "가능한지", "확인 후 안내" 같은 표현을 쓰지 않는다.
- "추가로 필요한 사항", "변경이 있으신가요"를 쓰지 않는다.
- "시간대가 있으신가요", "몇 시", "시간을 알려주세요"처럼 시간을 다시 묻지 않는다.
- confirming_info 상태라면 반드시 예약 의사가 맞는지 확인하는 질문만 한다.
- confirming_info 상태라면 반드시 "예약"이라는 단어를 포함한다.
- confirming_info 상태라면 반드시 "맞으실까요?", "맞을까요?", "확인해도 될까요?" 중 하나로 끝낸다.
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
    elif conversation_state == "closing":
        task = "통화를 마무리하는 문장만 작성해라."
    else:
        task = "현재 상태에 맞는 병원 접수 직원 응답을 한 문장으로 작성해라."

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
- 병원 접수 직원의 응답 한 문장만 출력한다.
- JSON, markdown, 따옴표, assistant, user를 출력하지 않는다.
- 이미 확인된 정보는 다시 묻지 않는다.
- 예약 가능 여부를 확정하지 않는다.
- "예약 가능합니다", "예약해드리겠습니다", "예약되었습니다"를 쓰지 않는다.
- "가능합니다", "가능하십니다", "예약 가능", "예약이 가능"을 절대 쓰지 않는다.
- "가능하신지", "가능한지", "확인 후 안내" 같은 표현을 쓰지 않는다.
- "시간대가 있으신가요", "몇 시", "시간을 알려주세요"처럼 시간을 다시 묻지 않는다.
- confirming_info 상태라면 반드시 사용자의 의사가 맞는지 확인하는 질문만 한다.
- confirming_info 상태라면 반드시 "맞으실까요?", "맞을까요?", "확인해도 될까요?" 중 하나로 끝낸다.
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
        "예약 가능합니다",
        "예약해드리겠습니다",
        "예약되었습니다",
        "예약 완료",
        "예약이 완료",
        "예약이 가능",
        "가능하십니다",
        "가능하신지",
        "가능한지",
        "확인하기 위해",
        "확인 후",
        "확인되었습니다",
        "예약이 확인되었습니다",
        "예약이 완료되었습니다",    
        "바로 안내해드리겠습니다",
        "정상적으로 잡혀",
        "추가로 필요한 사항",
        "변경이 있으신가요",
    ]

    if any(phrase in text for phrase in banned_phrases):
        return ""

    if len(text) < 8:
        return ""

    return text


def validate_ai_message_by_state(text: str, state: dict) -> bool:
    """
    LLM이 생성한 문장이 현재 conversation_state에 맞는지 검증한다.
    True면 LLM 문장을 그대로 사용하고,
    False면 retry 또는 fallback을 사용한다.
    """
    text = (text or "").strip()

    if not text:
        return False

    conversation_state = state.get("conversation_state") or "asking_purpose"

    banned_phrases = [
        "예약 가능합니다",
        "예약해드리겠습니다",
        "예약되었습니다",
        "예약 완료",
        "예약이 완료",
        "예약이 가능",
        "가능하십니다",
        "가능하신지",
        "가능한지",
        "확인하기 위해",
        "확인 후",
        "확인되었습니다",
        "예약이 확인되었습니다",
        "예약이 완료되었습니다",    
        "바로 안내해드리겠습니다",
        "정상적으로 잡혀",
        "추가로 필요한 사항",
        "변경이 있으신가요",
    ]

    if any(phrase in text for phrase in banned_phrases):
        return False

    if conversation_state == "asking_department":
        has_department_question = any(keyword in text for keyword in [
            "진료과",
            "과를",
            "어느 과",
            "무슨 과",
            "진료받으실 과",
        ])

        asks_wrong_info = any(keyword in text for keyword in [
            "날짜",
            "요일",
            "시간대",
            "몇 시",
            "연락처",
            "성함",
        ])

        too_verbose = any(phrase in text for phrase in [
            "알려주시면 더 정확하게",
            "알려주시면 더 정확히",
            "도와드릴 수 있습니다",
            "안내해드릴 수 있습니다",
        ])

        too_long = len(text) > 70

        return (
            has_department_question
            and not asks_wrong_info
            and not too_verbose
            and not too_long
        )   

    if conversation_state == "asking_date":
        has_date_question = any(keyword in text for keyword in [
            "날짜",
            "언제",
            "요일",
            "방문",
        ])

        asks_wrong_info = any(keyword in text for keyword in [
            "진료과",
            "어느 과",
            "시간대",
            "몇 시",
            "연락처",
            "성함",
        ])

        return has_date_question and not asks_wrong_info

    if conversation_state == "asking_time":
        has_time_question = any(keyword in text for keyword in [
            "시간",
            "시간대",
            "몇 시",
            "오전",
            "오후",
        ])

        asks_wrong_info = any(keyword in text for keyword in [
            "진료과",
            "어느 과",
            "날짜",
            "요일",
            "연락처",
            "성함",
        ])

        return has_time_question and not asks_wrong_info

    if conversation_state == "confirming_info":
        department = state.get("department")
        date = state.get("date")
        time = state.get("time")

        has_confirm_question = any(keyword in text for keyword in [
            "맞으실까요",
            "맞을까요",
            "맞습니까",
            "맞으신가요",
            "확인하면 될까요",
            "확인해도 될까요",
            "확인해드려도 될까요",
        ])

        asks_new_info = any(keyword in text for keyword in [
            "알려주시겠어요",
            "말씀해주시겠어요",
            "있으실까요",
            "있으신가요",
            "정해져 있으신가요",
            "몇 시",
            "어느 과",
            "날짜",
            "시간대",
            "성함",
            "연락처",
        ])

        has_saved_info = True

        if department and department not in text:
            has_saved_info = False

        if date and date not in text:
            has_saved_info = False

        if time and time not in text:
            has_saved_info = False

        # confirming_info 상태에서는 "예약"이라는 단어가 포함되어야
        # 단순 진료 확인이 아니라 예약 정보 확인 문장으로 판단한다.
        has_reservation_word = "예약" in text

        return (
            has_confirm_question
            and has_saved_info
            and has_reservation_word
            and not asks_new_info
        )

    if conversation_state == "closing":
        return any(keyword in text for keyword in [
            "궁금하신 점",
            "문의",
            "마무리",
            "감사",
            "좋은 하루",
        ])

    if conversation_state == "END":
        return any(keyword in text for keyword in [
            "감사합니다",
            "좋은 하루",
            "편안한 하루",
        ])

    return True


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
    """
    ai_message 생성 노드이다.

    우선순위:
    1. LLM 1차 응답
    2. LLM retry 응답
    3. fallback 응답
    """
    if state.get("conversation_state") == "END":
        ai_message = fallback_ai_message("END", state)
        return {
            "ai_message": ai_message,
            "last_ai_message": ai_message,
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

    if ai_message and validate_ai_message_by_state(ai_message, state):
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

    if retry_ai_message and validate_ai_message_by_state(retry_ai_message, state):
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