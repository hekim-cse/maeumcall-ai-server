from __future__ import annotations

from typing import List

from services.flow.reservation.common.time_utils import (
    resolve_final_reservation_time,
    format_time_options,
)

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
                f"{date} {time} 예약이시죠? 어느 과로 진료 보실까요?",
                f"{date} {time}로 확인했습니다. 어느 과로 진료 보실까요?",
                f"{date} {time}에 어느 과로 진료 보실까요?",
                f"{date} {time} 예약으로 확인할게요. 어느 과로 진료 보실까요?",
            ]
            return choose_message(candidates, state)

        candidates = [
            "예약 도와드릴게요. 어느 과로 진료 보실까요?",
            "어느 과로 진료 보실까요?",
            "어느 과로 예약 도와드릴까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_department":
        if date != "원하시는 날짜" and time != "원하시는 시간대":
            candidates = [
                f"{date} {time} 예약이시죠? 어느 과로 진료 보실까요?",
                f"{date} {time}로 확인했습니다. 어느 과로 진료 보실까요?",
                f"{date} {time}에 어느 과로 진료 보실까요?",
            ]
            return choose_message(candidates, state)

        candidates = [
            "예약 도와드릴게요. 어느 과로 진료 보실까요?",
            "어느 과로 진료 보실까요?",
            "어느 과로 예약 도와드릴까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "asking_date":
        candidates = [
            "예약 날짜는 언제가 괜찮으세요?",
            f"{department} 진료 예약이시죠. 날짜는 언제가 괜찮으세요?",
            "방문 날짜는 언제가 괜찮으세요?",
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
            "시간은 몇 시쯤 괜찮으세요?",
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
            "시간은 몇 시쯤 괜찮으세요?",
            f"{date} 예약으로 확인했습니다. 시간은 몇 시쯤 괜찮으세요?",
            f"{date} 방문 예정이시죠. 편하신 시간대가 있으세요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "confirming_info":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"{date} {final_time} {department} 진료 맞으실까요?",
            f"{date} {final_time}, {department}로 예약 도와드릴까요?",
            f"{date} {final_time} {department} 진료로 확인했습니다. 맞으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "checking_availability":
        candidates = [
            "잠시만요. 예약 가능한지 확인해볼게요.",
            "예약 가능한지 확인해보겠습니다. 잠시만 기다려주세요.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_available":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"{date} {final_time} {department} 예약 가능합니다. 이 시간 괜찮으세요?",
            f"확인해보니 {date} {final_time} 가능합니다. 이 시간 괜찮으세요?",
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
            f"예약 완료됐습니다. {date} {final_time}에 {department}로 방문해주시면 됩니다.",
            f"{date} {final_time} {department} 진료로 예약 완료됐습니다.",
        ]
        return choose_message(candidates, state)
    

    if conversation_state == "closing":
        candidates = [
            "더 궁금한 점 없으시면 통화 마무리하겠습니다.",
            "다른 문의 없으시면 여기서 마무리하겠습니다.",
            "다른 문의 없으시면 통화 마무리하겠습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "END":
        candidates = [
            "감사합니다. 좋은 하루 보내세요.",
            "감사합니다. 편안한 하루 보내세요.",
            "문의해주셔서 감사합니다. 좋은 하루 되세요.",
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
            "시간은 몇 시쯤 괜찮으세요?",
            f"{date} 예약으로 확인했습니다. 시간은 몇 시쯤 괜찮으세요?",
            f"{date} 방문 예정이시죠. 편하신 시간대가 있으세요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "confirming_info":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"{date} {final_time} {department} 진료 맞으실까요?",
            f"{date} {final_time}, {department}로 예약 도와드릴까요?",
            f"{date} {final_time} {department} 진료로 확인했습니다. 맞으실까요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "checking_availability":
        candidates = [
            "잠시만요. 예약 가능한지 확인해볼게요.",
            "예약 가능한지 확인해보겠습니다. 잠시만 기다려주세요.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_available":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"{date} {final_time} {department} 예약 가능합니다. 이 시간 괜찮으세요?",
            f"확인해보니 {date} {final_time} 가능합니다. 이 시간 괜찮으세요?",
        ]
        return choose_message(candidates, state)

    if conversation_state == "reservation_confirmed":
        final_time = resolve_final_reservation_time(state) or time
        candidates = [
            f"예약 완료됐습니다. {date} {final_time}에 {department}로 방문해주시면 됩니다.",
            f"{date} {final_time} {department} 진료로 예약 완료됐습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "closing":
        candidates = [
            "더 궁금한 점 없으시면 통화 마무리하겠습니다.",
            "다른 문의 없으시면 여기서 마무리하겠습니다.",
            "다른 문의 없으시면 통화 마무리하겠습니다.",
        ]
        return choose_message(candidates, state)

    if conversation_state == "END":
        candidates = [
            "감사합니다. 좋은 하루 보내세요.",
            "감사합니다. 편안한 하루 보내세요.",
            "문의해주셔서 감사합니다. 좋은 하루 되세요.",
        ]
        return choose_message(candidates, state)

    return fallback_ai_message(conversation_state, state)
