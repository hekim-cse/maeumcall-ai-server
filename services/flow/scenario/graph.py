from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from llm.client import complete_json_messages
from llm.prompt_builder import generate_prompts
from llm.structured_output import allowed_string, complete_validated_json, optional_string
from schemas.chat_models import ChatRequest
from services.flow.scenario.registry import get_scenario_config
from services.flow.scenario.state import ScenarioConversationState


def _conversation_messages(turns: Any) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    for turn in turns or []:
        if not isinstance(turn, dict):
            raise ValueError("history turns must be objects")
        role = turn.get("role")
        text = turn.get("text")
        if role not in {"user", "assistant"}:
            raise ValueError("history role must be user or assistant")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("history text must be a non-empty string")
        messages.append({"role": role, "content": text.strip()})
    return messages


def _validate_turn_result(data: Dict[str, Any]) -> Dict[str, Any]:
    action = allowed_string(data, "action", {"continue", "end"})
    response = optional_string(data, "response")
    if not response:
        raise ValueError("response must be a non-empty string")
    etiquette_tip = optional_string(data, "etiquette_tip")
    return {
        "action": action,
        "response": response,
        "etiquette_tip": etiquette_tip,
    }


def prepare_turn_node(state: ScenarioConversationState) -> Dict[str, Any]:
    try:
        previous_turn_count = max(0, int(state.get("turn_count") or 0))
    except (TypeError, ValueError):
        raise ValueError("turn_count must be a non-negative integer")
    return {"turn_count": previous_turn_count + 1}


def generate_turn_node(state: ScenarioConversationState) -> Dict[str, Any]:
    category = state.get("category") or ""
    title = state.get("title") or ""
    config = get_scenario_config(category, title)
    if config is None:
        raise ValueError("scenario configuration is required")

    payload = dict(state.get("request_payload") or {})
    request = ChatRequest(**payload)
    system_prompt, user_prompt = generate_prompts(request)
    history = _conversation_messages(state.get("history"))

    contract = (
        "반드시 다음 JSON 객체 하나만 출력한다: "
        '{"action":"continue"|"end","response":string,"etiquette_tip":string|null}. '
        "사용자가 명확히 통화를 끝내려는 경우에만 action=end로 한다. "
        "response는 현재 역할과 시나리오에 맞는 상대방의 다음 발화 한 번이다. "
        "교수님/회사 상황에서 초반 자기소개나 용건 전달이 부족할 때만 etiquette_tip을 작성하고, "
        "그 외에는 null로 한다. 설명, markdown, 코드블록은 출력하지 않는다. "
        f"톤 참고 예시: {config.response_example}"
    )
    messages = [{"role": "system", "content": f"{system_prompt}\n\n{contract}"}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    result = complete_validated_json(
        messages,
        completion=complete_json_messages,
        validator=_validate_turn_result,
    )
    should_end = result["action"] == "end"
    return {
        "conversation_state": "END" if should_end else "active",
        "should_end_call": should_end,
        "ai_message": result["response"],
        "last_ai_message": result["response"],
        "etiquette_tip": result["etiquette_tip"],
    }


def attach_replies_node(state: ScenarioConversationState) -> Dict[str, Any]:
    if state.get("should_end_call"):
        return {"recommended_replies": []}
    config = get_scenario_config(state.get("category") or "", state.get("title") or "")
    if config is None:
        raise ValueError("scenario configuration is required")
    return {"recommended_replies": list(config.recommended_replies)}


def build_scenario_conversation_graph():
    builder = StateGraph(ScenarioConversationState)
    builder.add_node("prepare_turn", prepare_turn_node)
    builder.add_node("generate_turn", generate_turn_node)
    builder.add_node("attach_replies", attach_replies_node)
    builder.add_edge(START, "prepare_turn")
    builder.add_edge("prepare_turn", "generate_turn")
    builder.add_edge("generate_turn", "attach_replies")
    builder.add_edge("attach_replies", END)
    return builder.compile()


scenario_conversation_graph = build_scenario_conversation_graph()
