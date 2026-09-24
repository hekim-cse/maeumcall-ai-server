from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.metrics import EvaluationScores, score_predictions
from evals.structured_nlu.schema import (
    CasePrediction,
    DatasetSplit,
    DifficultyTag,
    EvaluationCase,
    GoldDataset,
    ReviewStatus,
)


class CoverageDimension(StrEnum):
    REVIEW_STATUS = "review_status"
    SCENARIO = "scenario"
    CONVERSATION_STATE = "conversation_state"
    USER_ACTION = "user_action"
    STATE_ACTION = "state_action"
    INTENT = "intent"
    FIELD_PRESENT = "field_present"
    FIELD_ABSENT = "field_absent"
    FIELD_OPTION = "field_option"
    CHANGE_FIELD = "change_field"
    DIFFICULTY_TAG = "difficulty_tag"


@dataclass(frozen=True)
class ScenarioCoverageRequirement:
    conversation_states: frozenset[str]
    user_actions: frozenset[str]
    fields: frozenset[str]
    change_fields: frozenset[str]
    allowed_intents: frozenset[str | None]
    actions_by_state: tuple[tuple[str, frozenset[str]], ...]
    field_options: tuple[tuple[str, frozenset[str]], ...]


@dataclass(frozen=True)
class BenchmarkProfile:
    profile_id: str
    scenarios: tuple[tuple[str, ScenarioCoverageRequirement], ...]
    required_tags: frozenset[DifficultyTag]

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be blank")
        scenario_keys = [scenario_key for scenario_key, _ in self.scenarios]
        if not scenario_keys or len(set(scenario_keys)) != len(scenario_keys):
            raise ValueError("benchmark profile scenarios must be non-empty and unique")
        unknown_scenarios = set(scenario_keys) - set(EVALUATION_CONTRACTS)
        if unknown_scenarios:
            raise ValueError(f"benchmark profile contains unknown scenarios: {unknown_scenarios}")
        for scenario_key, requirement in self.scenarios:
            contract = EVALUATION_CONTRACTS[scenario_key]
            if not requirement.conversation_states:
                raise ValueError(f"profile requires no conversation states: {scenario_key}")
            if not requirement.conversation_states <= contract.conversation_states:
                raise ValueError(f"profile states exceed the live contract: {scenario_key}")
            if not requirement.user_actions <= contract.user_actions:
                raise ValueError(f"profile actions exceed the live contract: {scenario_key}")
            declared_states = [state for state, _ in requirement.actions_by_state]
            if len(declared_states) != len(set(declared_states)):
                raise ValueError(f"profile state-action states must be unique: {scenario_key}")
            required_actions_by_state = dict(requirement.actions_by_state)
            if set(required_actions_by_state) != set(requirement.conversation_states):
                raise ValueError(f"profile state-action mapping is incomplete: {scenario_key}")
            for state, actions in required_actions_by_state.items():
                if not actions <= contract.allowed_actions_for_state(state):
                    raise ValueError(
                        f"profile state actions exceed the live contract: {scenario_key}"
                    )
            declared_actions = frozenset().union(*required_actions_by_state.values())
            if declared_actions != requirement.user_actions:
                raise ValueError(f"profile state actions differ from user actions: {scenario_key}")
            actions_in_required_states = frozenset().union(
                *(
                    contract.allowed_actions_for_state(state)
                    for state in requirement.conversation_states
                )
            )
            if not requirement.user_actions <= actions_in_required_states:
                raise ValueError(
                    f"profile actions cannot occur in the required states: {scenario_key}"
                )
            if not requirement.fields <= set(contract.field_names):
                raise ValueError(f"profile fields exceed the live contract: {scenario_key}")
            if not requirement.change_fields <= set(contract.field_names):
                raise ValueError(f"profile change fields exceed the live contract: {scenario_key}")
            if requirement.change_fields and not contract.uses_current_fields:
                raise ValueError(f"change fields are unsupported for the scenario: {scenario_key}")
            if (
                not requirement.allowed_intents
                or not requirement.allowed_intents <= contract.allowed_intents
            ):
                raise ValueError(f"profile intents exceed the live contract: {scenario_key}")
            contract_options = dict(contract.field_options)
            for field_name, values in requirement.field_options:
                if field_name not in requirement.fields or values != contract_options.get(
                    field_name
                ):
                    raise ValueError(
                        f"profile field options differ from the live contract: {scenario_key}"
                    )

    @property
    def scenario_requirements(self) -> dict[str, ScenarioCoverageRequirement]:
        return dict(self.scenarios)

    @property
    def fingerprint(self) -> str:
        payload = {
            "profile_id": self.profile_id,
            "required_tags": sorted(tag.value for tag in self.required_tags),
            "scenarios": {
                scenario_key: {
                    "conversation_states": sorted(requirement.conversation_states),
                    "user_actions": sorted(requirement.user_actions),
                    "fields": sorted(requirement.fields),
                    "change_fields": sorted(requirement.change_fields),
                    "allowed_intents": sorted(
                        "<null>" if intent is None else intent
                        for intent in requirement.allowed_intents
                    ),
                    "actions_by_state": {
                        state: sorted(actions)
                        for state, actions in sorted(requirement.actions_by_state)
                    },
                    "field_options": {
                        field_name: sorted(values)
                        for field_name, values in sorted(requirement.field_options)
                    },
                }
                for scenario_key, requirement in sorted(self.scenarios)
            },
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CoverageIssue:
    dimension: CoverageDimension
    missing_values: tuple[str, ...]
    scenario_key: str | None = None


@dataclass(frozen=True)
class BenchmarkCoverageReport:
    profile_id: str
    profile_fingerprint: str
    split: DatasetSplit
    case_count: int
    issues: tuple[CoverageIssue, ...]

    @property
    def is_complete(self) -> bool:
        return not self.issues

    def require_complete(self) -> None:
        if self.is_complete:
            return
        details = "; ".join(_format_issue(issue) for issue in self.issues)
        raise ValueError(f"benchmark coverage is incomplete: {details}")


@dataclass(frozen=True)
class BenchmarkSlice:
    profile_id: str
    profile_fingerprint: str
    dataset_version: int
    state_contract_version: int
    dataset_fingerprint: str
    split: DatasetSplit
    cases: tuple[EvaluationCase, ...]
    coverage: BenchmarkCoverageReport


@dataclass(frozen=True)
class QualifiedTestSlice(BenchmarkSlice):
    corpus_fingerprint: str
    corpus_cases: tuple[EvaluationCase, ...]


def _build_official_profile() -> BenchmarkProfile:
    scenarios = []
    for scenario_key, contract in EVALUATION_CONTRACTS.items():
        scenarios.append(
            (
                scenario_key,
                ScenarioCoverageRequirement(
                    conversation_states=contract.conversation_states,
                    user_actions=contract.user_actions,
                    fields=frozenset(contract.field_names),
                    change_fields=(
                        frozenset(contract.field_names)
                        if contract.uses_current_fields
                        else frozenset()
                    ),
                    allowed_intents=contract.allowed_intents,
                    actions_by_state=contract.actions_by_state,
                    field_options=contract.field_options,
                ),
            )
        )
    return BenchmarkProfile(
        profile_id="maeumcall-structured-nlu-v1",
        scenarios=tuple(scenarios),
        required_tags=frozenset(DifficultyTag),
    )


OFFICIAL_BENCHMARK_PROFILE = _build_official_profile()
OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT = (
    "bc7a053b09ee97a18ecf9eb11964d48008b5db208cb8012c1ae7d5c4bb932b93"
)
if OFFICIAL_BENCHMARK_PROFILE.fingerprint != OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT:
    raise RuntimeError("official benchmark profile changed; create a new version and fingerprint")


def inspect_benchmark_coverage(
    dataset: GoldDataset,
    *,
    split: DatasetSplit,
    profile: BenchmarkProfile = OFFICIAL_BENCHMARK_PROFILE,
) -> BenchmarkCoverageReport:
    cases = tuple(case for case in dataset.cases if case.split is split)
    issues: list[CoverageIssue] = []
    unapproved_ids = sorted(
        case.id for case in cases if case.review_status is not ReviewStatus.ADJUDICATED
    )
    if unapproved_ids:
        issues.append(
            CoverageIssue(
                dimension=CoverageDimension.REVIEW_STATUS,
                missing_values=tuple(unapproved_ids),
            )
        )

    requirements = profile.scenario_requirements
    covered_scenarios = {case.scenario_key for case in cases}
    missing_scenarios = sorted(set(requirements) - covered_scenarios)
    if missing_scenarios:
        issues.append(
            CoverageIssue(
                dimension=CoverageDimension.SCENARIO,
                missing_values=tuple(missing_scenarios),
            )
        )

    for scenario_key, requirement in requirements.items():
        scenario_cases = tuple(case for case in cases if case.scenario_key == scenario_key)
        if not scenario_cases:
            continue
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.CONVERSATION_STATE,
            required=requirement.conversation_states,
            covered={case.conversation_state for case in scenario_cases},
            scenario_key=scenario_key,
        )
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.USER_ACTION,
            required=requirement.user_actions,
            covered={case.labels.user_action for case in scenario_cases},
            scenario_key=scenario_key,
        )
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.STATE_ACTION,
            required=frozenset(
                f"{state}->{action}"
                for state, actions in requirement.actions_by_state
                for action in actions
            ),
            covered={
                f"{case.conversation_state}->{case.labels.user_action}" for case in scenario_cases
            },
            scenario_key=scenario_key,
        )
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.INTENT,
            required=frozenset(
                "<null>" if intent is None else intent for intent in requirement.allowed_intents
            ),
            covered={
                "<null>" if case.labels.intent is None else case.labels.intent
                for case in scenario_cases
            },
            scenario_key=scenario_key,
        )

        present_fields = {
            field_name
            for case in scenario_cases
            for field_name, expected in case.labels.fields.items()
            if expected is not None
        }
        absent_fields = {
            field_name
            for case in scenario_cases
            for field_name, expected in case.labels.fields.items()
            if expected is None
        }
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.FIELD_PRESENT,
            required=requirement.fields,
            covered=present_fields,
            scenario_key=scenario_key,
        )
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.FIELD_ABSENT,
            required=requirement.fields,
            covered=absent_fields,
            scenario_key=scenario_key,
        )
        required_options = frozenset(
            f"{field_name}={value}"
            for field_name, values in requirement.field_options
            for value in values
        )
        covered_options = {
            f"{field_name}={value}"
            for case in scenario_cases
            for field_name, expected in case.labels.fields.items()
            if expected is not None
            for value in expected.accepted_values
        }
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.FIELD_OPTION,
            required=required_options,
            covered=covered_options,
            scenario_key=scenario_key,
        )
        _append_missing_issue(
            issues,
            dimension=CoverageDimension.CHANGE_FIELD,
            required=requirement.change_fields,
            covered={
                case.labels.change_field
                for case in scenario_cases
                if case.labels.change_field is not None
            },
            scenario_key=scenario_key,
        )

    _append_missing_issue(
        issues,
        dimension=CoverageDimension.DIFFICULTY_TAG,
        required=frozenset(tag.value for tag in profile.required_tags),
        covered={tag.value for case in cases for tag in case.tags},
    )
    return BenchmarkCoverageReport(
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        split=split,
        case_count=len(cases),
        issues=tuple(issues),
    )


def prepare_benchmark_slice(
    dataset: GoldDataset,
    *,
    split: DatasetSplit,
    profile: BenchmarkProfile,
) -> BenchmarkSlice:
    report = inspect_benchmark_coverage(dataset, split=split, profile=profile)
    report.require_complete()
    cases = tuple(case for case in dataset.cases if case.split is split)
    return BenchmarkSlice(
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        dataset_version=dataset.dataset_version,
        state_contract_version=dataset.state_contract_version,
        dataset_fingerprint=_dataset_fingerprint(dataset, split=split),
        split=split,
        cases=cases,
        coverage=report,
    )


def prepare_qualified_test_slice(dataset: GoldDataset) -> QualifiedTestSlice:
    _require_complete_corpus(dataset)
    benchmark = prepare_benchmark_slice(
        dataset,
        split=DatasetSplit.TEST,
        profile=OFFICIAL_BENCHMARK_PROFILE,
    )
    return QualifiedTestSlice(
        **benchmark.__dict__,
        corpus_fingerprint=_corpus_fingerprint(dataset),
        corpus_cases=dataset.cases,
    )


def score_qualified_test_slice(
    benchmark: QualifiedTestSlice,
    predictions: tuple[CasePrediction, ...],
) -> EvaluationScores:
    if benchmark.split is not DatasetSplit.TEST:
        raise ValueError("qualified scoring requires the test split")
    if any(case.split is not DatasetSplit.TEST for case in benchmark.cases):
        raise ValueError("qualified test slice contains a non-test case")
    if benchmark.profile_id != OFFICIAL_BENCHMARK_PROFILE.profile_id:
        raise ValueError("qualified test profile id does not match")
    if benchmark.profile_fingerprint != OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT:
        raise ValueError("qualified test profile fingerprint does not match")
    corpus = GoldDataset(
        dataset_version=benchmark.dataset_version,
        state_contract_version=benchmark.state_contract_version,
        cases=benchmark.corpus_cases,
    )
    _require_complete_corpus(corpus)
    if benchmark.corpus_fingerprint != _corpus_fingerprint(corpus):
        raise ValueError("qualified test corpus fingerprint does not match")
    expected_test_cases = tuple(case for case in corpus.cases if case.split is DatasetSplit.TEST)
    if benchmark.cases != expected_test_cases:
        raise ValueError("qualified test cases do not match the complete corpus")
    if benchmark.dataset_fingerprint != _dataset_fingerprint(
        corpus,
        split=DatasetSplit.TEST,
    ):
        raise ValueError("qualified test dataset fingerprint does not match")
    coverage = inspect_benchmark_coverage(
        corpus,
        split=DatasetSplit.TEST,
        profile=OFFICIAL_BENCHMARK_PROFILE,
    )
    if benchmark.coverage != coverage:
        raise ValueError("qualified test coverage report does not match")
    coverage.require_complete()
    return score_predictions(benchmark.cases, predictions)


def _dataset_fingerprint(dataset: GoldDataset, *, split: DatasetSplit) -> str:
    payload = {
        "dataset_version": dataset.dataset_version,
        "state_contract_version": dataset.state_contract_version,
        "split": split.value,
        "cases": [case.model_dump(mode="json") for case in dataset.cases if case.split is split],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _corpus_fingerprint(dataset: GoldDataset) -> str:
    payload = {
        "dataset_version": dataset.dataset_version,
        "state_contract_version": dataset.state_contract_version,
        "cases": [case.model_dump(mode="json") for case in dataset.cases],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _require_complete_corpus(dataset: GoldDataset) -> None:
    present_splits = {case.split for case in dataset.cases}
    required_splits = set(DatasetSplit)
    if present_splits != required_splits:
        missing = sorted(split.value for split in required_splits - present_splits)
        raise ValueError(f"qualified scoring requires a complete corpus; missing splits: {missing}")


def _append_missing_issue(
    issues: list[CoverageIssue],
    *,
    dimension: CoverageDimension,
    required: frozenset[str],
    covered: set[str],
    scenario_key: str | None = None,
) -> None:
    missing = tuple(sorted(required - covered))
    if missing:
        issues.append(
            CoverageIssue(
                dimension=dimension,
                missing_values=missing,
                scenario_key=scenario_key,
            )
        )


def _format_issue(issue: CoverageIssue) -> str:
    scope = f"{issue.scenario_key}:" if issue.scenario_key else ""
    return f"{scope}{issue.dimension.value}={list(issue.missing_values)}"
