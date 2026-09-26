from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.authoring import CaseId
from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    CoverageDimension,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.draft_seed_policy import AI_DRAFT_SEED_SPECS_V1
from evals.structured_nlu.obligations import build_official_authoring_obligations
from evals.structured_nlu.schema import (
    DatasetSplit,
    EvaluationCase,
    GoldLabels,
    NonEmptyText,
    NonEmptyUserMessage,
    ReviewStatus,
)
from evals.structured_nlu.semantics import DifficultyTag

AI_DRAFT_SEED_SCHEMA_VERSION = 1
AI_DRAFT_PROVENANCE = "ai_assisted_unreviewed"
AI_DRAFT_GENERATOR_ID = "openai-codex"


class DraftObligationReference(BaseModel):
    """Point at one live-contract obligation that a proposed case is meant to exercise."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_key: NonEmptyText
    dimension: CoverageDimension
    value: NonEmptyText


class ProposedAuthoringCase(BaseModel):
    """Store an unreviewed case proposal without claiming human authorship."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: CaseId
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    offered_alternative_times: tuple[NonEmptyText, ...]
    user_message: NonEmptyUserMessage
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)


class AIDraftSuggestion(BaseModel):
    """Keep one AI suggestion outside the official AuthoringGroup source contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suggestion_id: CaseId
    conversation_group_id: CaseId
    scenario_key: NonEmptyText
    primary_obligation: DraftObligationReference
    proposed_case: ProposedAuthoringCase


class AIDraftSeedManifestV1(BaseModel):
    """Provide one explicitly unreviewed starting suggestion for every NLU scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_seed_schema_version: Literal[AI_DRAFT_SEED_SCHEMA_VERSION]
    profile_id: NonEmptyText
    profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: Literal[AI_DRAFT_PROVENANCE]
    generator_id: Literal[AI_DRAFT_GENERATOR_ID]
    human_review_required: Literal[True]
    suggestions: tuple[AIDraftSuggestion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matches_live_contract_without_promoting_drafts(self) -> AIDraftSeedManifestV1:
        if self.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
            raise ValueError("AI draft seed profile id does not match the official profile")
        if self.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE.fingerprint:
            raise ValueError("AI draft seed profile fingerprint does not match the live contract")

        scenario_keys = [suggestion.scenario_key for suggestion in self.suggestions]
        if len(scenario_keys) != len(set(scenario_keys)):
            raise ValueError("AI draft seeds must contain one suggestion per scenario")
        if set(scenario_keys) != set(EVALUATION_CONTRACTS):
            raise ValueError("AI draft seeds must exactly cover the 16 structured NLU scenarios")

        suggestion_ids = [suggestion.suggestion_id for suggestion in self.suggestions]
        case_ids = [suggestion.proposed_case.id for suggestion in self.suggestions]
        group_ids = [suggestion.conversation_group_id for suggestion in self.suggestions]
        if len(suggestion_ids) != len(set(suggestion_ids)):
            raise ValueError("AI draft suggestion ids must be unique")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("AI draft proposed case ids must be unique")
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("AI draft conversation group ids must be unique")

        obligations = {
            (obligation.scenario_key, obligation.dimension, obligation.value)
            for obligation in build_official_authoring_obligations()
        }
        for suggestion in self.suggestions:
            reference = suggestion.primary_obligation
            if reference.scenario_key != suggestion.scenario_key:
                raise ValueError("AI draft obligation scenario must match its suggestion")
            if (reference.scenario_key, reference.dimension, reference.value) not in obligations:
                raise ValueError("AI draft primary obligation is not in the official inventory")
            _validate_proposed_case(suggestion)
        return self


def _validate_proposed_case(suggestion: AIDraftSuggestion) -> None:
    """Reuse live case validation without emitting a human-authored artifact."""
    proposed = suggestion.proposed_case
    EvaluationCase(
        **proposed.model_dump(mode="python"),
        conversation_group_id=suggestion.conversation_group_id,
        split=DatasetSplit.DEVELOPMENT,
        scenario_key=suggestion.scenario_key,
        provenance="human_authored",
        review_status=ReviewStatus.DRAFT,
    )


def build_ai_draft_seed_manifest_v1() -> AIDraftSeedManifestV1:
    suggestions = []
    for scenario_key, seed in sorted(AI_DRAFT_SEED_SPECS_V1.items()):
        contract = EVALUATION_CONTRACTS[scenario_key]
        if "unknown" not in contract.allowed_actions_for_state("greeting"):
            raise RuntimeError(f"AI draft seed requires greeting->unknown: {scenario_key}")
        if seed.intent not in contract.allowed_intents:
            raise RuntimeError(f"AI draft seed intent is not allowed: {scenario_key}={seed.intent}")
        fields = {field_name: None for field_name in contract.field_names}
        current_fields = fields.copy() if contract.uses_current_fields else {}
        case_id = f"ai-seed-{seed.slug}.c1"
        suggestions.append(
            AIDraftSuggestion(
                suggestion_id=f"ai-seed-{seed.slug}",
                conversation_group_id=f"ai-seed-{seed.slug}",
                scenario_key=scenario_key,
                primary_obligation=DraftObligationReference(
                    scenario_key=scenario_key,
                    dimension=CoverageDimension.STATE_ACTION,
                    value="greeting->unknown",
                ),
                proposed_case=ProposedAuthoringCase(
                    id=case_id,
                    conversation_state="greeting",
                    current_fields=current_fields,
                    offered_alternative_times=(),
                    user_message=seed.user_message,
                    labels=GoldLabels(
                        intent=seed.intent,
                        fields=fields,
                        user_action="unknown",
                        change_field=None,
                    ),
                    tags=(DifficultyTag.HARD_NEGATIVE,),
                ),
            )
        )
    return AIDraftSeedManifestV1(
        draft_seed_schema_version=AI_DRAFT_SEED_SCHEMA_VERSION,
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        provenance=AI_DRAFT_PROVENANCE,
        generator_id=AI_DRAFT_GENERATOR_ID,
        human_review_required=True,
        suggestions=tuple(suggestions),
    )


def serialize_ai_draft_seed_manifest_v1() -> str:
    return (
        json.dumps(
            build_ai_draft_seed_manifest_v1().model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_ai_draft_seed_schema_v1() -> str:
    schema = AIDraftSeedManifestV1.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:ai-draft-seeds:v1"
    schema["properties"]["profile_id"]["const"] = OFFICIAL_BENCHMARK_PROFILE.profile_id
    schema["properties"]["profile_fingerprint"]["const"] = OFFICIAL_BENCHMARK_PROFILE.fingerprint
    schema["$defs"]["AIDraftSuggestion"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    schema["$defs"]["DraftObligationReference"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
