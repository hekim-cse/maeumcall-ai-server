from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Any, Callable, Dict, FrozenSet, Mapping, Optional, Protocol, Set

from schemas.chat_models import ChatRequest, ChatResponse
from services.flow.common.scenario_keys import canonicalize_scenario_label
from core.observability import record_contract_failure


SCENARIO_STATE_VERSION = 2


class ScenarioStateContractError(ValueError):
    def __init__(self, code: str, public_message: str, *, status_code: int = 422):
        super().__init__(public_message)
        record_contract_failure("scenario_state", code)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


class CompiledGraph(Protocol):
    def invoke(self, input: Mapping[str, Any], *args: Any, **kwargs: Any) -> Dict[str, Any]: ...


CompactState = Callable[[Dict[str, Any]], Dict[str, Any]]
ValidateState = Callable[[Dict[str, Any]], None]


def build_scenario_key(category: str, title: str) -> str:
    return (
        f"{canonicalize_scenario_label(category)}:"
        f"{canonicalize_scenario_label(title)}"
    )


def validate_client_state(
    req: ChatRequest,
    *,
    category: str,
    title: str,
    allowed_fields: Set[str],
    allowed_conversation_states: AbstractSet[str],
) -> Dict[str, Any]:
    raw = dict(req.scenarioState or {})
    embedded_conversation_state = raw.get("conversation_state")
    for conversation_state in (req.conversationState, embedded_conversation_state):
        if (
            conversation_state is not None
            and conversation_state not in allowed_conversation_states
        ):
            raise ScenarioStateContractError(
                "CONVERSATION_STATE_INVALID",
                "현재 시나리오에서 허용되지 않는 대화 상태입니다.",
            )

    if embedded_conversation_state == "END" or req.conversationState == "END":
        raise ScenarioStateContractError(
            "CONVERSATION_ALREADY_ENDED",
            "이미 종료된 통화에는 새 메시지를 보낼 수 없습니다.",
            status_code=409,
        )

    if not raw:
        return {}

    expected_key = build_scenario_key(category, title)
    actual_key = raw.get("scenario_key")
    if actual_key != expected_key:
        raise ScenarioStateContractError(
            "SCENARIO_STATE_MISMATCH",
            "현재 시나리오와 전달된 상태가 일치하지 않습니다. 통화를 다시 시작해 주세요.",
        )

    version = raw.get("state_version")
    if version != SCENARIO_STATE_VERSION:
        raise ScenarioStateContractError(
            "SCENARIO_STATE_VERSION_UNSUPPORTED",
            "지원하지 않는 대화 상태 버전입니다. 통화를 다시 시작해 주세요.",
        )

    metadata_fields = {"scenario_key", "state_version"}
    unknown_fields = set(raw) - allowed_fields - metadata_fields
    if unknown_fields:
        raise ScenarioStateContractError(
            "SCENARIO_STATE_INVALID",
            "대화 상태에 허용되지 않은 필드가 포함되어 있습니다.",
        )

    state = {key: value for key, value in raw.items() if key in allowed_fields}
    embedded_conversation_state = state.get("conversation_state")
    if (
        req.conversationState is not None
        and embedded_conversation_state is not None
        and req.conversationState != embedded_conversation_state
    ):
        raise ScenarioStateContractError(
            "CONVERSATION_STATE_MISMATCH",
            "conversationState와 scenarioState의 대화 상태가 일치하지 않습니다.",
        )

    return state


def envelope_state(
    state: Dict[str, Any],
    *,
    category: str,
    title: str,
) -> Dict[str, Any]:
    return {
        "scenario_key": build_scenario_key(category, title),
        "state_version": SCENARIO_STATE_VERSION,
        **state,
    }


@dataclass(frozen=True)
class DetailedGraphContract:
    category: str
    title: str
    graph: CompiledGraph
    compact_state: CompactState
    defaults: Mapping[str, Any]
    allowed_conversation_states: FrozenSet[str]
    initial_conversation_state: str = "greeting"
    validate_state: Optional[ValidateState] = None

    @property
    def allowed_state_fields(self) -> Set[str]:
        return set(self.compact_state({}))


def complete_detailed_graph(
    req: ChatRequest,
    contract: DetailedGraphContract,
) -> ChatResponse:
    previous_state = validate_client_state(
        req,
        category=contract.category,
        title=contract.title,
        allowed_fields=contract.allowed_state_fields,
        allowed_conversation_states=contract.allowed_conversation_states,
    )
    if contract.validate_state is not None:
        contract.validate_state(previous_state)
    conversation_state = (
        req.conversationState
        or previous_state.get("conversation_state")
        or contract.initial_conversation_state
    )
    initial_state: Dict[str, Any] = {
        **previous_state,
        **{
            key: previous_state.get(key) or value
            for key, value in contract.defaults.items()
        },
        "user_message": req.userMessage,
        "conversation_state": conversation_state,
        "history": req.serialized_history(),
        "recommended_replies": [],
        "should_end_call": False,
    }

    result = contract.graph.invoke(initial_state)
    compacted = contract.compact_state(result)
    return ChatResponse(
        response=result["ai_message"],
        etiquetteTip=None,
        recommendedReplies=result["recommended_replies"],
        conversationState=result["conversation_state"],
        shouldEndCall=result["should_end_call"],
        scenarioState=envelope_state(
            compacted,
            category=contract.category,
            title=contract.title,
        ),
    )
