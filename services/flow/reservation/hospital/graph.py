from __future__ import annotations

from typing import Dict

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
from services.flow.reservation.hospital.generation import (
    build_ai_message_prompt,
    build_retry_prompt,
    clean_ai_message,
)
from services.flow.reservation.hospital.validator import validate_hospital_reservation_message


    


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
