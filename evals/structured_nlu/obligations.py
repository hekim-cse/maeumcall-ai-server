from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    CoverageDimension,
)


@dataclass(frozen=True)
class AuthoringObligation:
    """Represent one contract-derived item that the corpus must exercise."""

    dimension: CoverageDimension
    value: str
    scenario_key: str | None = None


def serialize_official_authoring_obligations() -> str:
    obligations = build_official_authoring_obligations()
    payload = {
        "profile_id": OFFICIAL_BENCHMARK_PROFILE.profile_id,
        "profile_fingerprint": OFFICIAL_BENCHMARK_PROFILE.fingerprint,
        "obligation_count": len(obligations),
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
    obligations.extend(
        AuthoringObligation(
            dimension=CoverageDimension.DIFFICULTY_TAG,
            value=tag.value,
        )
        for tag in sorted(OFFICIAL_BENCHMARK_PROFILE.required_tags, key=lambda tag: tag.value)
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
