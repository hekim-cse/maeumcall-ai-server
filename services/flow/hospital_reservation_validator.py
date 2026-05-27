from __future__ import annotations

from typing import Dict, Any

from services.flow.reservation_time_utils import is_time_in_options


def validate_hospital_reservation_message(text: str, state: Dict[str, Any]) -> bool:
    """
    병원 예약 시나리오에서 LLM이 생성한 응답이 현재 상태에 맞는지 검증한다.

    True:
    - LLM 응답을 그대로 사용한다.

    False:
    - retry 또는 fallback으로 넘어간다.
    """
    text = (text or "").strip()

    if not text:
        return False

    conversation_state = state.get("conversation_state") or "asking_purpose"

    global_banned_phrases = [
        "바로 안내해드리겠습니다",
        "정상적으로 잡혀",
    ]

    if _contains_any(text, global_banned_phrases):
        return False

    validators = {
        "asking_department": _validate_asking_department,
        "asking_date": _validate_asking_date,
        "asking_time": _validate_asking_time,
        "confirming_info": _validate_confirming_info,
        "checking_availability": _validate_checking_availability,
        "reservation_available": _validate_reservation_available,
        "reservation_unavailable": _validate_reservation_unavailable,
        "suggest_alternative": _validate_suggest_alternative,
        "reservation_confirmed": _validate_reservation_confirmed,
        "closing": _validate_closing,
        "END": _validate_end,
    }

    validator = validators.get(conversation_state)

    if validator is None:
        return True

    return validator(text, state)


def _validate_asking_department(text: str, state: Dict[str, Any]) -> bool:
    has_department_question = _contains_any(text, [
        "진료과",
        "과를",
        "어느 과",
        "무슨 과",
        "진료받으실 과",
    ])

    asks_wrong_info = _contains_any(text, [
        "날짜",
        "요일",
        "시간대",
        "몇 시",
        "연락처",
        "성함",
    ])

    too_verbose = _contains_any(text, [
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


def _validate_asking_date(text: str, state: Dict[str, Any]) -> bool:
    has_date_question = _contains_any(text, [
        "날짜",
        "언제",
        "요일",
        "방문",
    ])

    asks_wrong_info = _contains_any(text, [
        "진료과",
        "어느 과",
        "시간대",
        "몇 시",
        "연락처",
        "성함",
    ])

    return has_date_question and not asks_wrong_info


def _validate_asking_time(text: str, state: Dict[str, Any]) -> bool:
    has_time_question = _contains_any(text, [
        "시간",
        "시간대",
        "몇 시",
        "오전",
        "오후",
    ])

    asks_wrong_info = _contains_any(text, [
        "진료과",
        "어느 과",
        "날짜",
        "요일",
        "연락처",
        "성함",
    ])

    return has_time_question and not asks_wrong_info


def _validate_confirming_info(text: str, state: Dict[str, Any]) -> bool:
    department = state.get("department")
    date = state.get("date")
    time = state.get("time")

    has_confirm_question = _contains_any(text, [
        "맞으실까요",
        "맞을까요",
        "맞습니까",
        "맞으신가요",
        "확인하면 될까요",
        "확인해도 될까요",
        "확인해드려도 될까요",
    ])

    asks_new_info = _contains_any(text, [
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

    invalid_confirming_phrases = [
        "예약 가능합니다",
        "예약이 가능합니다",
        "예약해드리겠습니다",
        "예약되었습니다",
        "예약 완료",
        "예약이 완료",
        "예약이 확인",
        "가능합니다",
        "가능하십니다",
    ]

    if _contains_any(text, invalid_confirming_phrases):
        return False

    has_saved_info = True

    if department and department not in text:
        has_saved_info = False

    if date and date not in text:
        has_saved_info = False

    if time and time not in text:
        has_saved_info = False

    has_reservation_word = "예약" in text

    return (
        has_confirm_question
        and has_saved_info
        and has_reservation_word
        and not asks_new_info
    )


def _validate_checking_availability(text: str, state: Dict[str, Any]) -> bool:
    has_checking_expression = _contains_any(text, [
        "확인해보겠습니다",
        "확인하겠습니다",
        "잠시만",
        "기다려",
    ])

    says_result_too_early = _contains_any(text, [
        "예약 가능합니다",
        "예약이 어렵습니다",
        "예약이 완료되었습니다",
        "예약되었습니다",
    ])

    return has_checking_expression and not says_result_too_early


def _validate_reservation_available(text: str, state: Dict[str, Any]) -> bool:
    has_available_expression = _contains_any(text, [
        "예약이 가능합니다",
        "예약 가능합니다",
        "가능합니다",
    ])

    asks_confirmation = _contains_any(text, [
        "진행",
        "괜찮으실까요",
        "도와드릴까요",
        "예약할까요",
        "해드릴까요",
        "이 시간으로",
        "원하실까요",
    ])

    return has_available_expression and asks_confirmation


def _validate_reservation_unavailable(text: str, state: Dict[str, Any]) -> bool:
    has_unavailable_expression = _contains_any(text, [
        "예약이 어렵",
        "예약이 모두 차",
        "예약은 모두 차",
        "예약은 어렵",
        "어렵습니다",
        "불가능",
    ])

    has_alternative_expression = _contains_any(text, [
        "대신",
        "다른 시간",
        "가능한 시간",
        "괜찮으실까요",
        "시간대",
    ])
    
    incomplete_ending = text.endswith((
        "도",
        "은",
        "는",
        "가",
        "이",
        "을",
        "를",
        "하나",
        "가능하나",
        "해당 시간도",
    ))

    if incomplete_ending:
        return False
    

    return has_unavailable_expression and has_alternative_expression


def _validate_suggest_alternative(text: str, state: Dict[str, Any]) -> bool:
    alternative_times = state.get("alternative_times") or []

    mentions_alternative_time = any(
        alternative_time in text
        for alternative_time in alternative_times
    )

    has_choice_expression = _contains_any(text, [
        "선택",
        "말씀",
        "알려",
        "괜찮",
        "원하시는 시간",
        "가능한 시간",
        "시간",
    ])

    ambiguous_or_invalid_expression = _contains_any(text, [
        "외에도",
        "그 시간도",
        "해당 시간도",
        "가능하나",
    ])

    if ambiguous_or_invalid_expression:
        return False

    return mentions_alternative_time and has_choice_expression


def _validate_reservation_confirmed(text: str, state: Dict[str, Any]) -> bool:
    has_confirmed_expression = _contains_any(text, [
        "예약이 완료",
        "예약되었습니다",
        "예약 완료",
        "완료되었습니다",
        "예약으로 완료",
    ])

    selected_time = state.get("selected_time")
    alternative_times = state.get("alternative_times") or []

    # 대안 시간 선택 후 예약 완료 상태라면,
    # 선택한 시간이 대안 시간 목록 안에 있어야 한다.
    if selected_time and alternative_times:
        if not is_time_in_options(selected_time, alternative_times):
            return False

    return has_confirmed_expression


def _validate_closing(text: str, state: Dict[str, Any]) -> bool:
    has_closing_expression = _contains_any(text, [
        "궁금하신 점",
        "문의",
        "마무리",
        "감사",
        "좋은 하루",
    ])

    too_verbose_or_reconfirm = _contains_any(text, [
        "정상적으로 접수",
        "예약이 완료",
        "예약되었습니다",
        "도움이 필요하시면 언제든",
    ])

    return has_closing_expression and not too_verbose_or_reconfirm


def _validate_end(text: str, state: Dict[str, Any]) -> bool:
    return _contains_any(text, [
        "감사합니다",
        "좋은 하루",
        "편안한 하루",
    ])


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)