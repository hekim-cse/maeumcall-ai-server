from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS, EvaluationContract
from evals.structured_nlu.semantics import DifficultyTag

COVERAGE_CONTRACT_V3_ID = "maeumcall-structured-nlu-coverage-v3"


class CurrentFieldsContext(StrEnum):
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"
    GUARDED_PARTIAL = "guarded_partial"
    GUARDED_COMPLETE = "guarded_complete"


class CurrentDeltaRelation(StrEnum):
    CURRENT_VALUE_NOT_REEMITTED = "current_value_not_reemitted"
    MISSING_VALUE_PROVIDED = "missing_value_provided"
    EXISTING_VALUE_REPLACED = "existing_value_replaced"
    EXISTING_VALUE_CLEARED = "existing_value_cleared"


class AlternativeTimeRelation(StrEnum):
    NO_OFFERS = "no_offers"
    OFFERS_UNSELECTED = "offers_unselected"
    SELECTED_OFFER = "selected_offer"


@dataclass(frozen=True)
class ScenarioCoveragePolicyV3:
    applicable_tags: frozenset[DifficultyTag]
    current_contexts_by_state: tuple[tuple[str, frozenset[CurrentFieldsContext]], ...]
    current_field_names: frozenset[str]
    current_field_options: tuple[tuple[str, frozenset[str]], ...]
    current_delta_relations: tuple[tuple[str, frozenset[CurrentDeltaRelation]], ...]
    alternative_relations_by_state_action: tuple[
        tuple[str, str, frozenset[AlternativeTimeRelation]], ...
    ]


@dataclass(frozen=True)
class CoverageContractV3:
    contract_id: str
    scenarios: tuple[tuple[str, ScenarioCoveragePolicyV3], ...]
    classifier_algorithms: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_id != COVERAGE_CONTRACT_V3_ID:
            raise ValueError("coverage contract id does not match V3")
        scenario_keys = [scenario_key for scenario_key, _ in self.scenarios]
        if set(scenario_keys) != set(EVALUATION_CONTRACTS):
            raise ValueError("coverage V3 scenarios must exactly match the live contracts")
        if len(scenario_keys) != len(set(scenario_keys)):
            raise ValueError("coverage V3 scenarios must be unique")
        for scenario_key, policy in self.scenarios:
            _validate_scenario_policy(scenario_key, policy)

    @property
    def scenario_policies(self) -> dict[str, ScenarioCoveragePolicyV3]:
        return dict(self.scenarios)

    @property
    def canonical_payload(self) -> str:
        payload = {
            "contract_id": self.contract_id,
            "classifier_algorithms": sorted(self.classifier_algorithms),
            "scenarios": {
                scenario_key: {
                    "applicable_tags": sorted(tag.value for tag in policy.applicable_tags),
                    "current_contexts_by_state": {
                        state: sorted(context.value for context in contexts)
                        for state, contexts in policy.current_contexts_by_state
                    },
                    "current_field_names": sorted(policy.current_field_names),
                    "current_field_options": {
                        field_name: sorted(values)
                        for field_name, values in policy.current_field_options
                    },
                    "current_delta_relations": {
                        field_name: sorted(relation.value for relation in relations)
                        for field_name, relations in policy.current_delta_relations
                    },
                    "alternative_relations_by_state_action": [
                        {
                            "state": state,
                            "action": action,
                            "relations": sorted(relation.value for relation in relations),
                        }
                        for state, action, relations in policy.alternative_relations_by_state_action
                    ],
                }
                for scenario_key, policy in self.scenarios
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_payload.encode("utf-8")).hexdigest()


_COMMON_TAGS = frozenset(
    {
        DifficultyTag.SINGLE_FIELD,
        DifficultyTag.MULTI_FIELD,
        DifficultyTag.NEGATION,
        DifficultyTag.ELLIPSIS,
        DifficultyTag.COLLOQUIAL,
        DifficultyTag.AMBIGUOUS,
        DifficultyTag.HARD_NEGATIVE,
    }
)


def _build_coverage_contract_v3() -> CoverageContractV3:
    policies = tuple(
        (scenario_key, _build_scenario_policy(contract))
        for scenario_key, contract in sorted(EVALUATION_CONTRACTS.items())
    )
    return CoverageContractV3(
        contract_id=COVERAGE_CONTRACT_V3_ID,
        scenarios=policies,
        classifier_algorithms=(
            "current-fields-context-exact-v1",
            "current-delta-relation-exact-v1",
            "alternative-time-relation-exact-v1",
            "scenario-difficulty-applicability-v1",
        ),
    )


def _build_scenario_policy(contract: EvaluationContract) -> ScenarioCoveragePolicyV3:
    applicable_tags = set(_COMMON_TAGS)
    applicable_tags.update(
        tag for _, objective_tags in contract.objective_tags_by_action for tag in objective_tags
    )
    if contract.scenario_key == "고객센터:a/s 접수":
        applicable_tags.add(DifficultyTag.SAFETY)

    if contract.workflow_spec is None:
        current_contexts: tuple[tuple[str, frozenset[CurrentFieldsContext]], ...] = ()
        current_names = frozenset()
        current_options: tuple[tuple[str, frozenset[str]], ...] = ()
        current_relations: tuple[tuple[str, frozenset[CurrentDeltaRelation]], ...] = ()
    else:
        spec = contract.workflow_spec
        contexts: dict[str, frozenset[CurrentFieldsContext]] = {
            "greeting": frozenset({CurrentFieldsContext.EMPTY}),
            spec.collecting_state: frozenset(
                {CurrentFieldsContext.EMPTY, CurrentFieldsContext.PARTIAL}
            ),
            spec.confirming_state: frozenset({CurrentFieldsContext.COMPLETE}),
            spec.ready_state: frozenset({CurrentFieldsContext.COMPLETE}),
            spec.completed_state: frozenset({CurrentFieldsContext.COMPLETE}),
            "cancelled": frozenset(
                {
                    CurrentFieldsContext.EMPTY,
                    CurrentFieldsContext.PARTIAL,
                    CurrentFieldsContext.COMPLETE,
                }
            ),
            "closing": frozenset(
                {
                    CurrentFieldsContext.EMPTY,
                    CurrentFieldsContext.PARTIAL,
                    CurrentFieldsContext.COMPLETE,
                }
            ),
        }
        if spec.guards:
            for guard in spec.guards:
                contexts[guard.state] = frozenset(
                    {
                        CurrentFieldsContext.GUARDED_PARTIAL,
                        CurrentFieldsContext.GUARDED_COMPLETE,
                    }
                )
            contexts["closing"] = contexts["closing"] | frozenset(
                {
                    CurrentFieldsContext.GUARDED_PARTIAL,
                    CurrentFieldsContext.GUARDED_COMPLETE,
                }
            )
        current_contexts = tuple((state, contexts[state]) for state in sorted(contexts))
        current_names = frozenset(contract.field_names)
        current_options = contract.field_options
        current_relations = tuple(
            (
                field_name,
                frozenset(
                    {
                        CurrentDeltaRelation.CURRENT_VALUE_NOT_REEMITTED,
                        CurrentDeltaRelation.MISSING_VALUE_PROVIDED,
                        CurrentDeltaRelation.EXISTING_VALUE_REPLACED,
                        CurrentDeltaRelation.EXISTING_VALUE_CLEARED,
                    }
                ),
            )
            for field_name in contract.field_names
        )

    alternative_relations = []
    actions_by_state = dict(contract.actions_by_state)
    for state in sorted(contract.alternative_states):
        for action in sorted(actions_by_state[state]):
            if action == "select_alternative_time":
                relations = frozenset({AlternativeTimeRelation.SELECTED_OFFER})
            else:
                relations = frozenset(
                    {
                        AlternativeTimeRelation.NO_OFFERS,
                        AlternativeTimeRelation.OFFERS_UNSELECTED,
                    }
                )
            alternative_relations.append((state, action, relations))

    return ScenarioCoveragePolicyV3(
        applicable_tags=frozenset(applicable_tags),
        current_contexts_by_state=current_contexts,
        current_field_names=current_names,
        current_field_options=current_options,
        current_delta_relations=current_relations,
        alternative_relations_by_state_action=tuple(alternative_relations),
    )


def _validate_scenario_policy(
    scenario_key: str,
    policy: ScenarioCoveragePolicyV3,
) -> None:
    contract = EVALUATION_CONTRACTS[scenario_key]
    if not policy.applicable_tags:
        raise ValueError(f"coverage V3 requires difficulty tags: {scenario_key}")
    if contract.workflow_spec is None:
        if any(
            (
                policy.current_contexts_by_state,
                policy.current_field_names,
                policy.current_field_options,
                policy.current_delta_relations,
            )
        ):
            raise ValueError(
                f"non-workflow scenario declares current context policy: {scenario_key}"
            )
    else:
        if policy.current_field_names != frozenset(contract.field_names):
            raise ValueError(
                f"coverage V3 current fields differ from live contract: {scenario_key}"
            )
        if policy.current_field_options != contract.field_options:
            raise ValueError(
                f"coverage V3 current options differ from live contract: {scenario_key}"
            )
        if set(dict(policy.current_contexts_by_state)) - contract.conversation_states:
            raise ValueError(f"coverage V3 context state exceeds live contract: {scenario_key}")

    expected_alternative_pairs = {
        (state, action)
        for state in contract.alternative_states
        for action in contract.allowed_actions_for_state(state)
    }
    actual_alternative_pairs = {
        (state, action) for state, action, _ in policy.alternative_relations_by_state_action
    }
    if actual_alternative_pairs != expected_alternative_pairs:
        raise ValueError(
            f"coverage V3 alternative relations differ from live contract: {scenario_key}"
        )


OFFICIAL_COVERAGE_CONTRACT_V3 = _build_coverage_contract_v3()


def classify_current_fields_context(
    contract: EvaluationContract,
    *,
    conversation_state: str,
    current_fields: dict[str, str | None],
) -> CurrentFieldsContext | None:
    """Classify a validated workflow snapshot without numeric thresholds."""
    spec = contract.workflow_spec
    if spec is None:
        return None
    present_count = sum(value is not None for value in current_fields.values())
    if present_count == 0:
        return CurrentFieldsContext.EMPTY
    guarded = spec.guard_for_state(conversation_state) is not None or (
        conversation_state == "closing" and spec.matching_guard(current_fields) is not None
    )
    if present_count == len(current_fields):
        return CurrentFieldsContext.GUARDED_COMPLETE if guarded else CurrentFieldsContext.COMPLETE
    return CurrentFieldsContext.GUARDED_PARTIAL if guarded else CurrentFieldsContext.PARTIAL


def classify_alternative_time_relation(
    *,
    offered_alternative_times: tuple[str, ...],
    selected_time: str | None,
) -> AlternativeTimeRelation:
    if selected_time is not None:
        if selected_time not in offered_alternative_times:
            raise ValueError("selected alternative must exactly match a server offer")
        return AlternativeTimeRelation.SELECTED_OFFER
    if offered_alternative_times:
        return AlternativeTimeRelation.OFFERS_UNSELECTED
    return AlternativeTimeRelation.NO_OFFERS


def observed_current_delta_relations(
    *,
    current_fields: dict[str, str | None],
    output_fields: dict[str, str | None],
    user_action: str,
    change_field: str | None,
) -> frozenset[str]:
    """Return exact field relations exercised by one workflow case."""
    observed = {
        f"{field_name}->{CurrentDeltaRelation.CURRENT_VALUE_NOT_REEMITTED.value}"
        for field_name, current_value in current_fields.items()
        if current_value is not None and output_fields[field_name] is None
    }
    if user_action == "provide_details":
        observed.update(
            f"{field_name}->{CurrentDeltaRelation.MISSING_VALUE_PROVIDED.value}"
            for field_name, value in output_fields.items()
            if current_fields[field_name] is None and value is not None
        )
    if user_action == "change_detail" and change_field is not None:
        relation = (
            CurrentDeltaRelation.EXISTING_VALUE_REPLACED
            if output_fields[change_field] is not None
            else CurrentDeltaRelation.EXISTING_VALUE_CLEARED
        )
        observed.add(f"{change_field}->{relation.value}")
    return frozenset(observed)
