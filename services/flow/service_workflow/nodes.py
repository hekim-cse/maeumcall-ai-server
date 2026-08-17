from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from services.flow.service_workflow.contracts import ServiceWorkflowSpec
from services.flow.service_workflow.state import ServiceWorkflowState
from services.flow.service_workflow.structured import analyze_service_workflow_message


Node = Callable[[ServiceWorkflowState], Dict[str, Any]]


def build_extract_node(spec: ServiceWorkflowSpec) -> Node:
    def extract(state: ServiceWorkflowState) -> Dict[str, Any]:
        current_fields = _normalized_fields(spec, state.get("fields"))
        analyzed = analyze_service_workflow_message(
            spec,
            conversation_state=state.get("conversation_state") or "greeting",
            current_fields=current_fields,
            user_message=state.get("user_message") or "",
        )
        next_fields = dict(current_fields)
        for key, value in analyzed["fields"].items():
            if value is not None:
                next_fields[key] = value

        change_field = analyzed["change_field"]
        if analyzed["user_action"] == "change_detail" and change_field is not None:
            if analyzed["fields"][change_field] is None:
                next_fields[change_field] = None

        return {
            "intent": spec.intent,
            "fields": next_fields,
            "user_action": analyzed["user_action"],
            "change_field": change_field,
            "last_ai_message": state.get("last_ai_message"),
            "history": state.get("history") or [],
            "recommended_replies": [],
            "should_end_call": False,
        }

    return extract


def build_decide_node(spec: ServiceWorkflowSpec) -> Node:
    def decide(state: ServiceWorkflowState) -> Dict[str, Any]:
        current_state = state.get("conversation_state") or "greeting"
        user_action = state.get("user_action") or "unknown"
        fields = _normalized_fields(spec, state.get("fields"))
        missing_fields = [key for key in spec.field_keys if not fields[key]]

        if user_action == "end_call":
            return {
                "conversation_state": "END",
                "missing_fields": missing_fields,
                "should_end_call": True,
            }
        if user_action == "cancel_workflow":
            return {
                "conversation_state": "cancelled",
                "workflow_status": "cancelled",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }
        if current_state == "cancelled":
            return _close_or_stay(user_action, "cancelled", missing_fields)
        if current_state == "closing":
            return {
                "conversation_state": "closing",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }

        current_guard = spec.guard_for_state(current_state)
        if current_guard is not None:
            if user_action == "go_closing":
                return {
                    "conversation_state": "closing",
                    "missing_fields": missing_fields,
                    "should_end_call": False,
                }
            if user_action == "change_detail":
                next_guard = spec.matching_guard(fields)
                if next_guard is not None:
                    return {
                        "conversation_state": next_guard.state,
                        "workflow_status": "blocked",
                        "missing_fields": missing_fields,
                        "should_end_call": False,
                    }
                next_state = spec.collecting_state if missing_fields else spec.confirming_state
                return {
                    "conversation_state": next_state,
                    "workflow_status": "in_progress",
                    "missing_fields": missing_fields,
                    "should_end_call": False,
                }
            return {
                "conversation_state": current_guard.state,
                "workflow_status": "blocked",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }

        matching_guard = spec.matching_guard(fields)
        if matching_guard is not None:
            return {
                "conversation_state": matching_guard.state,
                "workflow_status": "blocked",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }

        if user_action == "change_detail":
            next_state = spec.collecting_state if missing_fields else spec.confirming_state
            return {
                "conversation_state": next_state,
                "workflow_status": "in_progress",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }

        if current_state == spec.confirming_state:
            if user_action == "confirm_details" and not missing_fields:
                return {
                    "conversation_state": spec.ready_state,
                    "workflow_status": "ready",
                    "missing_fields": [],
                    "should_end_call": False,
                }
            return {
                "conversation_state": spec.confirming_state,
                "workflow_status": "in_progress",
                "missing_fields": missing_fields,
                "should_end_call": False,
            }

        if current_state == spec.ready_state:
            return _close_or_stay(user_action, spec.ready_state, missing_fields, ready=True)

        next_state = spec.collecting_state if missing_fields else spec.confirming_state
        return {
            "conversation_state": next_state,
            "workflow_status": "in_progress",
            "missing_fields": missing_fields,
            "should_end_call": False,
        }

    return decide


def build_response_node(spec: ServiceWorkflowSpec) -> Node:
    def generate(state: ServiceWorkflowState) -> Dict[str, Any]:
        conversation_state = state.get("conversation_state") or spec.collecting_state
        fields = _normalized_fields(spec, state.get("fields"))
        missing_fields = state.get("missing_fields") or []

        if conversation_state == spec.collecting_state:
            missing_key = missing_fields[0] if missing_fields else spec.field_keys[0]
            message = _field(spec, missing_key).question
        elif conversation_state == spec.confirming_state:
            summary = _field_summary(spec, fields)
            message = f"{spec.confirmation_prefix} {summary}. 맞습니까?"
        elif conversation_state == spec.ready_state:
            message = spec.ready_message_for(fields)
        elif conversation_state == "cancelled":
            message = spec.cancelled_message
        elif conversation_state == "closing":
            message = spec.closing_message
        elif conversation_state == "END":
            message = "네, 알겠습니다. 통화를 마치겠습니다."
        else:
            guard = spec.guard_for_state(conversation_state)
            if guard is None:
                raise ValueError(f"unsupported workflow state: {conversation_state}")
            message = guard.message
        return {"ai_message": message, "last_ai_message": message}

    return generate


def build_replies_node(spec: ServiceWorkflowSpec) -> Node:
    def attach(state: ServiceWorkflowState) -> Dict[str, Any]:
        conversation_state = state.get("conversation_state") or spec.collecting_state
        missing_fields = state.get("missing_fields") or []
        if conversation_state == spec.collecting_state:
            missing_key = missing_fields[0] if missing_fields else spec.field_keys[0]
            replies = list(_field(spec, missing_key).replies)
        elif conversation_state == spec.confirming_state:
            replies = ["네, 맞습니다.", "수정할 내용이 있습니다.", "진행을 취소하겠습니다."]
        elif conversation_state == spec.ready_state:
            replies = list(spec.ready_replies)
        elif conversation_state == "cancelled":
            replies = ["네, 통화를 마치겠습니다."]
        elif conversation_state == "closing":
            replies = ["네, 감사합니다."]
        else:
            guard = spec.guard_for_state(conversation_state)
            replies = list(guard.replies) if guard is not None else []
        return {"recommended_replies": replies}

    return attach


def _normalized_fields(
    spec: ServiceWorkflowSpec,
    raw_fields: Optional[Dict[str, Optional[str]]],
) -> Dict[str, Optional[str]]:
    source = raw_fields or {}
    return {key: source.get(key) for key in spec.field_keys}


def _field(spec: ServiceWorkflowSpec, key: str):
    return next(field for field in spec.fields if field.key == key)


def _field_summary(spec: ServiceWorkflowSpec, fields: Dict[str, Optional[str]]) -> str:
    return ", ".join(
        f"{field.label}: {field.display_value(fields[field.key])}"
        for field in spec.fields
    )


def _close_or_stay(
    user_action: str,
    current_state: str,
    missing_fields: List[str],
    *,
    ready: bool = False,
) -> Dict[str, Any]:
    if user_action == "go_closing":
        return {
            "conversation_state": "closing",
            "missing_fields": missing_fields,
            "should_end_call": False,
        }
    return {
        "conversation_state": current_state,
        "workflow_status": "ready" if ready else "cancelled",
        "missing_fields": missing_fields,
        "should_end_call": False,
    }
