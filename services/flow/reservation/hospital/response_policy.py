from __future__ import annotations

from services.flow.reservation.common.time_utils import (
    format_time_options,
    resolve_final_reservation_time,
)


def _select_policy_message(candidates: list[str], state: dict) -> str:
    if not candidates:
        raise ValueError("response policy requires at least one candidate")
    previous = state.get("last_ai_message")
    return next((message for message in candidates if message != previous), candidates[0])


def _with_service_greeting(message: str, state: dict) -> str:
    if state.get("history") or state.get("last_ai_message"):
        return message
    service_name = state.get("service_name") or "마음병원"
    return f"네, {service_name}입니다. {message}"


def build_hospital_response(conversation_state: str, state: dict = None) -> str:
    """Build a deterministic response from validated reservation state.

    This is a product response policy, not an LLM failure recovery path.
    Unknown states fail explicitly instead of producing a generic sentence.
    """
    state = state or {}
    department = state.get("department") or "선택하신 진료과"
    date = state.get("date") or "원하시는 날짜"
    time = state.get("time") or "원하시는 시간대"
    final_time = resolve_final_reservation_time(state) or time
    user_name = state.get("user_name") or "예약자"

    if conversation_state in {"asking_purpose", "asking_department"}:
        if date != "원하시는 날짜" and time != "원하시는 시간대":
            candidates = [
                f"{date} {time}로 확인했습니다. 어느 과로 진료 보실까요?",
                f"{date} {time}에 어느 과로 진료 보실까요?",
            ]
            return _select_policy_message(candidates, state)
        message = _select_policy_message(
            ["예약 도와드릴게요. 어느 과로 진료 보실까요?", "어느 과로 예약 도와드릴까요?"],
            state,
        )
        return _with_service_greeting(message, state)

    if conversation_state == "asking_date":
        return _select_policy_message(
            [
                f"{department} 진료 예약이시죠. 날짜는 언제가 괜찮으세요?",
                "예약 날짜는 언제가 괜찮으세요?",
            ],
            state,
        )

    if conversation_state == "asking_time":
        return _select_policy_message(
            [
                f"{date} 예약으로 확인했습니다. 원하시는 시간대를 말씀해주시겠어요?",
                f"{date} 중 편하신 시간대가 있으실까요?",
            ],
            state,
        )

    if conversation_state == "asking_user_name":
        return _select_policy_message(
            [
                f"{date} {time} {department} 예약으로 확인했습니다. 예약자 성함을 말씀해주시겠어요?",
                "예약하시는 분의 성함을 말씀해주시겠어요?",
            ],
            state,
        )

    if conversation_state == "confirming_info":
        return _select_policy_message(
            [
                f"{date} {final_time} {department} 진료 예약을 원하시는 것이 맞으실까요?",
                f"{user_name}님, {date} {final_time} {department} 진료 예약으로 확인해도 될까요?",
            ],
            state,
        )

    if conversation_state == "checking_availability":
        return _select_policy_message(
            [
                "예약 가능한지 확인해보겠습니다. 잠시만 기다려주세요.",
                "잠시만요. 예약 가능한지 확인해볼게요.",
            ],
            state,
        )

    if conversation_state == "reservation_available":
        return _select_policy_message(
            [
                f"{date} {final_time} {department} 예약 가능합니다. 이 시간 괜찮으세요?",
                f"확인해보니 {date} {final_time} 가능합니다. 이 시간으로 진행할까요?",
            ],
            state,
        )

    if conversation_state in {"reservation_unavailable", "suggest_alternative"}:
        alternatives = state.get("alternative_times") or []
        if not alternatives:
            return _select_policy_message(
                [
                    f"{date} {time}에는 예약이 어렵습니다. 다른 날짜나 시간을 말씀해주시겠어요?",
                    "현재 예약 가능한 대안 시간이 없습니다. 원하시는 다른 날짜나 시간을 말씀해주시겠어요?",
                ],
                state,
            )
        options = format_time_options(alternatives)
        if conversation_state == "reservation_unavailable":
            return _select_policy_message(
                [
                    f"요청하신 {date} {time} 예약은 어렵습니다. 대신 {options} 중 가능한 시간이 있으실까요?",
                    f"요청하신 {date} 시간대는 마감되었습니다. {options} 중에서 선택해주시겠어요?",
                ],
                state,
            )
        return _select_policy_message(
            [
                f"가능한 대안 시간은 {options}입니다. 어떤 시간이 괜찮으실까요?",
                f"현재 안내 가능한 시간은 {options}입니다. 이 중에서 선택해주시겠어요?",
            ],
            state,
        )

    if conversation_state == "reservation_confirmed":
        return _select_policy_message(
            [
                f"{date} {final_time} {department} 진료로 예약 완료됐습니다.",
                f"예약 완료됐습니다. {date} {final_time}에 {department}로 방문해주시면 됩니다.",
            ],
            state,
        )

    if conversation_state == "closing":
        return _select_policy_message(
            [
                "다른 문의 없으시면 통화 마무리하겠습니다.",
                "더 궁금한 점 없으시면 여기서 마무리하겠습니다.",
            ],
            state,
        )

    if conversation_state == "END":
        return _select_policy_message(
            ["감사합니다. 좋은 하루 보내세요.", "문의해주셔서 감사합니다. 편안한 하루 보내세요."],
            state,
        )

    raise ValueError(f"unsupported hospital conversation state: {conversation_state}")
