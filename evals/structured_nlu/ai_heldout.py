"""Separate review gate for AI-authored, human-adjudicated heldout cases.

This is not the human-authored official benchmark or its V4 freeze boundary.
The ledger records a human decision; a hash cannot prove who actually reviewed it.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import (
    DatasetSplit,
    GoldLabels,
    NonEmptyText,
    NonEmptyUserMessage,
    ReviewStatus,
    validate_evaluation_case_semantics,
)
from evals.structured_nlu.semantics import DifficultyTag
from services.flow.common.state_contract import SCENARIO_STATE_VERSION

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CaseId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]


class AIHeldoutCase(BaseModel):
    """One fictional, AI-authored case; never masquerade as human-authored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: CaseId
    conversation_group_id: CaseId
    split: DatasetSplit
    scenario_key: NonEmptyText
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    offered_alternative_times: tuple[NonEmptyText, ...]
    user_message: NonEmptyUserMessage
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    provenance: Literal["ai_authored"]
    review_status: ReviewStatus

    @model_validator(mode="after")
    def follows_live_contract(self) -> AIHeldoutCase:
        validate_evaluation_case_semantics(
            scenario_key=self.scenario_key,
            conversation_state=self.conversation_state,
            current_fields=self.current_fields,
            offered_alternative_times=self.offered_alternative_times,
            labels=self.labels,
            tags=self.tags,
        )
        return self


class AIHeldoutDataset(BaseModel):
    """Separate corpus format; the official GoldDataset does not accept it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_authored_heldout_dataset_v1"]
    dataset_version: Literal[1]
    state_contract_version: Literal[SCENARIO_STATE_VERSION]
    declared_model_exposure: Literal["not_run"]
    cases: tuple[AIHeldoutCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases_and_inputs(self) -> AIHeldoutDataset:
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("AI heldout case IDs must be unique")
        groups: dict[str, set[DatasetSplit]] = {}
        inputs: set[str] = set()
        for case in self.cases:
            groups.setdefault(case.conversation_group_id, set()).add(case.split)
            payload = {
                "scenario_key": case.scenario_key,
                "conversation_state": case.conversation_state,
                "current_fields": case.current_fields,
                "offered_alternative_times": case.offered_alternative_times,
                "user_message": case.user_message,
            }
            fingerprint = json.dumps(
                _normalize_nfc(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            if fingerprint in inputs:
                raise ValueError("duplicate AI heldout model inputs are not allowed")
            inputs.add(fingerprint)
        if any(len(splits) > 1 for splits in groups.values()):
            raise ValueError("AI heldout conversation groups must not cross splits")
        return self


class AIHeldoutReviewLedger(BaseModel):
    """One explicit decision over the exact raw dataset bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_authored_heldout_review_v1"]
    reviewed_for: Literal["ai_authored_heldout_accuracy"]
    dataset_sha256: Sha256
    accepted_case_ids: tuple[CaseId, ...] = Field(min_length=1)
    adjudicator_id: CaseId
    adjudicated_at: datetime
    rationale: NonEmptyText

    @model_validator(mode="after")
    def decision_is_well_formed(self) -> AIHeldoutReviewLedger:
        if self.adjudicated_at.tzinfo is None:
            raise ValueError("adjudicated_at must include a timezone")
        if list(self.accepted_case_ids) != sorted(set(self.accepted_case_ids)):
            raise ValueError("accepted_case_ids must be unique and sorted")
        return self


class ReviewedAIHeldout(BaseModel):
    """Validated input bundle for a future AI-heldout prediction runner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: AIHeldoutDataset
    dataset_sha256: Sha256
    review_ledger: AIHeldoutReviewLedger
    scenario_counts: dict[str, int]


def verify_ai_heldout_review(dataset_bytes: bytes, review_ledger_bytes: bytes) -> ReviewedAIHeldout:
    """Reject draft, mismatched, or incomplete 16-scenario heldout inputs."""
    dataset = AIHeldoutDataset.model_validate_json(dataset_bytes)
    ledger = AIHeldoutReviewLedger.model_validate_json(review_ledger_bytes)
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    if ledger.dataset_sha256 != digest:
        raise ValueError("review ledger does not match the exact AI heldout dataset bytes")
    if any(case.split is not DatasetSplit.TEST for case in dataset.cases):
        raise ValueError("AI heldout scoring requires test cases only")
    if any(case.review_status is not ReviewStatus.ADJUDICATED for case in dataset.cases):
        raise ValueError("AI heldout scoring requires adjudicated cases only")
    case_ids = tuple(sorted(case.id for case in dataset.cases))
    if ledger.accepted_case_ids != case_ids:
        raise ValueError("review ledger case IDs must exactly match the AI heldout dataset")
    counts = Counter(case.scenario_key for case in dataset.cases)
    if set(counts) != set(EVALUATION_CONTRACTS):
        raise ValueError("AI heldout evaluation requires cases from all 16 detailed scenarios")
    return ReviewedAIHeldout(
        dataset=dataset,
        dataset_sha256=digest,
        review_ledger=ledger,
        scenario_counts={key: counts[key] for key in sorted(counts)},
    )


def load_reviewed_ai_heldout(dataset_path: Path, review_ledger_path: Path) -> ReviewedAIHeldout:
    """Read each artifact once so review and execution share exact bytes."""
    return verify_ai_heldout_review(dataset_path.read_bytes(), review_ledger_path.read_bytes())


def _normalize_nfc(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {key: _normalize_nfc(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_nfc(item) for item in value]
    return value
