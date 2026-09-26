from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.coverage_v3 import COVERAGE_CONTRACT_V3_ID
from evals.structured_nlu.review import (
    EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
    canonical_json_text,
    evaluation_case_fingerprint,
    normalize_text_tree,
    read_regular_artifact,
)
from evals.structured_nlu.schema import DatasetSplit, EvaluationCase, GoldDataset, NonEmptyText

CONTRAST_MANIFEST_SCHEMA_VERSION = 1
CONTRAST_GROUP_FINGERPRINT_ALGORITHM_V1 = "contrast-group-canonical-json-sha256-v1"
CONTRAST_MANIFEST_FINGERPRINT_ALGORITHM_V1 = "contrast-manifest-semantic-sha256-v1"
CONTRAST_CONTEXT_FIELDS = frozenset(
    {"conversation_state", "current_fields", "offered_alternative_times"}
)

Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ReviewerId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")]
ReviewRationale = Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]


@dataclass(frozen=True)
class ContrastRolePolicy:
    role_id: str
    scenario_key: str
    allowed_actions: frozenset[str] = frozenset()
    allowed_states: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ContrastFamilyPolicy:
    family_id: str
    roles: tuple[ContrastRolePolicy, ...]
    shared_context_fields: frozenset[str]


class ContrastMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: NonEmptyText
    case_id: NonEmptyText
    case_fingerprint: Sha256Fingerprint


class ContrastGroupDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contrast_group_id: NonEmptyText
    family_id: NonEmptyText
    comparison_axis_id: NonEmptyText
    confusion_axis: NonEmptyText
    members: tuple[ContrastMember, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_members(self) -> ContrastGroupDefinition:
        role_ids = [member.role_id for member in self.members]
        case_ids = [member.case_id for member in self.members]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("contrast member role_id values must be unique")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("contrast member case_id values must be unique")
        return self


class ContrastGroupApproval(BaseModel):
    """Record the human decision that these exact cases form the declared contrast."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_fingerprint_algorithm: Literal[CONTRAST_GROUP_FINGERPRINT_ALGORITHM_V1]
    group_fingerprint: Sha256Fingerprint
    reviewer_id: ReviewerId
    reviewed_at: AwareDatetime
    rationale: ReviewRationale
    decision: Literal["approved"]


class ContrastGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    definition: ContrastGroupDefinition
    approval: ContrastGroupApproval


class ContrastManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contrast_manifest_schema_version: Literal[1]
    coverage_contract_id: Literal[COVERAGE_CONTRACT_V3_ID]
    case_fingerprint_algorithm: Literal[EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1]
    groups: tuple[ContrastGroup, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_groups(self) -> ContrastManifestV1:
        group_ids = [group.definition.contrast_group_id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("contrast_group_id values must be unique")
        return self


@dataclass(frozen=True)
class VerifiedContrastManifest:
    fingerprint: str
    covered_roles_by_split: tuple[tuple[DatasetSplit, frozenset[str]], ...]


def _role(
    role_id: str,
    scenario_key: str,
    *actions: str,
    states: frozenset[str] = frozenset(),
) -> ContrastRolePolicy:
    return ContrastRolePolicy(role_id, scenario_key, frozenset(actions), states)


DETAILED_POSITIVE_CONTRASTS_V1 = MappingProxyType(
    {
        "교수님:면담 예약": ("collecting_appointment_info", "provide_appointment_info"),
        "교수님:과제 문의": ("collecting_assignment_info", "provide_assignment_info"),
        "교수님:결석 사유 전달": ("collecting_absence_info", "provide_absence_info"),
        "예약:병원 예약": ("asking_date", "continue_collecting"),
        "예약:식당 예약": ("collecting_reservation_info", "continue_collecting"),
        "예약:미용실 예약": ("collecting_reservation_info", "continue_collecting"),
        "예약:스터디룸 예약": ("collecting_reservation_info", "continue_collecting"),
    }
)
_detailed_scenario_keys = {
    scenario_key
    for scenario_key, contract in EVALUATION_CONTRACTS.items()
    if contract.workflow_spec is None
}
if set(DETAILED_POSITIVE_CONTRASTS_V1) != _detailed_scenario_keys:
    raise RuntimeError(
        "detailed positive contrast declarations must exactly match live scenarios: "
        f"missing={sorted(_detailed_scenario_keys - set(DETAILED_POSITIVE_CONTRASTS_V1))}, "
        f"stale={sorted(set(DETAILED_POSITIVE_CONTRASTS_V1) - _detailed_scenario_keys)}"
    )


def _build_official_families() -> tuple[ContrastFamilyPolicy, ...]:
    families: list[ContrastFamilyPolicy] = []

    reservation_actions = (
        "select_alternative_time",
        "ask_other_time",
        "change_date",
        "unknown",
    )
    for scenario_key in (
        "예약:병원 예약",
        "예약:식당 예약",
        "예약:미용실 예약",
        "예약:스터디룸 예약",
    ):
        slug = scenario_key.split(":", 1)[1].replace(" ", "-")
        alternative_states = EVALUATION_CONTRACTS[scenario_key].alternative_states
        families.append(
            ContrastFamilyPolicy(
                f"reservation-alternative-action-{slug}",
                tuple(
                    _role(action, scenario_key, action, states=alternative_states)
                    for action in reservation_actions
                ),
                frozenset({"conversation_state", "current_fields", "offered_alternative_times"}),
            )
        )

    for scenario_key in (
        "배달:주문 변경",
        "배달:배달 지연 문의",
        "배달:환불/재배달 문의",
        "시청:여권 발급 문의",
        "시청:주민등록 등본 문의",
        "시청:대형폐기물 배출",
        "고객센터:인터넷/통화 문제 문의",
        "고객센터:요금/약정 상담",
        "고객센터:a/s 접수",
    ):
        slug = scenario_key.replace(":", "-").replace("/", "-").replace(" ", "-")
        spec = EVALUATION_CONTRACTS[scenario_key].workflow_spec
        if spec is None:
            raise RuntimeError(f"workflow contrast is missing its live spec: {scenario_key}")
        families.append(
            ContrastFamilyPolicy(
                f"workflow-stage-action-{slug}",
                (
                    _role(
                        "confirm",
                        scenario_key,
                        "confirm_details",
                        states=frozenset({spec.confirming_state}),
                    ),
                    _role(
                        "complete",
                        scenario_key,
                        "complete_simulation",
                        states=frozenset({spec.ready_state}),
                    ),
                    _role(
                        "cancel",
                        scenario_key,
                        "cancel_workflow",
                        states=frozenset({spec.confirming_state}),
                    ),
                ),
                frozenset({"current_fields", "offered_alternative_times"}),
            )
        )

    for scenario_key, contract in sorted(EVALUATION_CONTRACTS.items()):
        if contract.workflow_spec is not None:
            positive_action = "provide_details"
            state = contract.workflow_spec.collecting_state
        else:
            state, positive_action = DETAILED_POSITIVE_CONTRASTS_V1[scenario_key]
        slug = scenario_key.replace(":", "-").replace("/", "-").replace(" ", "-")
        families.append(
            ContrastFamilyPolicy(
                f"positive-vs-unknown-{slug}",
                (
                    _role(
                        "positive",
                        scenario_key,
                        positive_action,
                        states=frozenset({state}),
                    ),
                    _role(
                        "unknown",
                        scenario_key,
                        "unknown",
                        states=frozenset({state}),
                    ),
                ),
                frozenset({"conversation_state", "current_fields", "offered_alternative_times"}),
            )
        )
    return tuple(families)


OFFICIAL_CONTRAST_FAMILIES_V1 = _build_official_families()
_family_ids = [family.family_id for family in OFFICIAL_CONTRAST_FAMILIES_V1]
if len(_family_ids) != len(set(_family_ids)):
    raise RuntimeError("contrast family ids must be unique")
for _family in OFFICIAL_CONTRAST_FAMILIES_V1:
    if len(_family.roles) < 2:
        raise RuntimeError(f"contrast family requires at least two roles: {_family.family_id}")
    _role_ids = [role.role_id for role in _family.roles]
    if len(_role_ids) != len(set(_role_ids)):
        raise RuntimeError(f"contrast role ids must be unique: {_family.family_id}")
    if (
        not _family.shared_context_fields
        or not _family.shared_context_fields <= CONTRAST_CONTEXT_FIELDS
    ):
        raise RuntimeError(f"contrast shared context fields are invalid: {_family.family_id}")
    for _policy_role in _family.roles:
        _contract = EVALUATION_CONTRACTS.get(_policy_role.scenario_key)
        _actions_by_state = dict(_contract.actions_by_state) if _contract is not None else {}
        if (
            _contract is None
            or not _policy_role.allowed_actions <= _contract.user_actions
            or not _policy_role.allowed_states <= _contract.conversation_states
            or any(
                not _policy_role.allowed_actions <= _actions_by_state[state]
                for state in _policy_role.allowed_states
            )
        ):
            raise RuntimeError(
                f"contrast role differs from the live contract: "
                f"{_family.family_id}/{_policy_role.role_id}"
            )


def contrast_policy_payload() -> str:
    payload = {
        "coverage_contract_id": COVERAGE_CONTRACT_V3_ID,
        "contrast_manifest_schema_version": CONTRAST_MANIFEST_SCHEMA_VERSION,
        "context_comparison_algorithm": "contrast-context-exact-v1",
        "group_fingerprint_algorithm": CONTRAST_GROUP_FINGERPRINT_ALGORITHM_V1,
        "case_fingerprint_algorithm": EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
        "manifest_fingerprint_algorithm": CONTRAST_MANIFEST_FINGERPRINT_ALGORITHM_V1,
        "families": {
            family.family_id: {
                "shared_context_fields": sorted(family.shared_context_fields),
                "roles": {
                    role.role_id: {
                        "scenario_key": role.scenario_key,
                        "allowed_actions": sorted(role.allowed_actions),
                        "allowed_states": sorted(role.allowed_states),
                    }
                    for role in family.roles
                },
            }
            for family in OFFICIAL_CONTRAST_FAMILIES_V1
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def contrast_policy_fingerprint() -> str:
    return hashlib.sha256(contrast_policy_payload().encode("utf-8")).hexdigest()


def contrast_role_obligations() -> frozenset[str]:
    return frozenset(
        f"{family.family_id}->{role.role_id}"
        for family in OFFICIAL_CONTRAST_FAMILIES_V1
        for role in family.roles
    )


def verify_contrast_manifest(
    dataset: GoldDataset,
    manifest_path: Path,
) -> VerifiedContrastManifest:
    raw = read_regular_artifact(manifest_path, label="contrast manifest")
    return verify_contrast_manifest_snapshot(dataset, raw)


def verify_contrast_manifest_snapshot(
    dataset: GoldDataset,
    raw: bytes,
) -> VerifiedContrastManifest:
    """Verify a contrast manifest captured in the caller's immutable snapshot."""
    try:
        decoded = normalize_text_tree(json.loads(raw, object_pairs_hook=_object_from_unique_pairs))
        manifest = ContrastManifestV1.model_validate(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid contrast manifest") from exc
    cases_by_id = {case.id: case for case in dataset.cases}
    families = {family.family_id: family for family in OFFICIAL_CONTRAST_FAMILIES_V1}
    groups_by_split: dict[DatasetSplit, dict[str, ContrastGroup]] = {
        DatasetSplit.VALIDATION: {},
        DatasetSplit.TEST: {},
    }
    for group in manifest.groups:
        definition = group.definition
        family = families.get(definition.family_id)
        if family is None:
            raise ValueError(f"unknown contrast family: {definition.family_id}")
        if definition.comparison_axis_id != family.family_id:
            raise ValueError(f"contrast comparison axis must match family: {definition.family_id}")
        if group.approval.group_fingerprint != contrast_group_fingerprint(definition):
            raise ValueError(
                f"contrast group approval does not match current content: "
                f"{definition.contrast_group_id}"
            )
        members_by_role = {member.role_id: member for member in definition.members}
        expected_roles = {role.role_id for role in family.roles}
        if set(members_by_role) != expected_roles:
            raise ValueError(f"contrast roles must exactly match family: {definition.family_id}")
        member_cases = []
        for role in family.roles:
            case = cases_by_id.get(members_by_role[role.role_id].case_id)
            if case is None:
                raise ValueError(
                    f"contrast case does not exist: {members_by_role[role.role_id].case_id}"
                )
            if case.scenario_key != role.scenario_key:
                raise ValueError(f"contrast case does not match role scenario: {role.role_id}")
            if role.allowed_actions and case.labels.user_action not in role.allowed_actions:
                raise ValueError(f"contrast case does not match role action: {role.role_id}")
            if role.allowed_states and case.conversation_state not in role.allowed_states:
                raise ValueError(f"contrast case does not match role state: {role.role_id}")
            if members_by_role[role.role_id].case_fingerprint != evaluation_case_fingerprint(case):
                raise ValueError(f"contrast case fingerprint does not match: {role.role_id}")
            member_cases.append(case)
        context_signatures = {
            _contrast_context_signature(case, family.shared_context_fields) for case in member_cases
        }
        if len(context_signatures) != 1:
            raise ValueError(
                f"contrast members do not share required context: {definition.family_id}"
            )
        splits = {case.split for case in member_cases}
        if len(splits) != 1 or next(iter(splits)) not in groups_by_split:
            raise ValueError("contrast members must share validation or test split")
        split = next(iter(splits))
        if definition.family_id in groups_by_split[split]:
            raise ValueError(f"contrast family must appear once per split: {definition.family_id}")
        groups_by_split[split][definition.family_id] = group

    required_families = set(families)
    for split, split_groups in groups_by_split.items():
        if set(split_groups) != required_families:
            raise ValueError(f"contrast families are incomplete for {split.value}")
    normalized = {
        "contrast_manifest_schema_version": manifest.contrast_manifest_schema_version,
        "coverage_contract_id": manifest.coverage_contract_id,
        "case_fingerprint_algorithm": manifest.case_fingerprint_algorithm,
        "fingerprint_algorithm": CONTRAST_MANIFEST_FINGERPRINT_ALGORITHM_V1,
        "groups": [
            {
                "definition": _canonical_group_definition(group.definition),
                "approval": group.approval.model_dump(mode="json"),
            }
            for group in sorted(manifest.groups, key=lambda item: item.definition.contrast_group_id)
        ],
    }
    payload = canonical_json_text(normalized)
    return VerifiedContrastManifest(
        fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        covered_roles_by_split=tuple(
            (
                split,
                frozenset(
                    f"{group.definition.family_id}->{member.role_id}"
                    for group in groups_by_split[split].values()
                    for member in group.definition.members
                ),
            )
            for split in (DatasetSplit.VALIDATION, DatasetSplit.TEST)
        ),
    )


def _object_from_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"contrast manifest contains a duplicate key: {key}")
        result[key] = value
    return result


def _contrast_context_signature(case: EvaluationCase, fields: frozenset[str]) -> str:
    values = {
        "conversation_state": case.conversation_state,
        "current_fields": case.current_fields,
        "offered_alternative_times": case.offered_alternative_times,
    }
    payload = {field: values[field] for field in sorted(fields)}
    return canonical_json_text(payload)


def _canonical_group_definition(definition: ContrastGroupDefinition) -> dict[str, object]:
    return {
        "contrast_group_id": definition.contrast_group_id,
        "family_id": definition.family_id,
        "comparison_axis_id": definition.comparison_axis_id,
        "confusion_axis": definition.confusion_axis,
        "members": [
            member.model_dump(mode="json")
            for member in sorted(definition.members, key=lambda item: item.role_id)
        ],
    }


def contrast_group_fingerprint(definition: ContrastGroupDefinition) -> str:
    """Bind human approval to one exact semantic contrast relationship."""
    payload = {
        "algorithm": CONTRAST_GROUP_FINGERPRINT_ALGORITHM_V1,
        "definition": _canonical_group_definition(definition),
    }
    return hashlib.sha256(canonical_json_text(payload).encode("utf-8")).hexdigest()


def serialize_contrast_manifest_schema() -> str:
    schema = ContrastManifestV1.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:contrast-manifest:v1"
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
