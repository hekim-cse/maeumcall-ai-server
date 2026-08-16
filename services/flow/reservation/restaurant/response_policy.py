from __future__ import annotations

from typing import List

from services.flow.reservation.restaurant.policy import (
    get_missing_restaurant_fields,
)


def choose_message(candidates: List[str], state: dict) -> str:
    """
    직전 AI 응답과 다른 문장을 우선 선택한다.
    테스트 재현성을 위해 random은 사용하지 않는다.
    """
    last_ai_message = state.get("last_ai_message")

    for message in candidates:
        if message != last_ai_message:
            return message

    if not candidates:
        raise ValueError("restaurant response policy requires at least one candidate")
    return candidates[0]


def with_service_greeting(message: str, state: dict) -> str:
    """
    첫 응답일 때만 식당명 인사말을 붙인다.
    """
    current_state = state.get("conversation_state") or "greeting"
    last_ai_message = state.get("last_ai_message")

    if current_state == "greeting" and not last_ai_message:
        service_name = state.get("service_name") or "마음식당"
        return f"네, {service_name}입니다. {message}"

    return message


def build_restaurant_response(conversation_state: str, state: dict = None) -> str:
    """
    식당 예약 상태에 맞는 정형 응답을 생성한다.
    """
    state = state or {}

    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간"
    party_size = state.get("party_size") or "인원"

    if conversation_state == "collecting_reservation_info":
        missing = get_missing_restaurant_fields(state)
        if "date" in missing:
            return with_service_greeting("예약 날짜는 언제가 괜찮으세요?", state)
        if "time" in missing:
            return f"{date} 예약으로 확인했습니다. 시간은 몇 시쯤 괜찮으세요?"
        if "party_size" in missing:
            return f"{date} {time} 예약으로 확인했습니다. 몇 분이서 오시나요?"
        if "user_name" in missing:
            return "예약자 성함을 말씀해주시겠어요?"
        raise ValueError("collecting_reservation_info requires at least one missing field")

    if conversation_state == "asking_date":
        candidates = [
            "예약 도와드리겠습니다. 예약 날짜는 언제가 괜찮으세요?",
            "예약 날짜는 언제로 도와드릴까요?",
            "방문 날짜는 언제가 괜찮으세요?",
        ]
        message = choose_message(candidates, state)
        return with_service_greeting(message, state)

    if conversation_state == "asking_time":
        candidates = [
            f"{date} 예약으로 확인했습니다. 시간은 몇 시쯤 괜찮으세요?",
            "예약 시간은 몇 시쯤 괜찮으세요?",
            f"{date} 방문 예정이시죠. 편하신 시간이 있으세요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_party_size":
        candidates = [
            f"{date} {time} 예약으로 확인했습니다. 몇 분이서 오시나요?",
            "몇 분 예약으로 도와드릴까요?",
            "방문 인원은 몇 분이실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "confirming_info":
        candidates = [
            f"{date} {time}에 {party_size} 예약 맞으실까요?",
            f"{date} {time}, {party_size} 예약으로 확인했습니다. 맞으실까요?",
            f"{date} {time} {party_size} 예약 도와드리면 될까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "checking_availability":
        candidates = [
            "잠시만요. 예약 가능한지 확인해보겠습니다.",
            "예약 가능한지 확인해볼게요. 잠시만 기다려주세요.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_available":
        available_time = state.get("available_time") or state.get("selected_time") or time
        candidates = [
            f"{date} {available_time}에 {party_size} 예약 가능합니다. 이 시간 괜찮으세요?",
            f"확인해보니 {date} {available_time} 예약 가능합니다. 진행해드릴까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_unavailable":
        alternatives = state.get("alternative_times") or []
        if alternatives:
            alternatives_text = " 또는 ".join(alternatives)
            candidates = [
                f"죄송하지만 요청하신 시간은 예약이 어렵습니다. 대신 {alternatives_text}는 가능합니다. 괜찮으신 시간이 있으세요?",
                f"해당 시간은 마감되었습니다. {alternatives_text} 중에는 예약 가능합니다.",
            ]
            return choose_message(candidates, state)

        candidates = [
            "죄송하지만 해당 시간은 예약이 어렵습니다. 다른 날짜나 시간으로 확인해드릴까요?",
            "요청하신 시간은 마감되었습니다. 다른 시간대로 도와드릴까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_confirmed":
        final_time = state.get("selected_time") or state.get("available_time") or time
        candidates = [
            f"예약 완료됐습니다. {date} {final_time}에 {party_size} 방문해주시면 됩니다.",
            f"{date} {final_time} {party_size} 예약 완료해드렸습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "closing":
        candidates = [
            "감사합니다. 좋은 하루 보내세요.",
            "네, 감사합니다. 방문 때 뵙겠습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "END":
        return "감사합니다. 좋은 하루 보내세요."

    raise ValueError(f"unsupported restaurant conversation state: {conversation_state}")
