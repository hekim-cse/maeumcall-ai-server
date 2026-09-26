from __future__ import annotations

import json
import unicodedata
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.semantics import OBJECTIVE_DIFFICULTY_TAGS_V1, DifficultyTag
from services.flow.common.state_contract import SCENARIO_STATE_VERSION


class DatasetSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    TEST = "test"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ADJUDICATED = "adjudicated"


NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000, pattern=r"\S"),
]
NonEmptyUserMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000, pattern=r"\S"),
]
STRUCTURED_NLU_DATASET_VERSION = 2


class ExpectedField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_values: tuple[NonEmptyText, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def accepted_values_are_unique(self) -> ExpectedField:
        if len(set(self.accepted_values)) != len(self.accepted_values):
            raise ValueError("accepted_values must be unique")
        return self


class GoldLabels(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: NonEmptyText | None
    fields: dict[str, ExpectedField | None]
    user_action: NonEmptyText
    change_field: NonEmptyText | None


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]
    conversation_group_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$"),
    ]
    split: DatasetSplit
    scenario_key: NonEmptyText
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    offered_alternative_times: tuple[NonEmptyText, ...]
    user_message: NonEmptyUserMessage
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    provenance: Literal["human_authored"]
    review_status: ReviewStatus

    @model_validator(mode="after")
    def follows_live_service_contract(self) -> EvaluationCase:
        validate_evaluation_case_semantics(
            scenario_key=self.scenario_key,
            conversation_state=self.conversation_state,
            current_fields=self.current_fields,
            offered_alternative_times=self.offered_alternative_times,
            labels=self.labels,
            tags=self.tags,
        )
        return self


def validate_evaluation_case_semantics(
    *,
    scenario_key: str,
    conversation_state: str,
    current_fields: dict[str, str | None],
    offered_alternative_times: tuple[str, ...],
    labels: GoldLabels,
    tags: tuple[DifficultyTag, ...],
) -> None:
    """Validate live NLU meaning without inventing provenance or review metadata."""
    contract = EVALUATION_CONTRACTS.get(scenario_key)
    if contract is None:
        raise ValueError(f"unknown detailed scenario: {scenario_key}")
    if conversation_state not in contract.conversation_states:
        raise ValueError(
            f"conversation_state is not allowed for {scenario_key}: {conversation_state}"
        )
    if labels.intent not in contract.allowed_intents:
        raise ValueError(f"intent must be one of {sorted(map(str, contract.allowed_intents))}")
    if set(labels.fields) != set(contract.field_names):
        raise ValueError(f"label fields must be exactly {sorted(contract.field_names)}")
    field_options = dict(contract.field_options)
    for field_name, expected in labels.fields.items():
        allowed_values = field_options.get(field_name)
        if expected is None or allowed_values is None:
            continue
        if len(expected.accepted_values) != 1:
            raise ValueError(
                f"option fields require exactly one canonical accepted value: {field_name}"
            )
        invalid_values = set(expected.accepted_values) - allowed_values
        if invalid_values:
            raise ValueError(
                f"accepted_values are not allowed for {scenario_key}: "
                f"{field_name}={sorted(invalid_values)}"
            )
    if labels.user_action not in contract.allowed_actions_for_state(conversation_state):
        raise ValueError(
            f"user_action is not allowed for {scenario_key} "
            f"in {conversation_state}: {labels.user_action}"
        )

    if len(set(offered_alternative_times)) != len(offered_alternative_times):
        raise ValueError("offered_alternative_times must be unique")
    if offered_alternative_times and conversation_state not in contract.alternative_states:
        raise ValueError(
            "offered_alternative_times are allowed only in an alternative-selection state"
        )
    normalized_gold_fields = {
        name: expected.accepted_values[0] if expected is not None else None
        for name, expected in labels.fields.items()
    }
    contract.validate_prediction(
        intent=labels.intent,
        fields=normalized_gold_fields,
        user_action=labels.user_action,
        change_field=labels.change_field,
        conversation_state=conversation_state,
        current_fields=current_fields,
        offered_alternative_times=offered_alternative_times,
    )
    selected_time = labels.fields.get("selected_time")
    if selected_time is not None:
        unoffered_values = set(selected_time.accepted_values) - set(offered_alternative_times)
        if unoffered_values:
            raise ValueError(
                "selected_time accepted_values must all be server-offered alternatives"
            )

    if contract.uses_current_fields:
        if set(current_fields) != set(contract.field_names):
            raise ValueError(f"current_fields must be exactly {sorted(contract.field_names)}")
        contract.validate_current_fields(
            conversation_state=conversation_state,
            current_fields=current_fields,
        )
        if labels.user_action == "change_detail":
            if labels.change_field not in contract.field_names:
                raise ValueError("change_field must name a workflow field")
        elif labels.change_field is not None:
            raise ValueError("change_field must be null unless user_action is change_detail")
    else:
        contract.validate_current_fields(
            conversation_state=conversation_state,
            current_fields=current_fields,
        )
        if labels.change_field is not None:
            raise ValueError("change_field is only used by service workflows")

    if len(set(tags)) != len(tags):
        raise ValueError("tags must be unique")
    _validate_tag_semantics(
        scenario_key=scenario_key,
        current_fields=current_fields,
        labels=labels,
        tags=tags,
    )


class GoldDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: Literal[STRUCTURED_NLU_DATASET_VERSION]
    state_contract_version: Literal[SCENARIO_STATE_VERSION]
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> GoldDataset:
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        splits_by_group: dict[str, set[DatasetSplit]] = {}
        for case in self.cases:
            splits_by_group.setdefault(case.conversation_group_id, set()).add(case.split)
        leaked_groups = sorted(
            group_id for group_id, splits in splits_by_group.items() if len(splits) > 1
        )
        if leaked_groups:
            raise ValueError(f"conversation groups must not cross splits: {leaked_groups}")

        cases_by_input: dict[str, list[EvaluationCase]] = {}
        for case in self.cases:
            cases_by_input.setdefault(_evaluation_input_fingerprint(case), []).append(case)
        conflicting_inputs = []
        duplicate_inputs = []
        for matching_cases in cases_by_input.values():
            if len(matching_cases) < 2:
                continue
            case_ids = tuple(sorted(item.id for item in matching_cases))
            labels = {
                json.dumps(
                    _normalize_input_value(item.labels.model_dump(mode="json")),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for item in matching_cases
            }
            if len(labels) > 1:
                conflicting_inputs.append(case_ids)
            else:
                duplicate_inputs.append(case_ids)
        if conflicting_inputs:
            raise ValueError(
                f"identical evaluation inputs have conflicting labels: {sorted(conflicting_inputs)}"
            )
        if duplicate_inputs:
            raise ValueError(
                f"duplicate evaluation inputs are not allowed: {sorted(duplicate_inputs)}"
            )
        return self


class NormalizedPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: NonEmptyText | None
    fields: dict[str, NonEmptyText | None]
    user_action: NonEmptyText
    change_field: NonEmptyText | None


class EvaluationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_valid: bool
    latency_ms: Annotated[float, Field(ge=0)]
    output: NormalizedPrediction | None = None
    error_type: NonEmptyText | None = None

    @model_validator(mode="after")
    def valid_attempt_has_output(self) -> EvaluationAttempt:
        if self.contract_valid != (self.output is not None):
            raise ValueError("contract_valid must match output presence")
        if self.contract_valid and self.error_type is not None:
            raise ValueError("valid attempt must not contain error_type")
        if not self.contract_valid and self.error_type is None:
            raise ValueError("invalid attempt must contain error_type")
        return self


class CasePrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: NonEmptyText
    attempts: tuple[EvaluationAttempt, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def stops_after_first_valid_attempt(self) -> CasePrediction:
        valid_indexes = [
            index for index, attempt in enumerate(self.attempts) if attempt.contract_valid
        ]
        if len(valid_indexes) > 1:
            raise ValueError("only one valid attempt is allowed")
        if valid_indexes and valid_indexes[0] != len(self.attempts) - 1:
            raise ValueError("evaluation must stop after the first valid attempt")
        return self

    @property
    def final_output(self) -> NormalizedPrediction | None:
        final_attempt = self.attempts[-1]
        return final_attempt.output if final_attempt.contract_valid else None


def load_gold_dataset(path: Path) -> GoldDataset:
    with path.open(encoding="utf-8") as file:
        return GoldDataset.model_validate(json.load(file))


def _evaluation_input_fingerprint(case: EvaluationCase) -> str:
    """Identify exact model inputs without trusting author-assigned group IDs."""
    payload = {
        "scenario_key": _normalize_input_value(case.scenario_key),
        "conversation_state": _normalize_input_value(case.conversation_state),
        "current_fields": _normalize_input_value(case.current_fields),
        "offered_alternative_times": _normalize_input_value(case.offered_alternative_times),
        "user_message": _normalize_input_value(case.user_message),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_input_value(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {key: _normalize_input_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_normalize_input_value(item) for item in value)
    if isinstance(value, list):
        return [_normalize_input_value(item) for item in value]
    return value


def _validate_tag_semantics(
    *,
    scenario_key: str,
    current_fields: dict[str, str | None],
    labels: GoldLabels,
    tags: tuple[DifficultyTag, ...],
) -> None:
    tag_set = set(tags)
    present_fields = sum(expected is not None for expected in labels.fields.values())
    if DifficultyTag.SINGLE_FIELD in tag_set and present_fields != 1:
        raise ValueError("single_field tag requires exactly one present label field")
    if DifficultyTag.MULTI_FIELD in tag_set and present_fields < 2:
        raise ValueError("multi_field tag requires at least two present label fields")
    if present_fields == 1 and DifficultyTag.SINGLE_FIELD not in tag_set:
        raise ValueError("single_field tag is required for exactly one present label field")
    if present_fields >= 2 and DifficultyTag.MULTI_FIELD not in tag_set:
        raise ValueError("multi_field tag is required for two or more present label fields")
    contract = EVALUATION_CONTRACTS[scenario_key]
    required_objective_tags = dict(contract.objective_tags_by_action)[labels.user_action]
    present_objective_tags = tag_set & OBJECTIVE_DIFFICULTY_TAGS_V1
    if present_objective_tags != required_objective_tags:
        raise ValueError(
            "objective tags must exactly match the declared action semantics: "
            f"required={sorted(tag.value for tag in required_objective_tags)}, "
            f"present={sorted(tag.value for tag in present_objective_tags)}"
        )
    if DifficultyTag.HARD_NEGATIVE in tag_set and (
        labels.user_action != "unknown" or present_fields
    ):
        raise ValueError("hard_negative tag requires unknown action and absent label fields")
    safety_label = labels.fields.get("safety_status")
    safety_values = set(safety_label.accepted_values) if safety_label is not None else set()
    is_safety_branch = scenario_key == "고객센터:a/s 접수" and (
        "safety_issue" in safety_values or current_fields.get("safety_status") == "safety_issue"
    )
    if DifficultyTag.SAFETY in tag_set and not is_safety_branch:
        raise ValueError("safety tag requires the A/S safety branch")
    if is_safety_branch and DifficultyTag.SAFETY not in tag_set:
        raise ValueError("safety tag is required for the A/S safety branch")
