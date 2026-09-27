from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.ai_origin_policy import ai_origin_text_fingerprint_v1
from evals.structured_nlu.authoring import CaseId
from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    CoverageDimension,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.coverage_candidate_policy import (
    COVERAGE_CANDIDATE_SPECS_V1,
    CoverageCandidateSpecV1,
)
from evals.structured_nlu.coverage_candidate_policy_v2 import (
    COVERAGE_CANDIDATE_SPECS_V2,
    CoverageCandidateSpecV2,
)
from evals.structured_nlu.draft_seed_policy import AI_DRAFT_SEED_SPECS_V1
from evals.structured_nlu.obligations import build_official_authoring_obligations
from evals.structured_nlu.schema import (
    GoldLabels,
    NonEmptyText,
    NonEmptyUserMessage,
    ReviewStatus,
    validate_evaluation_case_semantics,
)
from evals.structured_nlu.semantics import DifficultyTag
from evals.structured_nlu.subagent_candidate_policy import (
    AI_SUBAGENT_CANDIDATE_SPECS_V1,
)

AI_DRAFT_SEED_SCHEMA_VERSION = 1
AI_DRAFT_PROVENANCE = "ai_assisted_unreviewed"
AI_DRAFT_GENERATOR_ID = "openai-codex"
AI_DRAFT_REVIEW_PACKET_VERSION = 1
AI_SUBAGENT_CANDIDATE_SCHEMA_VERSION = 1
AI_SUBAGENT_CANDIDATE_SET_ID = "structured-nlu-subagent-candidates-v1"
AI_SUBAGENT_GENERATOR_ID = "openai-codex-subagents"
AI_SUBAGENT_REVIEW_PACKET_VERSION = 1
AI_COVERAGE_CANDIDATE_SCHEMA_VERSION = 1
AI_COVERAGE_CANDIDATE_SET_ID = "structured-nlu-coverage-candidates-v1"
AI_COVERAGE_CANDIDATE_GENERATOR_ID = "openai-codex-coverage-candidates"
AI_COVERAGE_CANDIDATE_REVIEW_PACKET_VERSION = 1
AI_COVERAGE_BASELINE_SOURCE_ROOT = "evals/structured_nlu/data/source"
AI_COVERAGE_BASELINE_SPLIT_ASSIGNMENT_PATH = (
    "evals/structured_nlu/data/manifests/split-assignments.v1.json"
)
AI_COVERAGE_BASELINE_CASE_COUNT = 36
AI_COVERAGE_BASELINE_COVERED_OBLIGATION_COUNT = 349
AI_COVERAGE_BASELINE_CORPUS_FINGERPRINT = (
    "246e22b0d0b83b5ee0619f6ade5629c52fecb07e3b450f477efd2317da5e5ca7"
)
AI_COVERAGE_BASELINE_REPORT_ID = "maeumcall-structured-nlu-development-progress-v1"
AI_COVERAGE_PROJECTED_MARGINAL_GAIN = 233
AI_COVERAGE_PROJECTED_COVERED_OBLIGATION_COUNT = 582
AI_COVERAGE_OFFICIAL_OBLIGATION_COUNT = 1562
AI_COVERAGE_CANDIDATE_SCHEMA_VERSION_V2 = 2
AI_COVERAGE_CANDIDATE_SET_ID_V2 = "structured-nlu-coverage-candidates-v2"
AI_COVERAGE_CANDIDATE_REVIEW_PACKET_VERSION_V2 = 2
AI_COVERAGE_V1_MANIFEST_SHA256 = "28128c46b3b3a3a559066dd8dfbbf17e95344bc2d58079603a09da0c8fa5f6dc"
AI_COVERAGE_V2_BASELINE_COVERED_OBLIGATION_COUNT = 582
AI_COVERAGE_V2_BASELINE_MISSING_OBLIGATION_COUNT = 980
AI_COVERAGE_V2_PROJECTED_MARGINAL_GAIN = 31
AI_COVERAGE_V2_PROJECTED_COVERED_OBLIGATION_COUNT = 613
AI_COVERAGE_V2_PROJECTED_MISSING_OBLIGATION_COUNT = 949


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


@dataclass(frozen=True)
class CoverageCandidateDiagnosticCase:
    """Expose proposal semantics to diagnostics without inventing source provenance."""

    id: str
    scenario_key: str
    conversation_state: str
    current_fields: dict[str, str | None]
    offered_alternative_times: tuple[str, ...]
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...]
    review_status: ReviewStatus = ReviewStatus.DRAFT


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


class AISubagentSuggestion(AIDraftSuggestion):
    """Record a subagent alternative and its concise contract-based justification."""

    source_suggestion_id: CaseId
    drafting_rationale: NonEmptyText


class AISubagentCandidateManifestV1(BaseModel):
    """Keep subagent-written alternatives outside human-authored corpus source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subagent_candidate_schema_version: Literal[AI_SUBAGENT_CANDIDATE_SCHEMA_VERSION]
    candidate_set_id: Literal[AI_SUBAGENT_CANDIDATE_SET_ID]
    profile_id: NonEmptyText
    profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: Literal[AI_DRAFT_PROVENANCE]
    generator_id: Literal[AI_SUBAGENT_GENERATOR_ID]
    human_review_required: Literal[True]
    automatic_promotion_allowed: Literal[False]
    suggestions: tuple[AISubagentSuggestion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matches_live_contract_without_claiming_human_authorship(
        self,
    ) -> AISubagentCandidateManifestV1:
        if self.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
            raise ValueError("AI subagent profile id does not match the official profile")
        if self.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE.fingerprint:
            raise ValueError("AI subagent profile fingerprint does not match the live contract")

        scenario_keys = [suggestion.scenario_key for suggestion in self.suggestions]
        if len(scenario_keys) != len(set(scenario_keys)):
            raise ValueError("AI subagent candidates must contain one suggestion per scenario")
        if set(scenario_keys) != set(EVALUATION_CONTRACTS):
            raise ValueError("AI subagent candidates must exactly cover the 16 NLU scenarios")

        manifest = build_ai_draft_seed_manifest_v1()
        seeds_by_scenario = {
            suggestion.scenario_key: suggestion for suggestion in manifest.suggestions
        }
        suggestion_ids = [suggestion.suggestion_id for suggestion in self.suggestions]
        case_ids = [suggestion.proposed_case.id for suggestion in self.suggestions]
        group_ids = [suggestion.conversation_group_id for suggestion in self.suggestions]
        message_fingerprints = [
            ai_origin_text_fingerprint_v1(suggestion.proposed_case.user_message)
            for suggestion in self.suggestions
        ]
        for values, error in (
            (suggestion_ids, "AI subagent suggestion ids must be unique"),
            (case_ids, "AI subagent proposed case ids must be unique"),
            (group_ids, "AI subagent draft group ids must be unique"),
            (
                message_fingerprints,
                "AI subagent candidate messages must be unique after NFC normalization",
            ),
        ):
            if len(values) != len(set(values)):
                raise ValueError(error)

        obligations = {
            (obligation.scenario_key, obligation.dimension, obligation.value)
            for obligation in build_official_authoring_obligations()
        }
        for suggestion in self.suggestions:
            seed = seeds_by_scenario[suggestion.scenario_key]
            reference = suggestion.primary_obligation
            candidate_spec = AI_SUBAGENT_CANDIDATE_SPECS_V1[suggestion.scenario_key]
            expected_suggestion_id = f"ai-subagent-{candidate_spec.slug}"
            if suggestion.suggestion_id != expected_suggestion_id:
                raise ValueError("AI subagent suggestion id does not match the V1 policy")
            if suggestion.conversation_group_id != expected_suggestion_id:
                raise ValueError("AI subagent draft group id does not match the V1 policy")
            if suggestion.proposed_case.id != f"{expected_suggestion_id}.c1":
                raise ValueError("AI subagent proposed case id does not match the V1 policy")
            if suggestion.source_suggestion_id != seed.suggestion_id:
                raise ValueError("AI subagent source suggestion does not match its scenario")
            if suggestion.primary_obligation != seed.primary_obligation:
                raise ValueError("AI subagent obligation must match the bootstrap seed")
            if suggestion.drafting_rationale != candidate_spec.drafting_rationale:
                raise ValueError("AI subagent rationale does not match the V1 policy")
            if suggestion.proposed_case.user_message != candidate_spec.user_message:
                raise ValueError("AI subagent message does not match the V1 policy")
            expected_case = seed.proposed_case.model_copy(
                update={
                    "id": f"{expected_suggestion_id}.c1",
                    "user_message": candidate_spec.user_message,
                }
            )
            if suggestion.proposed_case != expected_case:
                raise ValueError("AI subagent proposed case drifted from the bootstrap contract")
            if ai_origin_text_fingerprint_v1(
                suggestion.proposed_case.user_message
            ) == ai_origin_text_fingerprint_v1(seed.proposed_case.user_message):
                raise ValueError("AI subagent candidate must differ from the bootstrap seed")
            if reference.scenario_key != suggestion.scenario_key:
                raise ValueError("AI subagent obligation scenario must match its suggestion")
            if (reference.scenario_key, reference.dimension, reference.value) not in obligations:
                raise ValueError("AI subagent primary obligation is not in the official inventory")
            _validate_proposed_case(suggestion)
        return self


class AICoverageCandidateSuggestionV1(AIDraftSuggestion):
    """Record one unreviewed proposal for a baseline coverage gap."""

    target_field: NonEmptyText
    baseline_obligation_missing: Literal[True]
    semantic_valid: Literal[True]


class AICoverageCandidateManifestV1(BaseModel):
    """Keep the 24 deterministic coverage proposals outside the official corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_candidate_schema_version: Literal[AI_COVERAGE_CANDIDATE_SCHEMA_VERSION]
    candidate_set_id: Literal[AI_COVERAGE_CANDIDATE_SET_ID]
    profile_id: NonEmptyText
    profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: Literal[AI_DRAFT_PROVENANCE]
    generator_id: Literal[AI_COVERAGE_CANDIDATE_GENERATOR_ID]
    human_review_required: Literal[True]
    automatic_promotion_allowed: Literal[False]
    baseline_source_root: Literal[AI_COVERAGE_BASELINE_SOURCE_ROOT]
    baseline_split_assignment_path: Literal[AI_COVERAGE_BASELINE_SPLIT_ASSIGNMENT_PATH]
    baseline_case_count: Literal[AI_COVERAGE_BASELINE_CASE_COUNT]
    baseline_corpus_fingerprint: Literal[AI_COVERAGE_BASELINE_CORPUS_FINGERPRINT]
    baseline_progress_report_id: Literal[AI_COVERAGE_BASELINE_REPORT_ID]
    baseline_covered_obligation_count: Literal[AI_COVERAGE_BASELINE_COVERED_OBLIGATION_COUNT]
    official_obligation_count: Literal[AI_COVERAGE_OFFICIAL_OBLIGATION_COUNT]
    projected_marginal_gain: Literal[AI_COVERAGE_PROJECTED_MARGINAL_GAIN]
    projected_covered_obligation_count: Literal[AI_COVERAGE_PROJECTED_COVERED_OBLIGATION_COUNT]
    suggestions: tuple[AICoverageCandidateSuggestionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matches_coverage_policy_and_live_contract(
        self,
    ) -> AICoverageCandidateManifestV1:
        if self.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
            raise ValueError("AI coverage profile id does not match the official profile")
        if self.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE.fingerprint:
            raise ValueError("AI coverage profile fingerprint does not match the live contract")
        if self.projected_covered_obligation_count != (
            self.baseline_covered_obligation_count + self.projected_marginal_gain
        ):
            raise ValueError("AI coverage projection arithmetic does not match")
        if len(self.suggestions) != len(COVERAGE_CANDIDATE_SPECS_V1):
            raise ValueError("AI coverage candidates must exactly match the V1 policy")

        ids = [suggestion.suggestion_id for suggestion in self.suggestions]
        group_ids = [suggestion.conversation_group_id for suggestion in self.suggestions]
        case_ids = [suggestion.proposed_case.id for suggestion in self.suggestions]
        fingerprints = [
            ai_origin_text_fingerprint_v1(suggestion.proposed_case.user_message)
            for suggestion in self.suggestions
        ]
        for values, error in (
            (ids, "AI coverage suggestion ids must be unique"),
            (group_ids, "AI coverage group ids must be unique"),
            (case_ids, "AI coverage case ids must be unique"),
            (fingerprints, "AI coverage messages must be unique after NFC normalization"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(error)

        obligations = {
            (obligation.scenario_key, obligation.dimension, obligation.value)
            for obligation in build_official_authoring_obligations()
        }
        by_id = {suggestion.suggestion_id: suggestion for suggestion in self.suggestions}
        for slug, spec in COVERAGE_CANDIDATE_SPECS_V1.items():
            expected_id = f"ai-coverage-v1-{slug}"
            suggestion = by_id.get(expected_id)
            if suggestion is None:
                raise ValueError("AI coverage candidate id does not match the V1 policy")
            if suggestion.conversation_group_id != expected_id:
                raise ValueError("AI coverage group id does not match the V1 policy")
            if suggestion.proposed_case.id != f"{expected_id}.c1":
                raise ValueError("AI coverage case id does not match the V1 policy")
            if suggestion.scenario_key != spec.scenario_key:
                raise ValueError("AI coverage scenario does not match the V1 policy")
            if suggestion.target_field != spec.target_field:
                raise ValueError("AI coverage target field does not match the V1 policy")
            expected_obligation = (
                spec.scenario_key,
                CoverageDimension.FIELD_PRESENT,
                spec.target_field,
            )
            reference = suggestion.primary_obligation
            if (
                reference.scenario_key,
                reference.dimension,
                reference.value,
            ) != expected_obligation:
                raise ValueError("AI coverage primary obligation does not match the V1 policy")
            if expected_obligation not in obligations:
                raise ValueError("AI coverage primary obligation is not official")
            if suggestion.proposed_case != _coverage_proposed_case(spec, expected_id):
                raise ValueError("AI coverage proposed case drifted from the V1 policy")
            _validate_proposed_case(suggestion)
        return self


class AICoverageCandidateSuggestionV2(AIDraftSuggestion):
    """Record one delta proposal and its exact projected obligation gains."""

    target_field: NonEmptyText
    baseline_obligation_missing: Literal[True]
    semantic_valid: Literal[True]
    projected_obligations: tuple[DraftObligationReference, ...] = Field(min_length=1)


class AICoverageCandidateManifestV2(BaseModel):
    """Describe a reusable delta batch evaluated after the immutable V1 candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_candidate_schema_version: Literal[AI_COVERAGE_CANDIDATE_SCHEMA_VERSION_V2]
    candidate_set_id: Literal[AI_COVERAGE_CANDIDATE_SET_ID_V2]
    predecessor_candidate_set_id: Literal[AI_COVERAGE_CANDIDATE_SET_ID]
    predecessor_candidate_manifest_sha256: Literal[AI_COVERAGE_V1_MANIFEST_SHA256]
    profile_id: NonEmptyText
    profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: Literal[AI_DRAFT_PROVENANCE]
    generator_id: Literal[AI_COVERAGE_CANDIDATE_GENERATOR_ID]
    human_review_required: Literal[True]
    automatic_promotion_allowed: Literal[False]
    baseline_source_root: Literal[AI_COVERAGE_BASELINE_SOURCE_ROOT]
    baseline_split_assignment_path: Literal[AI_COVERAGE_BASELINE_SPLIT_ASSIGNMENT_PATH]
    baseline_case_count: Literal[AI_COVERAGE_BASELINE_CASE_COUNT]
    baseline_corpus_fingerprint: Literal[AI_COVERAGE_BASELINE_CORPUS_FINGERPRINT]
    baseline_diagnostic_case_ids: tuple[CaseId, ...] = Field(min_length=1)
    baseline_covered_obligation_count: Literal[AI_COVERAGE_V2_BASELINE_COVERED_OBLIGATION_COUNT]
    baseline_missing_obligation_count: Literal[AI_COVERAGE_V2_BASELINE_MISSING_OBLIGATION_COUNT]
    official_obligation_count: Literal[AI_COVERAGE_OFFICIAL_OBLIGATION_COUNT]
    projected_marginal_gain: Literal[AI_COVERAGE_V2_PROJECTED_MARGINAL_GAIN]
    projected_covered_obligation_count: Literal[AI_COVERAGE_V2_PROJECTED_COVERED_OBLIGATION_COUNT]
    projected_missing_obligation_count: Literal[AI_COVERAGE_V2_PROJECTED_MISSING_OBLIGATION_COUNT]
    suggestions: tuple[AICoverageCandidateSuggestionV2, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matches_v2_policy_and_live_contract(self) -> AICoverageCandidateManifestV2:
        if self.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
            raise ValueError("AI coverage V2 profile id does not match")
        if self.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE.fingerprint:
            raise ValueError("AI coverage V2 profile fingerprint does not match")
        if self.baseline_covered_obligation_count + self.baseline_missing_obligation_count != (
            self.official_obligation_count
        ):
            raise ValueError("AI coverage V2 baseline counts do not balance")
        if self.projected_covered_obligation_count != (
            self.baseline_covered_obligation_count + self.projected_marginal_gain
        ):
            raise ValueError("AI coverage V2 projection arithmetic does not match")
        if self.projected_missing_obligation_count != (
            self.official_obligation_count - self.projected_covered_obligation_count
        ):
            raise ValueError("AI coverage V2 projected missing count does not match")

        v1 = build_ai_coverage_candidate_manifest_v1()
        if (
            hashlib.sha256(
                serialize_ai_coverage_candidate_manifest_v1().encode("utf-8")
            ).hexdigest()
            != self.predecessor_candidate_manifest_sha256
        ):
            raise ValueError("AI coverage V1 predecessor manifest fingerprint drifted")
        expected_baseline_ids = tuple(
            sorted(suggestion.proposed_case.id for suggestion in v1.suggestions)
        )
        if self.baseline_diagnostic_case_ids != expected_baseline_ids:
            raise ValueError("AI coverage V2 baseline diagnostic ids drifted from V1")
        if len(self.suggestions) != len(COVERAGE_CANDIDATE_SPECS_V2):
            raise ValueError("AI coverage V2 suggestions must exactly match policy")

        ids = [suggestion.suggestion_id for suggestion in self.suggestions]
        fingerprints = [
            ai_origin_text_fingerprint_v1(suggestion.proposed_case.user_message)
            for suggestion in self.suggestions
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("AI coverage V2 suggestion ids must be unique")
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("AI coverage V2 messages must be unique")

        official = {
            (obligation.scenario_key, obligation.dimension, obligation.value)
            for obligation in build_official_authoring_obligations()
        }
        by_id = {suggestion.suggestion_id: suggestion for suggestion in self.suggestions}
        projected = set()
        for slug, spec in COVERAGE_CANDIDATE_SPECS_V2.items():
            expected_id = f"ai-coverage-v2-{slug}"
            suggestion = by_id.get(expected_id)
            if suggestion is None:
                raise ValueError("AI coverage V2 candidate id does not match policy")
            if suggestion.conversation_group_id != expected_id:
                raise ValueError("AI coverage V2 group id does not match policy")
            if suggestion.proposed_case.id != f"{expected_id}.c1":
                raise ValueError("AI coverage V2 case id does not match policy")
            if suggestion.scenario_key != spec.scenario_key:
                raise ValueError("AI coverage V2 scenario does not match policy")
            if suggestion.target_field != spec.target_field:
                raise ValueError("AI coverage V2 target field does not match policy")
            expected_primary = (
                spec.scenario_key,
                CoverageDimension.CURRENT_FIELD_PRESENT,
                spec.target_field,
            )
            primary = suggestion.primary_obligation
            if (primary.scenario_key, primary.dimension, primary.value) != expected_primary:
                raise ValueError("AI coverage V2 primary obligation does not match policy")
            expected_projected = tuple(
                DraftObligationReference(
                    scenario_key=spec.scenario_key,
                    dimension=dimension,
                    value=value,
                )
                for dimension, value in spec.projected_obligations
            )
            if suggestion.projected_obligations != expected_projected:
                raise ValueError("AI coverage V2 projected obligations drifted from policy")
            for reference in suggestion.projected_obligations:
                key = (reference.scenario_key, reference.dimension, reference.value)
                if key not in official:
                    raise ValueError("AI coverage V2 projected obligation is not official")
                projected.add(key)
            if suggestion.proposed_case != _coverage_proposed_case(spec, expected_id):
                raise ValueError("AI coverage V2 proposed case drifted from policy")
            _validate_proposed_case(suggestion)
        if len(projected) != self.projected_marginal_gain:
            raise ValueError("AI coverage V2 projected obligation union does not match gain")
        return self


def _validate_proposed_case(suggestion: AIDraftSuggestion) -> None:
    """Reuse live semantic validation without inventing provenance or review metadata."""
    proposed = suggestion.proposed_case
    validate_evaluation_case_semantics(
        scenario_key=suggestion.scenario_key,
        conversation_state=proposed.conversation_state,
        current_fields=proposed.current_fields,
        offered_alternative_times=proposed.offered_alternative_times,
        labels=proposed.labels,
        tags=proposed.tags,
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


def build_ai_subagent_candidate_manifest_v1() -> AISubagentCandidateManifestV1:
    seed_manifest = build_ai_draft_seed_manifest_v1()
    seeds_by_scenario = {
        suggestion.scenario_key: suggestion for suggestion in seed_manifest.suggestions
    }
    suggestions = []
    for scenario_key, candidate in sorted(AI_SUBAGENT_CANDIDATE_SPECS_V1.items()):
        seed = seeds_by_scenario[scenario_key]
        proposed = seed.proposed_case.model_copy(
            update={
                "id": f"ai-subagent-{candidate.slug}.c1",
                "user_message": candidate.user_message,
            }
        )
        suggestions.append(
            AISubagentSuggestion(
                suggestion_id=f"ai-subagent-{candidate.slug}",
                conversation_group_id=f"ai-subagent-{candidate.slug}",
                scenario_key=scenario_key,
                source_suggestion_id=seed.suggestion_id,
                primary_obligation=seed.primary_obligation,
                proposed_case=proposed,
                drafting_rationale=candidate.drafting_rationale,
            )
        )
    return AISubagentCandidateManifestV1(
        subagent_candidate_schema_version=AI_SUBAGENT_CANDIDATE_SCHEMA_VERSION,
        candidate_set_id=AI_SUBAGENT_CANDIDATE_SET_ID,
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        provenance=AI_DRAFT_PROVENANCE,
        generator_id=AI_SUBAGENT_GENERATOR_ID,
        human_review_required=True,
        automatic_promotion_allowed=False,
        suggestions=tuple(suggestions),
    )


def build_ai_coverage_candidate_manifest_v1() -> AICoverageCandidateManifestV1:
    suggestions = []
    for slug, spec in sorted(COVERAGE_CANDIDATE_SPECS_V1.items()):
        suggestion_id = f"ai-coverage-v1-{slug}"
        suggestions.append(
            AICoverageCandidateSuggestionV1(
                suggestion_id=suggestion_id,
                conversation_group_id=suggestion_id,
                scenario_key=spec.scenario_key,
                target_field=spec.target_field,
                baseline_obligation_missing=True,
                semantic_valid=True,
                primary_obligation=DraftObligationReference(
                    scenario_key=spec.scenario_key,
                    dimension=CoverageDimension.FIELD_PRESENT,
                    value=spec.target_field,
                ),
                proposed_case=_coverage_proposed_case(spec, suggestion_id),
            )
        )
    return AICoverageCandidateManifestV1(
        coverage_candidate_schema_version=AI_COVERAGE_CANDIDATE_SCHEMA_VERSION,
        candidate_set_id=AI_COVERAGE_CANDIDATE_SET_ID,
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        provenance=AI_DRAFT_PROVENANCE,
        generator_id=AI_COVERAGE_CANDIDATE_GENERATOR_ID,
        human_review_required=True,
        automatic_promotion_allowed=False,
        baseline_source_root=AI_COVERAGE_BASELINE_SOURCE_ROOT,
        baseline_split_assignment_path=AI_COVERAGE_BASELINE_SPLIT_ASSIGNMENT_PATH,
        baseline_case_count=AI_COVERAGE_BASELINE_CASE_COUNT,
        baseline_corpus_fingerprint=AI_COVERAGE_BASELINE_CORPUS_FINGERPRINT,
        baseline_progress_report_id=AI_COVERAGE_BASELINE_REPORT_ID,
        baseline_covered_obligation_count=AI_COVERAGE_BASELINE_COVERED_OBLIGATION_COUNT,
        official_obligation_count=AI_COVERAGE_OFFICIAL_OBLIGATION_COUNT,
        projected_marginal_gain=AI_COVERAGE_PROJECTED_MARGINAL_GAIN,
        projected_covered_obligation_count=AI_COVERAGE_PROJECTED_COVERED_OBLIGATION_COUNT,
        suggestions=tuple(suggestions),
    )


def build_ai_coverage_candidate_manifest_v2() -> AICoverageCandidateManifestV2:
    v1 = build_ai_coverage_candidate_manifest_v1()
    suggestions = []
    for slug, spec in sorted(COVERAGE_CANDIDATE_SPECS_V2.items()):
        suggestion_id = f"ai-coverage-v2-{slug}"
        suggestions.append(
            AICoverageCandidateSuggestionV2(
                suggestion_id=suggestion_id,
                conversation_group_id=suggestion_id,
                scenario_key=spec.scenario_key,
                target_field=spec.target_field,
                baseline_obligation_missing=True,
                semantic_valid=True,
                primary_obligation=DraftObligationReference(
                    scenario_key=spec.scenario_key,
                    dimension=CoverageDimension.CURRENT_FIELD_PRESENT,
                    value=spec.target_field,
                ),
                projected_obligations=tuple(
                    DraftObligationReference(
                        scenario_key=spec.scenario_key,
                        dimension=dimension,
                        value=value,
                    )
                    for dimension, value in spec.projected_obligations
                ),
                proposed_case=_coverage_proposed_case(spec, suggestion_id),
            )
        )
    return AICoverageCandidateManifestV2(
        coverage_candidate_schema_version=AI_COVERAGE_CANDIDATE_SCHEMA_VERSION_V2,
        candidate_set_id=AI_COVERAGE_CANDIDATE_SET_ID_V2,
        predecessor_candidate_set_id=AI_COVERAGE_CANDIDATE_SET_ID,
        predecessor_candidate_manifest_sha256=AI_COVERAGE_V1_MANIFEST_SHA256,
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        provenance=AI_DRAFT_PROVENANCE,
        generator_id=AI_COVERAGE_CANDIDATE_GENERATOR_ID,
        human_review_required=True,
        automatic_promotion_allowed=False,
        baseline_source_root=AI_COVERAGE_BASELINE_SOURCE_ROOT,
        baseline_split_assignment_path=AI_COVERAGE_BASELINE_SPLIT_ASSIGNMENT_PATH,
        baseline_case_count=AI_COVERAGE_BASELINE_CASE_COUNT,
        baseline_corpus_fingerprint=AI_COVERAGE_BASELINE_CORPUS_FINGERPRINT,
        baseline_diagnostic_case_ids=tuple(
            sorted(suggestion.proposed_case.id for suggestion in v1.suggestions)
        ),
        baseline_covered_obligation_count=AI_COVERAGE_V2_BASELINE_COVERED_OBLIGATION_COUNT,
        baseline_missing_obligation_count=AI_COVERAGE_V2_BASELINE_MISSING_OBLIGATION_COUNT,
        official_obligation_count=AI_COVERAGE_OFFICIAL_OBLIGATION_COUNT,
        projected_marginal_gain=AI_COVERAGE_V2_PROJECTED_MARGINAL_GAIN,
        projected_covered_obligation_count=AI_COVERAGE_V2_PROJECTED_COVERED_OBLIGATION_COUNT,
        projected_missing_obligation_count=AI_COVERAGE_V2_PROJECTED_MISSING_OBLIGATION_COUNT,
        suggestions=tuple(suggestions),
    )


def coverage_candidate_diagnostic_cases(
    *manifests: AICoverageCandidateManifestV1 | AICoverageCandidateManifestV2,
) -> tuple[CoverageCandidateDiagnosticCase, ...]:
    """Project sidecar semantics without constructing an official evaluation case."""
    return tuple(
        CoverageCandidateDiagnosticCase(
            id=suggestion.proposed_case.id,
            scenario_key=suggestion.scenario_key,
            conversation_state=suggestion.proposed_case.conversation_state,
            current_fields=suggestion.proposed_case.current_fields,
            offered_alternative_times=suggestion.proposed_case.offered_alternative_times,
            labels=suggestion.proposed_case.labels,
            tags=suggestion.proposed_case.tags,
        )
        for manifest in manifests
        for suggestion in manifest.suggestions
    )


def _coverage_proposed_case(
    spec: CoverageCandidateSpecV1 | CoverageCandidateSpecV2,
    suggestion_id: str,
) -> ProposedAuthoringCase:
    fields = {
        field_name: (None if accepted_values is None else {"accepted_values": accepted_values})
        for field_name, accepted_values in spec.fields
    }
    return ProposedAuthoringCase(
        id=f"{suggestion_id}.c1",
        conversation_state=spec.conversation_state,
        current_fields=dict(spec.current_fields),
        offered_alternative_times=spec.offered_alternative_times,
        user_message=spec.user_message,
        labels=GoldLabels(
            intent=spec.intent,
            fields=fields,
            user_action=spec.user_action,
            change_field=spec.change_field,
        ),
        tags=spec.tags,
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


def serialize_ai_subagent_candidate_manifest_v1() -> str:
    return (
        json.dumps(
            build_ai_subagent_candidate_manifest_v1().model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_ai_subagent_candidate_schema_v1() -> str:
    schema = AISubagentCandidateManifestV1.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:ai-subagent-candidates:v1"
    schema["properties"]["profile_id"]["const"] = OFFICIAL_BENCHMARK_PROFILE.profile_id
    schema["properties"]["profile_fingerprint"]["const"] = OFFICIAL_BENCHMARK_PROFILE.fingerprint
    schema["$defs"]["AISubagentSuggestion"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    schema["$defs"]["DraftObligationReference"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def serialize_ai_coverage_candidate_manifest_v1() -> str:
    return (
        json.dumps(
            build_ai_coverage_candidate_manifest_v1().model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_ai_coverage_candidate_schema_v1() -> str:
    schema = AICoverageCandidateManifestV1.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:ai-coverage-candidates:v1"
    schema["properties"]["profile_id"]["const"] = OFFICIAL_BENCHMARK_PROFILE.profile_id
    schema["properties"]["profile_fingerprint"]["const"] = OFFICIAL_BENCHMARK_PROFILE.fingerprint
    schema["$defs"]["AICoverageCandidateSuggestionV1"]["properties"]["scenario_key"]["enum"] = (
        sorted(EVALUATION_CONTRACTS)
    )
    schema["$defs"]["DraftObligationReference"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def serialize_ai_coverage_candidate_manifest_v2() -> str:
    return (
        json.dumps(
            build_ai_coverage_candidate_manifest_v2().model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_ai_coverage_candidate_schema_v2() -> str:
    schema = AICoverageCandidateManifestV2.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:ai-coverage-candidates:v2"
    schema["properties"]["profile_id"]["const"] = OFFICIAL_BENCHMARK_PROFILE.profile_id
    schema["properties"]["profile_fingerprint"]["const"] = OFFICIAL_BENCHMARK_PROFILE.fingerprint
    schema["$defs"]["AICoverageCandidateSuggestionV2"]["properties"]["scenario_key"]["enum"] = (
        sorted(EVALUATION_CONTRACTS)
    )
    schema["$defs"]["DraftObligationReference"]["properties"]["scenario_key"]["enum"] = sorted(
        EVALUATION_CONTRACTS
    )
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_ai_draft_human_review_packet_v1() -> str:
    """Render a deterministic worksheet; it never promotes a suggestion into corpus source."""
    manifest = build_ai_draft_seed_manifest_v1()
    lines = [
        "# 구조화 NLU AI 초안 사람 작성 작업지 V1",
        "",
        "> 이 문서는 16개 AI 제안을 검토하기 위한 읽기·작성 양식입니다.",
        "> 공식 골든 corpus, 검수 원장 또는 사람 승인 증거가 아닙니다.",
        "",
        f"- 작업지 버전: `{AI_DRAFT_REVIEW_PACKET_VERSION}`",
        f"- 평가 프로필: `{manifest.profile_id}`",
        f"- 프로필 지문: `{manifest.profile_fingerprint}`",
        f"- AI 제안 수: `{len(manifest.suggestions)}`",
        "",
        "## 작성 규칙",
        "",
        "1. AI 문장을 그대로 복사하지 말고 참고만 한 뒤 사람이 새 문장을 작성합니다.",
        "2. 현재 상태·intent·user_action·필드·태그를 작성 지침과 라이브 계약에 맞춰 다시 확인합니다.",
        "3. 채택하지 않을 제안은 `거부`로 표시하고 이유를 남깁니다.",
        "4. 작성이 끝난 항목도 곧바로 `adjudicated`가 되지 않습니다. 별도 검수 원장을 거쳐야 합니다.",
        "5. 이 커밋된 원본 양식은 직접 편집하지 말고 작업용 사본에 답을 작성합니다.",
        "",
    ]
    for index, suggestion in enumerate(manifest.suggestions, start=1):
        proposed = suggestion.proposed_case
        proposed_label = json.dumps(
            {
                "intent": proposed.labels.intent,
                "fields": proposed.labels.model_dump(mode="json")["fields"],
                "user_action": proposed.labels.user_action,
                "change_field": proposed.labels.change_field,
                "tags": [tag.value for tag in proposed.tags],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        lines.extend(
            [
                f"## {index:02d}. {suggestion.scenario_key}",
                "",
                f"- 제안 ID: `{suggestion.suggestion_id}`",
                f"- 기준 의무: `{suggestion.primary_obligation.dimension.value}` "
                f"/ `{suggestion.primary_obligation.value}`",
                f"- 현재 상태: `{proposed.conversation_state}`",
                f"- AI 제안 발화: “{proposed.user_message}”",
                "- AI 제안 정답:",
                "",
                "```json",
                proposed_label,
                "```",
                "",
                "### 사람 작성란",
                "",
                "- 판단: [ ] 참고 후 새로 작성  [ ] 거부",
                "- 새 `conversation_group_id`: `{{직접 작성}}`",
                "- 새 case ID: `{{직접 작성}}`",
                "- 사람이 새로 작성한 발화:",
                "  > {{AI 문장과 다른 표현을 직접 작성}}",
                "- 최종 정답 또는 수정 사항:",
                "  > {{intent·action·fields·tags를 확인해 작성}}",
                "- 판단 근거:",
                "  > {{현재 상태와 작성 지침을 근거로 작성}}",
                "- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_ai_subagent_human_review_packet_v1() -> str:
    """Render subagent alternatives as a review aid, never as human-authored source."""
    manifest = build_ai_subagent_candidate_manifest_v1()
    lines = [
        "# 구조화 NLU 서브 에이전트 후보 사람 작성 작업지 V1",
        "",
        "> 이 문서의 후보와 판단 근거도 AI가 작성했습니다.",
        "> 그대로 복사하면 human_authored 골든 데이터가 될 수 없습니다.",
        "",
        f"- 작업지 버전: `{AI_SUBAGENT_REVIEW_PACKET_VERSION}`",
        f"- 후보 묶음: `{manifest.candidate_set_id}`",
        f"- 평가 프로필: `{manifest.profile_id}`",
        f"- 프로필 지문: `{manifest.profile_fingerprint}`",
        f"- 서브 에이전트 후보 수: `{len(manifest.suggestions)}`",
        "- 자동 승격 허용: `false`",
        "",
        "## 작성 규칙",
        "",
        "1. 후보 문장과 근거는 참고만 하고 사람이 새 표현과 판단 근거를 직접 작성합니다.",
        "2. 원래 AI seed와 서브 에이전트 후보 어느 쪽도 그대로 복사하지 않습니다.",
        "3. 사람이 작성한 결과는 별도 AuthoringGroup source와 검수 원장에서 다시 확인합니다.",
        "4. 이 작업지를 채웠다는 사실만으로 draft·reviewed·adjudicated 상태가 되지 않습니다.",
        "",
    ]
    for index, suggestion in enumerate(manifest.suggestions, start=1):
        proposed = suggestion.proposed_case
        proposed_label = json.dumps(
            {
                "intent": proposed.labels.intent,
                "fields": proposed.labels.model_dump(mode="json")["fields"],
                "user_action": proposed.labels.user_action,
                "change_field": proposed.labels.change_field,
                "tags": [tag.value for tag in proposed.tags],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        lines.extend(
            [
                f"## {index:02d}. {suggestion.scenario_key}",
                "",
                f"- 후보 ID: `{suggestion.suggestion_id}`",
                f"- 원본 제안 ID: `{suggestion.source_suggestion_id}`",
                f"- 기준 의무: `{suggestion.primary_obligation.dimension.value}` "
                f"/ `{suggestion.primary_obligation.value}`",
                f"- 현재 상태: `{proposed.conversation_state}`",
                f"- 서브 에이전트 후보 발화: “{proposed.user_message}”",
                f"- 서브 에이전트 판단 근거: {suggestion.drafting_rationale}",
                "- 제안 정답:",
                "",
                "```json",
                proposed_label,
                "```",
                "",
                "### 사람 작성란",
                "",
                "- 판단: [ ] 참고 후 새로 작성  [ ] 거부",
                "- 새 `conversation_group_id`: `{{직접 작성}}`",
                "- 새 case ID: `{{직접 작성}}`",
                "- 사람이 새로 작성한 발화:",
                "  > {{위 후보와 다른 표현을 직접 작성}}",
                "- 최종 정답 또는 수정 사항:",
                "  > {{intent·action·fields·tags를 확인해 작성}}",
                "- 사람이 작성한 판단 근거:",
                "  > {{현재 상태와 작성 지침을 근거로 직접 작성}}",
                "- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_ai_coverage_candidate_review_packet_v1() -> str:
    """Render coverage candidates as a review aid, never as official corpus source."""
    manifest = build_ai_coverage_candidate_manifest_v1()
    lines = [
        "# 구조화 NLU 커버리지 후보 검토 작업지 V1",
        "",
        "> 이 문서의 발화와 정답은 AI가 작성한 미검수 후보입니다.",
        "> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.",
        "> 커밋된 원본은 직접 체크하지 말고 작업용 사본에서 판단을 기록합니다.",
        "> 작업용 사본의 체크는 비공식 검토 메모이며 별도 승인 원장이나 adjudication이 아닙니다.",
        "",
        f"- 작업지 버전: `{AI_COVERAGE_CANDIDATE_REVIEW_PACKET_VERSION}`",
        f"- 후보 묶음: `{manifest.candidate_set_id}`",
        f"- 기준 source: `{manifest.baseline_source_root}`",
        f"- 기준 split 원장: `{manifest.baseline_split_assignment_path}`",
        f"- 기준 case 수: `{manifest.baseline_case_count}`",
        f"- 기준 corpus 지문: `{manifest.baseline_corpus_fingerprint}`",
        f"- 기준 충족 의무: `{manifest.baseline_covered_obligation_count}`",
        f"- 투영 추가 충족 의무: `{manifest.projected_marginal_gain}`",
        f"- 투영 충족 의무: `{manifest.projected_covered_obligation_count}`",
        f"- 전체 의무: `{manifest.official_obligation_count}`",
        "- 자동 승격 허용: `false`",
        "",
    ]
    for index, suggestion in enumerate(manifest.suggestions, start=1):
        proposed = suggestion.proposed_case
        proposed_payload = json.dumps(
            {
                "conversation_state": proposed.conversation_state,
                "current_fields": proposed.current_fields,
                "offered_alternative_times": proposed.offered_alternative_times,
                "intent": proposed.labels.intent,
                "fields": proposed.labels.model_dump(mode="json")["fields"],
                "user_action": proposed.labels.user_action,
                "change_field": proposed.labels.change_field,
                "tags": [tag.value for tag in proposed.tags],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        lines.extend(
            [
                f"## {index:02d}. {suggestion.scenario_key} / {suggestion.target_field}",
                "",
                f"- 후보 ID: `{suggestion.suggestion_id}`",
                f"- 기준 의무: `field_present` / `{suggestion.target_field}`",
                f"- 기준 시점 미충족: `{str(suggestion.baseline_obligation_missing).lower()}`",
                f"- 라이브 의미 계약 통과: `{str(suggestion.semantic_valid).lower()}`",
                f"- AI 후보 발화: “{proposed.user_message}”",
                "- 제안 입력·정답:",
                "",
                "```json",
                proposed_payload,
                "```",
                "",
                "- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부",
                "- 수정안 또는 판단 근거:",
                "  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_ai_coverage_candidate_review_packet_v2() -> str:
    """Render the V2 delta batch without changing the immutable V1 worksheet."""
    manifest = build_ai_coverage_candidate_manifest_v2()
    lines = [
        "# 구조화 NLU 커버리지 후보 검토 작업지 V2",
        "",
        "> 이 문서의 4개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.",
        "> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.",
        "> 커밋된 원본은 직접 체크하지 말고 작업용 사본에서 판단을 기록합니다.",
        "",
        f"- 작업지 버전: `{AI_COVERAGE_CANDIDATE_REVIEW_PACKET_VERSION_V2}`",
        f"- 후보 묶음: `{manifest.candidate_set_id}`",
        f"- 선행 후보 묶음: `{manifest.predecessor_candidate_set_id}`",
        f"- 기준 진단 case 수: `{len(manifest.baseline_diagnostic_case_ids)}`",
        f"- 기준 충족/미충족 의무: `{manifest.baseline_covered_obligation_count}` / "
        f"`{manifest.baseline_missing_obligation_count}`",
        f"- 투영 추가 충족 의무: `{manifest.projected_marginal_gain}`",
        f"- 투영 충족/미충족 의무: `{manifest.projected_covered_obligation_count}` / "
        f"`{manifest.projected_missing_obligation_count}`",
        "- 자동 승격 허용: `false`",
        "",
    ]
    for index, suggestion in enumerate(manifest.suggestions, start=1):
        proposed = suggestion.proposed_case
        payload = json.dumps(
            {
                "conversation_state": proposed.conversation_state,
                "current_fields": proposed.current_fields,
                "offered_alternative_times": proposed.offered_alternative_times,
                "labels": proposed.labels.model_dump(mode="json"),
                "tags": [tag.value for tag in proposed.tags],
                "projected_obligations": [
                    {
                        "dimension": item.dimension.value,
                        "value": item.value,
                    }
                    for item in suggestion.projected_obligations
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        lines.extend(
            [
                f"## {index:02d}. {suggestion.scenario_key} / {suggestion.target_field}",
                "",
                f"- 후보 ID: `{suggestion.suggestion_id}`",
                f"- 기준 의무: `current_field_present` / `{suggestion.target_field}`",
                f"- AI 후보 발화: “{proposed.user_message}”",
                "- 제안 입력·정답·투영 의무:",
                "",
                "```json",
                payload,
                "```",
                "",
                "- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부",
                "- 수정안 또는 판단 근거:",
                "  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
