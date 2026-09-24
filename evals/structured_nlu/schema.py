from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from services.flow.common.state_contract import SCENARIO_STATE_VERSION


class DatasetSplit(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    TEST = "test"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ADJUDICATED = "adjudicated"


class DifficultyTag(StrEnum):
    SINGLE_FIELD = "single_field"
    MULTI_FIELD = "multi_field"
    CORRECTION = "correction"
    NEGATION = "negation"
    ELLIPSIS = "ellipsis"
    COLLOQUIAL = "colloquial"
    AMBIGUOUS = "ambiguous"
    HARD_NEGATIVE = "hard_negative"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
    CLOSING = "closing"
    SAFETY = "safety"


NonEmptyText = Annotated[str, Field(min_length=1, max_length=1_000)]


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
    split: DatasetSplit
    scenario_key: NonEmptyText
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    user_message: Annotated[str, Field(min_length=1, max_length=4_000)]
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    provenance: Literal["human_authored"]
    review_status: ReviewStatus

    @model_validator(mode="after")
    def follows_live_service_contract(self) -> EvaluationCase:
        contract = EVALUATION_CONTRACTS.get(self.scenario_key)
        if contract is None:
            raise ValueError(f"unknown detailed scenario: {self.scenario_key}")
        if self.conversation_state not in contract.conversation_states:
            raise ValueError(
                f"conversation_state is not allowed for {self.scenario_key}: "
                f"{self.conversation_state}"
            )
        if self.labels.intent not in contract.allowed_intents:
            raise ValueError(f"intent must be one of {sorted(map(str, contract.allowed_intents))}")
        if set(self.labels.fields) != set(contract.field_names):
            raise ValueError(f"label fields must be exactly {sorted(contract.field_names)}")
        field_options = dict(contract.field_options)
        for field_name, expected in self.labels.fields.items():
            allowed_values = field_options.get(field_name)
            if expected is None or allowed_values is None:
                continue
            invalid_values = set(expected.accepted_values) - allowed_values
            if invalid_values:
                raise ValueError(
                    f"accepted_values are not allowed for {self.scenario_key}: "
                    f"{field_name}={sorted(invalid_values)}"
                )
        if self.labels.user_action not in contract.user_actions:
            raise ValueError(
                f"user_action is not allowed for {self.scenario_key}: {self.labels.user_action}"
            )

        if contract.uses_current_fields:
            if set(self.current_fields) != set(contract.field_names):
                raise ValueError(f"current_fields must be exactly {sorted(contract.field_names)}")
            if self.labels.user_action == "change_detail":
                if self.labels.change_field not in contract.field_names:
                    raise ValueError("change_field must name a workflow field")
            elif self.labels.change_field is not None:
                raise ValueError("change_field must be null unless user_action is change_detail")
        else:
            if self.current_fields:
                raise ValueError("current_fields must be empty for this extractor")
            if self.labels.change_field is not None:
                raise ValueError("change_field is only used by service workflows")

        if len(set(self.tags)) != len(self.tags):
            raise ValueError("tags must be unique")
        return self


class GoldDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_version: Literal[1]
    state_contract_version: Literal[SCENARIO_STATE_VERSION]
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> GoldDataset:
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("case ids must be unique")
        return self

    def official_cases(self, split: DatasetSplit | None = None) -> tuple[EvaluationCase, ...]:
        return tuple(
            case
            for case in self.cases
            if case.review_status is ReviewStatus.ADJUDICATED
            and (split is None or case.split is split)
        )


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
