from __future__ import annotations

from typing import Dict, List

from langgraph.graph import StateGraph, START, END
from services.flow.reservation.hospital.state import HospitalReservationState
from services.flow.reservation.hospital.templates import (
    build_template_ai_message,
    fallback_ai_message,
)
from services.flow.reservation.hospital.policy import (
    route_after_decide,
    should_use_template_first,
)
from services.flow.reservation.hospital.nodes import (
    attach_recommended_replies_node,
    check_availability_node,
    decide_next_state_node,
    extract_info_node,
    parse_user_action_node,
)

from services.flow.reservation.hospital.llm_client import complete_hospital_ai_message
from services.flow.reservation.hospital.validator import validate_hospital_reservation_message
from services.flow.reservation.common.time_utils import (
    resolve_final_reservation_time,
    format_time_options,
)


    


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

    raw_ai_message = complete_hospital_ai_message(
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

    retry_raw_ai_message = complete_hospital_ai_message(
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
