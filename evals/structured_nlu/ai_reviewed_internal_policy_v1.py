"""Qualification gate for a new AI-authored, human-reviewed internal sample benchmark.

This is deliberately separate from the exhaustive human-authored V3 benchmark.
It validates reviewed inputs and sampling balance, not the identity of a human
reviewer or the absence of semantically similar prior model exposure.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.ai_heldout import (
    AIHeldoutCase,
    AIHeldoutDataset,
    AIHeldoutReviewLedger,
    CaseId,
    Sha256,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import DatasetSplit, NonEmptyText, ReviewStatus
from evals.structured_nlu.semantics import DifficultyTag

POLICY_ID = "ai_authored_human_adjudicated_internal_sample_v1"
CLAIM_LABEL = "AI 작성·사람 검수 내부 공식 표본 평가"
MIN_VALIDATION_PER_SCENARIO = 2
MIN_TEST_PER_SCENARIO = 4
POLICY = {
    "policy_id": POLICY_ID,
    "claim_label": CLAIM_LABEL,
    "scope": "16_detailed_structured_nlu_scenarios_only",
    "primary_metric": "case_exact_match_rate",
    "validation_minimum_per_scenario": MIN_VALIDATION_PER_SCENARIO,
    "test_minimum_per_scenario": MIN_TEST_PER_SCENARIO,
    "balanced_action_groups": ["in_scope", "out_of_scope_unknown"],
    "later_state_test_minimum_per_scenario": 1,
    "paired_interval": {
        "method": "scenario_by_action_group_stratified_paired_percentile_bootstrap",
        "resamples": 20_000,
        "seed": 0,
        "confidence_level": 0.95,
    },
    "test_tuning": "forbidden_after_candidate_freeze",
    "official_human_authored_v3_equivalence": False,
}


def policy_sha256() -> str:
    payload = json.dumps(POLICY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class InternalCorpusAudit:
    policy_id: str
    policy_sha256: str
    validation_sha256: str
    test_sha256: str
    validation_case_ledger_sha256: str
    test_case_ledger_sha256: str
    validation_cases: int
    test_cases: int
    validation_per_scenario: int
    test_per_scenario: int
    scenario_count: int
    prior_exposure_messages_checked: int

    def to_dict(self) -> dict:
        return vars(self).copy()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def case_sha256(case: AIHeldoutCase) -> str:
    """Bind one decision to every case field, including the full labels and nulls."""
    raw = json.dumps(
        case.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha(raw)


class InternalCaseDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: CaseId
    case_sha256: Sha256
    adjudicator_role_id: CaseId
    adjudicated_at: datetime
    decision: Literal["accepted"]
    rationale: NonEmptyText

    @model_validator(mode="after")
    def has_timezone(self) -> InternalCaseDecisionV1:
        if self.adjudicated_at.tzinfo is None:
            raise ValueError("case decision timestamp requires a timezone")
        return self


class InternalCaseReviewLedgerV1(BaseModel):
    """Case-by-case decisions in addition to the existing aggregate review ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_reviewed_internal_case_decisions_v1"]
    dataset_sha256: Sha256
    decisions: tuple[InternalCaseDecisionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ordered_cases(self) -> InternalCaseReviewLedgerV1:
        ids = [decision.case_id for decision in self.decisions]
        if ids != sorted(set(ids)):
            raise ValueError("case decisions must have unique sorted IDs")
        return self


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _input_key(case) -> str:
    payload = {
        "scenario_key": case.scenario_key,
        "conversation_state": case.conversation_state,
        "current_fields": case.current_fields,
        "offered_alternative_times": case.offered_alternative_times,
        "user_message": case.user_message,
    }
    return _nfc(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _checked_split(
    dataset_raw: bytes,
    ledger_raw: bytes,
    case_ledger_raw: bytes,
    split: DatasetSplit,
) -> AIHeldoutDataset:
    dataset = AIHeldoutDataset.model_validate_json(dataset_raw)
    ledger = AIHeldoutReviewLedger.model_validate_json(ledger_raw)
    if ledger.dataset_sha256 != _sha(dataset_raw):
        raise ValueError(f"{split.value} review ledger does not match dataset bytes")
    if any(case.split is not split for case in dataset.cases):
        raise ValueError(f"{split.value} dataset contains a different split")
    if any(case.review_status is not ReviewStatus.ADJUDICATED for case in dataset.cases):
        raise ValueError(f"{split.value} requires adjudicated cases")
    if ledger.accepted_case_ids != tuple(sorted(case.id for case in dataset.cases)):
        raise ValueError(f"{split.value} review ledger case IDs differ")
    case_ledger = InternalCaseReviewLedgerV1.model_validate_json(case_ledger_raw)
    if case_ledger.dataset_sha256 != _sha(dataset_raw):
        raise ValueError(f"{split.value} case ledger does not match dataset bytes")
    decisions = {decision.case_id: decision for decision in case_ledger.decisions}
    if set(decisions) != {case.id for case in dataset.cases}:
        raise ValueError(f"{split.value} case ledger IDs differ")
    for case in dataset.cases:
        if decisions[case.id].case_sha256 != case_sha256(case):
            raise ValueError(f"{split.value} case decision content differs: {case.id}")
    return dataset


def _category(case) -> str:
    hard_negative = DifficultyTag.HARD_NEGATIVE in case.tags
    unknown = case.labels.user_action == "unknown"
    if hard_negative != unknown:
        raise ValueError(f"case category/tag conflict: {case.id}")
    return "out_of_scope_unknown" if unknown else "in_scope"


def _balanced_scenarios(dataset: AIHeldoutDataset, split: DatasetSplit) -> int:
    cases_by_scenario = {
        key: [case for case in dataset.cases if case.scenario_key == key]
        for key in EVALUATION_CONTRACTS
    }
    if any(not cases for cases in cases_by_scenario.values()):
        raise ValueError(f"{split.value} must cover all 16 detailed scenarios")
    counts = {len(cases) for cases in cases_by_scenario.values()}
    if len(counts) != 1:
        raise ValueError(f"{split.value} scenarios must have equal case counts")
    per_scenario = counts.pop()
    minimum = (
        MIN_VALIDATION_PER_SCENARIO if split is DatasetSplit.VALIDATION else MIN_TEST_PER_SCENARIO
    )
    if per_scenario < minimum or per_scenario % 2:
        raise ValueError(f"{split.value} scenario count must be even and at least {minimum}")
    for scenario, cases in cases_by_scenario.items():
        category_counts = Counter(_category(case) for case in cases)
        if category_counts != {
            "in_scope": per_scenario // 2,
            "out_of_scope_unknown": per_scenario // 2,
        }:
            raise ValueError(f"{split.value} action groups are unbalanced: {scenario}")
        if split is DatasetSplit.TEST and not any(
            case.conversation_state != "greeting" for case in cases
        ):
            raise ValueError(f"test lacks a later state: {scenario}")
    return per_scenario


def audit_internal_corpus(
    *,
    validation_dataset_bytes: bytes,
    validation_ledger_bytes: bytes,
    validation_case_ledger_bytes: bytes,
    test_dataset_bytes: bytes,
    test_ledger_bytes: bytes,
    test_case_ledger_bytes: bytes,
    prior_exposed_messages: tuple[str, ...],
) -> InternalCorpusAudit:
    """Check a new balanced, reviewed AI-origin corpus before any test model call.

    The prior-exposure inventory is supplied separately and must be audited for
    completeness; exact-text filtering cannot establish semantic independence.
    """
    if not prior_exposed_messages:
        raise ValueError("a prior-exposure inventory is required")
    if any(not _nfc(message) for message in prior_exposed_messages):
        raise ValueError("prior-exposure inventory contains a blank message")
    validation = _checked_split(
        validation_dataset_bytes,
        validation_ledger_bytes,
        validation_case_ledger_bytes,
        DatasetSplit.VALIDATION,
    )
    test = _checked_split(
        test_dataset_bytes, test_ledger_bytes, test_case_ledger_bytes, DatasetSplit.TEST
    )
    validation_count = _balanced_scenarios(validation, DatasetSplit.VALIDATION)
    test_count = _balanced_scenarios(test, DatasetSplit.TEST)
    all_cases = validation.cases + test.cases
    if len({case.id for case in all_cases}) != len(all_cases):
        raise ValueError("case IDs overlap across validation and test")
    if {case.conversation_group_id for case in validation.cases} & {
        case.conversation_group_id for case in test.cases
    }:
        raise ValueError("conversation groups overlap across validation and test")
    if len({_input_key(case) for case in all_cases}) != len(all_cases):
        raise ValueError("model inputs overlap across validation and test")
    validation_messages = {_nfc(case.user_message) for case in validation.cases}
    test_messages = {_nfc(case.user_message) for case in test.cases}
    if validation_messages & test_messages:
        raise ValueError("utterance text overlaps across validation and test")
    if test_messages & {_nfc(message) for message in prior_exposed_messages}:
        raise ValueError("test utterance was previously exposed")
    return InternalCorpusAudit(
        policy_id=POLICY_ID,
        policy_sha256=policy_sha256(),
        validation_sha256=_sha(validation_dataset_bytes),
        test_sha256=_sha(test_dataset_bytes),
        validation_case_ledger_sha256=_sha(validation_case_ledger_bytes),
        test_case_ledger_sha256=_sha(test_case_ledger_bytes),
        validation_cases=len(validation.cases),
        test_cases=len(test.cases),
        validation_per_scenario=validation_count,
        test_per_scenario=test_count,
        scenario_count=len(EVALUATION_CONTRACTS),
        prior_exposure_messages_checked=len(prior_exposed_messages),
    )
