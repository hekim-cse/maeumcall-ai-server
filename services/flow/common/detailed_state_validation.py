from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Tuple

from services.flow.common.state_contract import ScenarioStateContractError


MAX_STATE_TEXT_LENGTH = 1_000
MAX_AI_MESSAGE_LENGTH = 4_000
MAX_ALTERNATIVE_TIMES = 20


@dataclass(frozen=True)
class ReservationStateContract:
    identity_field: str
    required_fields: Tuple[str, ...]
    allowed_actions: FrozenSet[str]
    information_complete_states: FrozenSet[str]
    allowed_intents: FrozenSet[str | None] = frozenset({"reservation"})

    @property
    def expected_fields(self) -> FrozenSet[str]:
        return frozenset(
            {
                "intent",
                self.identity_field,
                *self.required_fields,
                "conversation_state",
                "last_ai_message",
                "user_action",
                "selected_time",
                "availability_status",
                "availability_reason",
                "available_time",
                "alternative_times",
                "availability_message_hint",
                "reservation_confirmed",
            }
        )

    def validate(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if set(state) != set(self.expected_fields):
            _invalid_state()
        if state.get("intent") not in self.allowed_intents:
            _invalid_state()

        text_fields = self.expected_fields - {
            "intent",
            "alternative_times",
            "reservation_confirmed",
        }
        for field in text_fields:
            _validate_optional_text(
                state.get(field),
                max_length=(
                    MAX_AI_MESSAGE_LENGTH
                    if field == "last_ai_message"
                    else MAX_STATE_TEXT_LENGTH
                ),
            )

        if state.get(self.identity_field) is None:
            _invalid_state()
        if state.get("conversation_state") is None:
            _invalid_state()
        if state.get("user_action") not in self.allowed_actions:
            _invalid_state()

        alternatives = state.get("alternative_times")
        if not isinstance(alternatives, list) or len(alternatives) > MAX_ALTERNATIVE_TIMES:
            _invalid_state()
        for alternative in alternatives:
            _validate_optional_text(alternative, allow_none=False)
        if len(alternatives) != len(set(alternatives)):
            _invalid_state()

        confirmed = state.get("reservation_confirmed")
        if confirmed is not None and not isinstance(confirmed, bool):
            _invalid_state()

        availability_status = state.get("availability_status")
        if availability_status not in {None, "available", "unavailable"}:
            _invalid_state()
        if availability_status is None:
            if (
                state.get("availability_reason") is not None
                or state.get("available_time") is not None
                or alternatives
            ):
                _invalid_state()
        elif availability_status == "available":
            if state.get("available_time") is None or state.get("availability_reason") is not None:
                _invalid_state()
        elif state.get("available_time") is not None or state.get("availability_reason") is None:
            _invalid_state()

        conversation_state = state["conversation_state"]
        if conversation_state in self.information_complete_states and any(
            state.get(field) is None for field in self.required_fields
        ):
            _invalid_state()
        if conversation_state == "reservation_available" and availability_status != "available":
            _invalid_state()
        if (
            conversation_state
            in {"reservation_unavailable", "suggest_alternative"}
            and availability_status != "unavailable"
        ):
            _invalid_state()
        if conversation_state == "reservation_confirmed" and (
            confirmed is not True or state.get("selected_time") is None
        ):
            _invalid_state()
        if confirmed is True and conversation_state not in {
            "reservation_confirmed",
            "closing",
            "END",
        }:
            _invalid_state()


@dataclass(frozen=True)
class ProfessorStateContract:
    intent: str
    required_fields: Tuple[str, ...]
    allowed_actions: FrozenSet[str]
    information_complete_states: FrozenSet[str]

    @property
    def expected_fields(self) -> FrozenSet[str]:
        return frozenset(
            {
                "intent",
                "professor_name",
                *self.required_fields,
                "conversation_state",
                "missing_fields",
                "last_ai_message",
                "user_action",
            }
        )

    def validate(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if set(state) != set(self.expected_fields) or state.get("intent") != self.intent:
            _invalid_state()

        for field in self.expected_fields - {"intent", "missing_fields"}:
            _validate_optional_text(
                state.get(field),
                max_length=(
                    MAX_AI_MESSAGE_LENGTH
                    if field == "last_ai_message"
                    else MAX_STATE_TEXT_LENGTH
                ),
            )
        if state.get("professor_name") is None or state.get("conversation_state") is None:
            _invalid_state()
        if state.get("user_action") not in self.allowed_actions:
            _invalid_state()

        missing_fields = state.get("missing_fields")
        actual_missing = [
            field for field in self.required_fields if state.get(field) is None
        ]
        if not isinstance(missing_fields, list):
            _invalid_state()
        if any(field not in self.required_fields for field in missing_fields):
            _invalid_state()
        if len(missing_fields) != len(set(missing_fields)) or missing_fields != actual_missing:
            _invalid_state()
        if (
            state["conversation_state"] in self.information_complete_states
            and actual_missing
        ):
            _invalid_state()


def _validate_optional_text(
    value: Any,
    *,
    allow_none: bool = True,
    max_length: int = MAX_STATE_TEXT_LENGTH,
) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        _invalid_state()


def _invalid_state() -> None:
    raise ScenarioStateContractError(
        "SCENARIO_STATE_INVALID",
        "대화 상태의 업무 필드 계약이 올바르지 않습니다.",
    )
