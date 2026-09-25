from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass

from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    CoverageDimension,
)
from evals.structured_nlu.contrast import contrast_role_obligations
from evals.structured_nlu.coverage_v3 import OFFICIAL_COVERAGE_CONTRACT_V3


@dataclass(frozen=True)
class AuthoringObligation:
    """Represent one contract-derived item that the corpus must exercise."""

    dimension: CoverageDimension
    value: str
    scenario_key: str | None = None


def serialize_official_authoring_obligations() -> str:
    obligations = build_official_authoring_obligations()
    dimension_counts = Counter(obligation.dimension.value for obligation in obligations)
    scenario_counts = Counter(
        obligation.scenario_key for obligation in obligations if obligation.scenario_key is not None
    )
    payload = {
        "profile_id": OFFICIAL_BENCHMARK_PROFILE.profile_id,
        "profile_fingerprint": OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        "obligation_count": len(obligations),
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "obligations": [
            {
                **asdict(obligation),
                "dimension": obligation.dimension.value,
            }
            for obligation in obligations
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_official_authoring_obligations() -> tuple[AuthoringObligation, ...]:
    """Derive authoring requirements from the fixed live-contract profile."""
    obligations: list[AuthoringObligation] = []
    for scenario_key, requirement in OFFICIAL_BENCHMARK_PROFILE.scenarios:
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.STATE_ACTION,
                scenario_key=scenario_key,
                value=f"{state}->{action}",
            )
            for state, actions in requirement.actions_by_state
            for action in sorted(actions)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.INTENT,
                scenario_key=scenario_key,
                value="<null>" if intent is None else intent,
            )
            for intent in sorted(
                requirement.allowed_intents,
                key=lambda value: "" if value is None else value,
            )
        )
        for dimension in (
            CoverageDimension.FIELD_PRESENT,
            CoverageDimension.FIELD_ABSENT,
        ):
            obligations.extend(
                AuthoringObligation(
                    dimension=dimension,
                    scenario_key=scenario_key,
                    value=field_name,
                )
                for field_name in sorted(requirement.fields)
            )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.FIELD_OPTION,
                scenario_key=scenario_key,
                value=f"{field_name}={option}",
            )
            for field_name, options in requirement.field_options
            for option in sorted(options)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.CHANGE_FIELD,
                scenario_key=scenario_key,
                value=field_name,
            )
            for field_name in sorted(requirement.change_fields)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.ACTION_FIELD_PRESENT,
                scenario_key=scenario_key,
                value=value,
            )
            for value in sorted(requirement.action_field_present)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.ACTION_FIELD_ABSENT,
                scenario_key=scenario_key,
                value=value,
            )
            for value in sorted(requirement.action_field_absent)
        )
    for scenario_key, policy in OFFICIAL_COVERAGE_CONTRACT_V3.scenarios:
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.SCENARIO_DIFFICULTY_TAG,
                scenario_key=scenario_key,
                value=tag.value,
            )
            for tag in sorted(policy.applicable_tags, key=lambda tag: tag.value)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.CURRENT_FIELDS_CONTEXT,
                scenario_key=scenario_key,
                value=f"{state}->{context.value}",
            )
            for state, contexts in policy.current_contexts_by_state
            for context in sorted(contexts, key=lambda item: item.value)
        )
        for dimension in (
            CoverageDimension.CURRENT_FIELD_PRESENT,
            CoverageDimension.CURRENT_FIELD_ABSENT,
        ):
            obligations.extend(
                AuthoringObligation(
                    dimension=dimension,
                    scenario_key=scenario_key,
                    value=field_name,
                )
                for field_name in sorted(policy.current_field_names)
            )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.CURRENT_FIELD_OPTION,
                scenario_key=scenario_key,
                value=f"{field_name}={value}",
            )
            for field_name, values in policy.current_field_options
            for value in sorted(values)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.CURRENT_DELTA_RELATION,
                scenario_key=scenario_key,
                value=f"{field_name}->{relation.value}",
            )
            for field_name, relations in policy.current_delta_relations
            for relation in sorted(relations, key=lambda item: item.value)
        )
        obligations.extend(
            AuthoringObligation(
                dimension=CoverageDimension.ALTERNATIVE_TIME_RELATION,
                scenario_key=scenario_key,
                value=f"{state}->{action}->{relation.value}",
            )
            for state, action, relations in policy.alternative_relations_by_state_action
            for relation in sorted(relations, key=lambda item: item.value)
        )
    obligations.extend(
        AuthoringObligation(
            dimension=CoverageDimension.CONTRAST_ROLE,
            value=value,
        )
        for value in sorted(contrast_role_obligations())
    )
    return tuple(
        sorted(
            obligations,
            key=lambda obligation: (
                "" if obligation.scenario_key is None else obligation.scenario_key,
                obligation.dimension.value,
                obligation.value,
            ),
        )
    )
