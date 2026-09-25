from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import (
    STRUCTURED_NLU_DATASET_VERSION,
    CasePrediction,
    DatasetSplit,
    DifficultyTag,
    EvaluationCase,
    GoldDataset,
    GoldLabels,
    NonEmptyText,
    NonEmptyUserMessage,
    ReviewStatus,
)
from services.flow.common.state_contract import SCENARIO_STATE_VERSION

if TYPE_CHECKING:
    from evals.structured_nlu.benchmark import QualifiedTestSlice
    from evals.structured_nlu.metrics import EvaluationScores

CaseId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]


class AuthoringCase(BaseModel):
    """One manually labelled model input inside a single semantic source group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: CaseId
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    offered_alternative_times: tuple[NonEmptyText, ...]
    user_message: NonEmptyUserMessage
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    review_status: ReviewStatus


class AuthoringGroup(BaseModel):
    """Own one semantic seed so all derived utterances stay in the same split."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoring_schema_version: Literal[2]
    conversation_group_id: CaseId
    scenario_key: NonEmptyText
    provenance: Literal["human_authored"]
    cases: tuple[AuthoringCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> AuthoringGroup:
        if self.scenario_key not in EVALUATION_CONTRACTS:
            raise ValueError(f"unknown scenario_key: {self.scenario_key}")
        case_ids = [case.id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("authoring case ids must be unique within a group")
        return self

    def compile_cases(self, split: DatasetSplit) -> tuple[EvaluationCase, ...]:
        return tuple(_compile_authoring_case(self, case, split) for case in self.cases)


class SplitAssignment(BaseModel):
    """Freeze one semantic source group into exactly one dataset split."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_group_id: CaseId
    split: DatasetSplit


class SplitAssignmentManifest(BaseModel):
    """Own every group-to-split decision outside the editable group files."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    split_assignment_schema_version: Literal[1]
    dataset_version: Literal[STRUCTURED_NLU_DATASET_VERSION]
    assignments: tuple[SplitAssignment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def group_ids_are_unique(self) -> SplitAssignmentManifest:
        group_ids = [assignment.conversation_group_id for assignment in self.assignments]
        duplicate_group_ids = sorted(
            group_id for group_id, count in Counter(group_ids).items() if count > 1
        )
        if duplicate_group_ids:
            raise ValueError(
                f"split assignments must contain unique group ids: {duplicate_group_ids}"
            )
        return self

    @property
    def split_by_group_id(self) -> dict[str, DatasetSplit]:
        return {
            assignment.conversation_group_id: assignment.split for assignment in self.assignments
        }

    @property
    def fingerprint(self) -> str:
        payload = {
            "split_assignment_schema_version": self.split_assignment_schema_version,
            "dataset_version": self.dataset_version,
            "assignments": [
                {
                    "conversation_group_id": group_id,
                    "split": split.value,
                }
                for group_id, split in sorted(self.split_by_group_id.items())
            ],
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthoringSourceFile:
    relative_path: str
    content: bytes


@dataclass(frozen=True)
class AuthoringSourceSnapshot:
    source_dir: Path
    files: tuple[AuthoringSourceFile, ...]
    split_assignments: AuthoringSourceFile

    @property
    def group_source_fingerprint(self) -> str:
        """Identify only group source files; split decisions have a separate fingerprint."""
        digest = hashlib.sha256()
        for source_file in self.files:
            digest.update(source_file.relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source_file.content)
            digest.update(b"\0")
        return digest.hexdigest()


def capture_authoring_source(
    source_dir: Path,
    split_assignments_path: Path,
) -> AuthoringSourceSnapshot:
    """Read every source file once so compilation and provenance share one snapshot."""
    resolved_source_dir = source_dir.resolve()
    if not resolved_source_dir.is_dir():
        raise ValueError(f"authoring source directory does not exist: {source_dir}")
    source_paths = tuple(sorted(resolved_source_dir.rglob("*.json")))
    if not source_paths:
        raise ValueError(f"authoring source directory contains no JSON groups: {source_dir}")

    resolved_assignments_path = split_assignments_path.resolve()
    if resolved_assignments_path.is_relative_to(resolved_source_dir):
        raise ValueError("split assignment manifest must be outside the group source directory")
    if split_assignments_path.is_symlink():
        raise ValueError("split assignment manifest must not be a symbolic link")
    if not resolved_assignments_path.is_file():
        raise ValueError(f"split assignment manifest does not exist: {split_assignments_path}")
    try:
        split_assignments_content = resolved_assignments_path.read_bytes()
    except OSError as exc:
        raise ValueError(
            f"unable to read split assignment manifest: {split_assignments_path}"
        ) from exc

    source_files = []
    for source_path in source_paths:
        if source_path.is_symlink():
            raise ValueError(f"authoring source files must not be symbolic links: {source_path}")
        try:
            resolved_path = source_path.resolve()
            relative_path = resolved_path.relative_to(resolved_source_dir).as_posix()
            content = resolved_path.read_bytes()
        except ValueError as exc:
            raise ValueError(f"authoring source escapes its directory: {source_path}") from exc
        except OSError as exc:
            raise ValueError(f"unable to read authoring source: {source_path}") from exc
        source_files.append(AuthoringSourceFile(relative_path=relative_path, content=content))
    return AuthoringSourceSnapshot(
        source_dir=resolved_source_dir,
        files=tuple(source_files),
        split_assignments=AuthoringSourceFile(
            relative_path="@split-assignments.v1.json",
            content=split_assignments_content,
        ),
    )


def compile_authoring_snapshot(snapshot: AuthoringSourceSnapshot) -> GoldDataset:
    assignment_manifest = _load_split_assignment_manifest(snapshot)

    groups = []
    for source_file in snapshot.files:
        try:
            decoded = json.loads(source_file.content)
            groups.append(AuthoringGroup.model_validate(_normalize_text_tree(decoded)))
        except ValueError as exc:
            source_path = snapshot.source_dir / source_file.relative_path
            raise ValueError(f"invalid authoring group: {source_path}") from exc

    group_ids = [group.conversation_group_id for group in groups]
    duplicate_group_ids = sorted(
        group_id for group_id, count in Counter(group_ids).items() if count > 1
    )
    if duplicate_group_ids:
        raise ValueError(
            f"conversation groups must be owned by one source file: {duplicate_group_ids}"
        )

    assignment_group_ids = set(assignment_manifest.split_by_group_id)
    source_group_ids = set(group_ids)
    missing_assignments = sorted(source_group_ids - assignment_group_ids)
    unused_assignments = sorted(assignment_group_ids - source_group_ids)
    if missing_assignments or unused_assignments:
        raise ValueError(
            "split assignment manifest must match the authoring groups exactly: "
            f"missing={missing_assignments}, unused={unused_assignments}"
        )

    cases = tuple(
        sorted(
            (
                case
                for group in groups
                for case in group.compile_cases(
                    assignment_manifest.split_by_group_id[group.conversation_group_id]
                )
            ),
            key=lambda case: (case.scenario_key, case.conversation_group_id, case.id),
        )
    )
    return GoldDataset(
        dataset_version=STRUCTURED_NLU_DATASET_VERSION,
        state_contract_version=SCENARIO_STATE_VERSION,
        cases=cases,
    )


def _load_split_assignment_manifest(
    snapshot: AuthoringSourceSnapshot,
) -> SplitAssignmentManifest:
    try:
        return SplitAssignmentManifest.model_validate(
            _normalize_text_tree(json.loads(snapshot.split_assignments.content))
        )
    except ValueError as exc:
        raise ValueError("invalid split assignment manifest") from exc


def compile_authoring_directory(
    source_dir: Path,
    split_assignments_path: Path,
) -> GoldDataset:
    """Compile group-owned source files into a deterministic GoldDataset."""
    return compile_authoring_snapshot(capture_authoring_source(source_dir, split_assignments_path))


def _compile_authoring_case(
    group: AuthoringGroup,
    case: AuthoringCase,
    split: DatasetSplit,
) -> EvaluationCase:
    payload = _normalize_text_tree(
        {
            **case.model_dump(mode="json"),
            "conversation_group_id": group.conversation_group_id,
            "split": split.value,
            "scenario_key": group.scenario_key,
            "provenance": group.provenance,
        }
    )
    payload["tags"] = sorted(payload["tags"])
    for expected in payload["labels"]["fields"].values():
        if expected is not None:
            expected["accepted_values"] = sorted(expected["accepted_values"])
    return EvaluationCase.model_validate(payload)


def _normalize_text_tree(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized_key = _normalize_text_tree(key)
            if normalized_key in normalized:
                raise ValueError(f"text normalization produced a duplicate key: {normalized_key}")
            normalized[normalized_key] = _normalize_text_tree(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_text_tree(item) for item in value]
    return value


def serialize_gold_dataset(dataset: GoldDataset) -> str:
    return (
        json.dumps(
            dataset.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_authoring_group_schema() -> str:
    """Export the editor-facing schema from the authoring model itself."""
    schema = AuthoringGroup.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:authoring-group:v2"
    schema["properties"]["scenario_key"]["enum"] = sorted(EVALUATION_CONTRACTS)
    return (
        json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def serialize_split_assignment_schema() -> str:
    """Export the editor-facing split assignment schema from the code contract."""
    schema = SplitAssignmentManifest.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:split-assignments:v1"
    return (
        json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def verify_compiled_authoring_corpus(
    source_dir: Path,
    split_assignments_path: Path,
    compiled_path: Path,
) -> tuple[GoldDataset, str, str]:
    """Require byte-identical source compilation before official qualification."""
    ensure_output_outside_source(source_dir, compiled_path)
    ensure_output_does_not_replace_manifest(split_assignments_path, compiled_path)
    snapshot = capture_authoring_source(source_dir, split_assignments_path)
    expected_dataset = compile_authoring_snapshot(snapshot)
    expected_bytes = serialize_gold_dataset(expected_dataset).encode("utf-8")
    if not compiled_path.is_file():
        raise ValueError(f"compiled corpus does not exist: {compiled_path}")
    if compiled_path.read_bytes() != expected_bytes:
        raise ValueError("compiled corpus differs from the authoring sources")
    split_assignment_fingerprint = _load_split_assignment_manifest(snapshot).fingerprint
    return expected_dataset, snapshot.group_source_fingerprint, split_assignment_fingerprint


def prepare_qualified_test_slice_from_authoring(
    source_dir: Path,
    split_assignments_path: Path,
    compiled_path: Path,
):
    """Prepare an official test slice only from verified authoring sources."""
    dataset, source_fingerprint, split_assignment_fingerprint = verify_compiled_authoring_corpus(
        source_dir,
        split_assignments_path,
        compiled_path,
    )
    from evals.structured_nlu.benchmark import _prepare_qualified_test_slice

    return _prepare_qualified_test_slice(
        dataset,
        authoring_source_fingerprint=source_fingerprint,
        split_assignment_fingerprint=split_assignment_fingerprint,
    )


def score_qualified_test_slice_from_authoring(
    source_dir: Path,
    split_assignments_path: Path,
    compiled_path: Path,
    benchmark: QualifiedTestSlice,
    predictions: tuple[CasePrediction, ...],
) -> EvaluationScores:
    """Revalidate authoring provenance immediately before qualified scoring."""
    dataset, source_fingerprint, split_assignment_fingerprint = verify_compiled_authoring_corpus(
        source_dir,
        split_assignments_path,
        compiled_path,
    )
    if benchmark.authoring_source_fingerprint != source_fingerprint:
        raise ValueError("qualified authoring source fingerprint does not match")
    if benchmark.split_assignment_fingerprint != split_assignment_fingerprint:
        raise ValueError("qualified split assignment fingerprint does not match")
    if benchmark.corpus_cases != dataset.cases:
        raise ValueError("qualified benchmark does not match the verified authoring corpus")
    from evals.structured_nlu.benchmark import _score_qualified_test_slice

    return _score_qualified_test_slice(benchmark, predictions)


def ensure_output_outside_source(source_dir: Path, output_path: Path) -> None:
    resolved_source_dir = source_dir.resolve()
    resolved_output = output_path.resolve(strict=False)
    if resolved_output == resolved_source_dir or resolved_output.is_relative_to(
        resolved_source_dir
    ):
        raise ValueError("compiled output must be outside the authoring source directory")


def ensure_output_does_not_replace_manifest(
    split_assignments_path: Path,
    output_path: Path,
) -> None:
    if output_path.resolve(strict=False) == split_assignments_path.resolve(strict=False):
        raise ValueError("compiled output must not replace the split assignment manifest")
