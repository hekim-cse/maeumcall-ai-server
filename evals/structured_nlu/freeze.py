from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.ai_origin_policy import (
    EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
    ai_origin_policy_fingerprint_v1,
    serialize_ai_origin_policy_v1,
)
from evals.structured_nlu.authoring import (
    AuthoringSourceFile,
    AuthoringSourceSnapshot,
    VerifiedAuthoringBundle,
    verify_compiled_authoring_snapshot,
)
from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
    QualifiedTestSlice,
    _prepare_qualified_test_slice,
    _score_qualified_test_slice,
)
from evals.structured_nlu.contrast import (
    CONTRAST_MANIFEST_SCHEMA_VERSION,
    contrast_policy_fingerprint,
    verify_contrast_manifest_snapshot,
)
from evals.structured_nlu.coverage_v3 import (
    COVERAGE_CONTRACT_V3_ID,
    OFFICIAL_COVERAGE_CONTRACT_V3,
)
from evals.structured_nlu.metrics import EvaluationScores
from evals.structured_nlu.obligations import (
    build_official_authoring_obligations,
    serialize_official_authoring_obligations,
)
from evals.structured_nlu.review import (
    ANNOTATION_GUIDELINE_V1_ID,
    canonical_json_text,
    normalize_text_tree,
    read_regular_artifact,
    verify_review_ledger_snapshot,
)
from evals.structured_nlu.schema import (
    STRUCTURED_NLU_DATASET_VERSION,
    CasePrediction,
    DatasetSplit,
)
from services.flow.common.state_contract import SCENARIO_STATE_VERSION

FREEZE_RECORD_SCHEMA_VERSION_V1 = 1
FREEZE_RECORD_SCHEMA_VERSION = 2
FREEZE_RECORD_FINGERPRINT_ALGORITHM_V1 = "freeze-record-canonical-json-sha256-v1"
FREEZE_RECORD_FINGERPRINT_ALGORITHM_V2 = "freeze-record-canonical-json-sha256-v2"
BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V1 = (
    "structured-nlu-benchmark-identity-canonical-json-sha256-v1"
)
BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V2 = (
    "structured-nlu-benchmark-identity-canonical-json-sha256-v2"
)
ID_SET_FINGERPRINT_ALGORITHM_V1 = "sorted-id-set-canonical-json-sha256-v1"

Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FreezeId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]
RepoRelativePath = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]


class GitInputRevisionV1(BaseModel):
    """Identify the committed input snapshot without referring to the later record commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_format: Literal["sha1", "sha256"]
    commit: str

    @model_validator(mode="after")
    def commit_matches_object_format(self) -> GitInputRevisionV1:
        expected_length = 40 if self.object_format == "sha1" else 64
        if len(self.commit) != expected_length or any(
            character not in "0123456789abcdef" for character in self.commit
        ):
            raise ValueError("input Git commit does not match its object format")
        return self


class FreezeContractVersionsV1(BaseModel):
    """Pin independently versioned authoring, review, and evaluation contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoring_schema_version: Literal[2]
    split_assignment_schema_version: Literal[1]
    dataset_schema_version: Literal[STRUCTURED_NLU_DATASET_VERSION]
    state_contract_version: Literal[SCENARIO_STATE_VERSION]
    review_ledger_schema_version: Literal[1]
    contrast_manifest_schema_version: Literal[CONTRAST_MANIFEST_SCHEMA_VERSION]
    coverage_profile_version: Literal[3]


class FreezeContractVersionsV2(FreezeContractVersionsV1):
    """Add the immutable AI-origin policy version to the governed contracts."""

    ai_origin_policy_schema_version: Literal[1]


class FreezeArtifactPathsV1(BaseModel):
    """Store only explicit repository-relative artifact paths; no moving latest pointer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_source_root: RepoRelativePath
    split_assignment_path: RepoRelativePath
    compiled_corpus_path: RepoRelativePath
    annotation_guideline_path: RepoRelativePath
    review_ledger_path: RepoRelativePath
    contrast_manifest_path: RepoRelativePath
    obligation_manifest_path: RepoRelativePath

    @model_validator(mode="after")
    def paths_are_safe_and_distinct(self) -> FreezeArtifactPathsV1:
        values = tuple(self.model_dump().values())
        for value in values:
            _validate_repo_relative_path(value)
        if len(set(values)) != len(values):
            raise ValueError("freeze artifact paths must be distinct")
        source_root = PurePosixPath(self.group_source_root)
        for value in values[1:]:
            if PurePosixPath(value).is_relative_to(source_root):
                raise ValueError("freeze artifacts must be outside the group source root")
        return self


class FreezeArtifactPathsV2(FreezeArtifactPathsV1):
    """Add the repository-owned AI-origin policy artifact to the frozen inputs."""

    ai_origin_policy_path: RepoRelativePath


class FreezeArtifactFingerprintsV1(BaseModel):
    """Bind raw source artifacts and their semantic compiled identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_source_fingerprint: Sha256Fingerprint
    split_assignment_fingerprint: Sha256Fingerprint
    compiled_artifact_sha256: Sha256Fingerprint
    corpus_fingerprint: Sha256Fingerprint
    annotation_guideline_fingerprint: Sha256Fingerprint
    review_ledger_fingerprint: Sha256Fingerprint
    contrast_manifest_fingerprint: Sha256Fingerprint
    obligation_manifest_sha256: Sha256Fingerprint


class FreezeArtifactFingerprintsV2(FreezeArtifactFingerprintsV1):
    """Bind both raw and semantic identities of the AI-origin policy."""

    ai_origin_policy_artifact_sha256: Sha256Fingerprint
    ai_origin_policy_fingerprint: Literal[EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1]


class FreezeBenchmarkContractV1(BaseModel):
    """Pin the exact policy that turns a corpus into a qualified benchmark."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: Literal["maeumcall-structured-nlu-v3"]
    profile_fingerprint: Literal[OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT]
    coverage_contract_id: Literal[COVERAGE_CONTRACT_V3_ID]
    coverage_contract_fingerprint: Literal[OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint]
    contrast_policy_fingerprint: Literal[contrast_policy_fingerprint()]
    annotation_guideline_id: Literal[ANNOTATION_GUIDELINE_V1_ID]
    obligation_count: int = Field(gt=0)

    @model_validator(mode="after")
    def obligation_count_matches_v3(self) -> FreezeBenchmarkContractV1:
        expected = len(build_official_authoring_obligations())
        if self.obligation_count != expected:
            raise ValueError("freeze obligation count differs from Coverage V3")
        return self


class FreezeCorpusInventoryV1(BaseModel):
    """Store diagnostic counts and exact ID-set identities without copying the corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_count: int = Field(gt=0)
    case_count: int = Field(gt=0)
    development_case_count: int = Field(gt=0)
    validation_case_count: int = Field(gt=0)
    test_case_count: int = Field(gt=0)
    group_ids_fingerprint: Sha256Fingerprint
    case_ids_fingerprint: Sha256Fingerprint

    @model_validator(mode="after")
    def split_counts_equal_case_count(self) -> FreezeCorpusInventoryV1:
        total = self.development_case_count + self.validation_case_count + self.test_case_count
        if total != self.case_count:
            raise ValueError("freeze split counts must equal the corpus case count")
        return self


class CorpusFreezeRecordV1(BaseModel):
    """Immutable V1 approval record for one exact structured-NLU benchmark snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    freeze_record_schema_version: Literal[FREEZE_RECORD_SCHEMA_VERSION_V1]
    freeze_id: FreezeId
    freeze_revision: int = Field(ge=1)
    previous_freeze_record_fingerprint: Sha256Fingerprint | None
    record_fingerprint_algorithm: Literal[FREEZE_RECORD_FINGERPRINT_ALGORITHM_V1]
    benchmark_identity_fingerprint_algorithm: Literal[BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V1]
    input_git_revision: GitInputRevisionV1
    versions: FreezeContractVersionsV1
    paths: FreezeArtifactPathsV1
    artifacts: FreezeArtifactFingerprintsV1
    benchmark: FreezeBenchmarkContractV1
    inventory: FreezeCorpusInventoryV1
    qualified_splits: tuple[Literal["validation"], Literal["test"]]
    benchmark_identity_fingerprint: Sha256Fingerprint
    record_fingerprint: Sha256Fingerprint

    @model_validator(mode="after")
    def record_is_self_consistent(self) -> CorpusFreezeRecordV1:
        if self.freeze_revision == 1 and self.previous_freeze_record_fingerprint is not None:
            raise ValueError("the first freeze revision must not name a previous record")
        if self.freeze_revision > 1 and self.previous_freeze_record_fingerprint is None:
            raise ValueError("later freeze revisions require a previous record fingerprint")
        if self.benchmark_identity_fingerprint != _benchmark_identity_fingerprint(
            versions=self.versions,
            artifacts=self.artifacts,
            benchmark=self.benchmark,
        ):
            raise ValueError("freeze benchmark identity fingerprint does not match")
        if self.record_fingerprint != _record_fingerprint(self):
            raise ValueError("freeze record fingerprint does not match")
        return self


class CorpusFreezeRecordV2(BaseModel):
    """Current record format, including the exact AI-origin exclusion policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    freeze_record_schema_version: Literal[FREEZE_RECORD_SCHEMA_VERSION]
    freeze_id: FreezeId
    freeze_revision: int = Field(ge=1)
    previous_freeze_record_fingerprint: Sha256Fingerprint | None
    record_fingerprint_algorithm: Literal[FREEZE_RECORD_FINGERPRINT_ALGORITHM_V2]
    benchmark_identity_fingerprint_algorithm: Literal[BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V2]
    input_git_revision: GitInputRevisionV1
    versions: FreezeContractVersionsV2
    paths: FreezeArtifactPathsV2
    artifacts: FreezeArtifactFingerprintsV2
    benchmark: FreezeBenchmarkContractV1
    inventory: FreezeCorpusInventoryV1
    qualified_splits: tuple[Literal["validation"], Literal["test"]]
    benchmark_identity_fingerprint: Sha256Fingerprint
    record_fingerprint: Sha256Fingerprint

    @model_validator(mode="after")
    def record_is_self_consistent(self) -> CorpusFreezeRecordV2:
        if self.freeze_revision == 1 and self.previous_freeze_record_fingerprint is not None:
            raise ValueError("the first freeze revision must not name a previous record")
        if self.freeze_revision > 1 and self.previous_freeze_record_fingerprint is None:
            raise ValueError("later freeze revisions require a previous record fingerprint")
        if self.benchmark_identity_fingerprint != _benchmark_identity_fingerprint(
            versions=self.versions,
            artifacts=self.artifacts,
            benchmark=self.benchmark,
        ):
            raise ValueError("freeze benchmark identity fingerprint does not match")
        if self.record_fingerprint != _record_fingerprint(self):
            raise ValueError("freeze record fingerprint does not match")
        return self


CorpusFreezeRecord = CorpusFreezeRecordV1 | CorpusFreezeRecordV2


@dataclass(frozen=True)
class VerifiedFrozenCorpus:
    record: CorpusFreezeRecord
    bundle: VerifiedAuthoringBundle
    benchmark: QualifiedTestSlice


def create_freeze_record_file(
    *,
    repo_root: Path,
    output_path: Path,
    freeze_id: str,
    freeze_revision: int,
    previous_record_paths: tuple[Path, ...],
    input_git_revision: str,
    paths: FreezeArtifactPathsV2,
) -> CorpusFreezeRecordV2:
    """Build and atomically create one explicit record without replacing any artifact."""
    resolved_repo_root = _verified_repo_root(repo_root)
    resolved_output = _resolve_external_record_path(resolved_repo_root, output_path)
    resolved_paths = _resolve_artifact_paths(resolved_repo_root, paths)
    governed_paths = set(resolved_paths.__dict__.values())
    if resolved_output in governed_paths or resolved_output.is_relative_to(
        resolved_paths.group_source_root
    ):
        raise ValueError("freeze record output must not replace a governed artifact")
    record = build_freeze_record(
        repo_root=resolved_repo_root,
        freeze_id=freeze_id,
        freeze_revision=freeze_revision,
        previous_record_paths=previous_record_paths,
        input_git_revision=input_git_revision,
        paths=paths,
    )
    write_new_freeze_record(resolved_output, record)
    return record


def build_freeze_record(
    *,
    repo_root: Path,
    freeze_id: str,
    freeze_revision: int,
    previous_record_paths: tuple[Path, ...],
    input_git_revision: str,
    paths: FreezeArtifactPathsV2,
) -> CorpusFreezeRecordV2:
    """Build a record only from committed, fully qualified worktree artifacts."""
    resolved_repo_root = _verified_repo_root(repo_root)
    resolved_commit, object_format = _resolve_git_revision(
        resolved_repo_root,
        input_git_revision,
    )
    head_commit, _ = _resolve_git_revision(resolved_repo_root, "HEAD")
    if resolved_commit != head_commit:
        raise ValueError("freeze creation requires input_git_revision to be the current HEAD")
    resolved_paths = _resolve_artifact_paths(resolved_repo_root, paths)
    previous_freeze_record_fingerprint = _verified_previous_record_chain(
        resolved_repo_root,
        freeze_id=freeze_id,
        freeze_revision=freeze_revision,
        next_input_commit=resolved_commit,
        previous_record_paths=previous_record_paths,
    )
    input_snapshot = _capture_git_input_snapshot(
        resolved_repo_root,
        resolved_commit,
        paths,
        group_source_root=resolved_paths.group_source_root,
    )
    _require_worktree_matches_snapshot(resolved_paths, input_snapshot)
    _require_clean_worktree(resolved_repo_root)
    bundle, benchmark, obligation_sha256 = _verify_freeze_input_snapshot(input_snapshot)
    inventory = _build_inventory(bundle)
    policy_artifact_sha256 = _verify_ai_origin_policy_snapshot(input_snapshot.ai_origin_policy)
    artifacts = FreezeArtifactFingerprintsV2(
        group_source_fingerprint=bundle.group_source_fingerprint,
        split_assignment_fingerprint=bundle.split_assignment_fingerprint,
        compiled_artifact_sha256=_sha256_bytes(input_snapshot.compiled_corpus),
        corpus_fingerprint=benchmark.corpus_fingerprint,
        annotation_guideline_fingerprint=bundle.review.guideline_fingerprint,
        review_ledger_fingerprint=bundle.review.ledger_fingerprint,
        contrast_manifest_fingerprint=bundle.contrast.fingerprint,
        obligation_manifest_sha256=obligation_sha256,
        ai_origin_policy_artifact_sha256=policy_artifact_sha256,
        ai_origin_policy_fingerprint=ai_origin_policy_fingerprint_v1(),
    )
    versions = _current_versions()
    benchmark_contract = _current_benchmark_contract()
    payload = {
        "freeze_record_schema_version": FREEZE_RECORD_SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "freeze_revision": freeze_revision,
        "previous_freeze_record_fingerprint": previous_freeze_record_fingerprint,
        "record_fingerprint_algorithm": FREEZE_RECORD_FINGERPRINT_ALGORITHM_V2,
        "benchmark_identity_fingerprint_algorithm": (BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V2),
        "input_git_revision": {
            "object_format": object_format,
            "commit": resolved_commit,
        },
        "versions": versions.model_dump(mode="json"),
        "paths": paths.model_dump(mode="json"),
        "artifacts": artifacts.model_dump(mode="json"),
        "benchmark": benchmark_contract.model_dump(mode="json"),
        "inventory": inventory.model_dump(mode="json"),
        "qualified_splits": ["validation", "test"],
        "benchmark_identity_fingerprint": _benchmark_identity_fingerprint(
            versions=versions,
            artifacts=artifacts,
            benchmark=benchmark_contract,
        ),
    }
    payload["record_fingerprint"] = _sha256_text(
        canonical_json_text(
            {
                "algorithm": FREEZE_RECORD_FINGERPRINT_ALGORITHM_V2,
                "record": payload,
            }
        )
    )
    return CorpusFreezeRecordV2.model_validate(payload)


def _verified_previous_record_chain(
    repo_root: Path,
    *,
    freeze_id: str,
    freeze_revision: int,
    next_input_commit: str,
    previous_record_paths: tuple[Path, ...],
) -> str | None:
    expected_count = freeze_revision - 1
    if len(previous_record_paths) != expected_count:
        if freeze_revision == 1:
            raise ValueError("the first freeze revision must not provide previous records")
        raise ValueError("freeze revision requires every previous record in revision order")
    if not previous_record_paths:
        return None

    resolved_paths = tuple(
        _resolve_external_record_path(repo_root, path) for path in previous_record_paths
    )
    if len(set(resolved_paths)) != len(resolved_paths):
        raise ValueError("freeze record lineage paths must be unique")
    successor_input_commit = next_input_commit
    successor_previous_fingerprint: str | None = None
    immediate_fingerprint: str | None = None
    for expected_revision, path in reversed(tuple(enumerate(resolved_paths, start=1))):
        previous = _load_freeze_record_from_git(
            repo_root,
            successor_input_commit,
            path,
        )
        if previous.freeze_id != freeze_id:
            raise ValueError("previous freeze record belongs to a different freeze lineage")
        if previous.freeze_revision != expected_revision:
            raise ValueError("previous freeze record revision is not contiguous")
        _require_git_ancestor(
            repo_root,
            previous.input_git_revision.commit,
            successor_input_commit,
        )
        _verify_historical_freeze_record(repo_root, previous)
        if successor_previous_fingerprint is not None and (
            successor_previous_fingerprint != previous.record_fingerprint
        ):
            raise ValueError("freeze record predecessor fingerprint does not match")
        if immediate_fingerprint is None:
            immediate_fingerprint = previous.record_fingerprint
        successor_previous_fingerprint = previous.previous_freeze_record_fingerprint
        successor_input_commit = previous.input_git_revision.commit
    if successor_previous_fingerprint is not None:
        raise ValueError("the first freeze revision must not name a predecessor")
    return immediate_fingerprint


def verify_freeze_record(
    *,
    repo_root: Path,
    record_path: Path,
    previous_record_paths: tuple[Path, ...] = (),
) -> VerifiedFrozenCorpus:
    """Recompute every governed value from an explicit record immediately before use."""
    resolved_repo_root = _verified_repo_root(repo_root)
    resolved_record_path = _resolve_external_record_path(resolved_repo_root, record_path)
    record = _load_committed_freeze_record(resolved_repo_root, resolved_record_path)
    previous_fingerprint = _verified_previous_record_chain(
        resolved_repo_root,
        freeze_id=record.freeze_id,
        freeze_revision=record.freeze_revision,
        next_input_commit=record.input_git_revision.commit,
        previous_record_paths=previous_record_paths,
    )
    if record.previous_freeze_record_fingerprint != previous_fingerprint:
        raise ValueError("freeze record predecessor fingerprint does not match")
    resolved_paths = _resolve_artifact_paths(resolved_repo_root, record.paths)
    resolved_commit, object_format = _resolve_git_revision(
        resolved_repo_root,
        record.input_git_revision.commit,
    )
    if (
        resolved_commit != record.input_git_revision.commit
        or object_format != record.input_git_revision.object_format
    ):
        raise ValueError("freeze input Git revision does not match the repository")
    _require_git_ancestor(resolved_repo_root, resolved_commit, "HEAD")
    input_snapshot = _capture_git_input_snapshot(
        resolved_repo_root,
        resolved_commit,
        record.paths,
        group_source_root=resolved_paths.group_source_root,
    )
    _require_worktree_matches_snapshot(resolved_paths, input_snapshot)
    bundle, benchmark, obligation_sha256 = _verify_freeze_input_snapshot(input_snapshot)
    _assert_record_evidence(
        record,
        bundle=bundle,
        benchmark=benchmark,
        obligation_sha256=obligation_sha256,
        compiled_artifact_sha256=_sha256_bytes(input_snapshot.compiled_corpus),
        ai_origin_policy_artifact_sha256=(
            _verify_ai_origin_policy_snapshot(input_snapshot.ai_origin_policy)
            if isinstance(record, CorpusFreezeRecordV2)
            else None
        ),
    )
    return VerifiedFrozenCorpus(record=record, bundle=bundle, benchmark=benchmark)


def _verify_historical_freeze_record(
    repo_root: Path,
    record: CorpusFreezeRecord,
) -> None:
    """Verify one predecessor from its own Git input without consulting the worktree."""
    resolved_commit, object_format = _resolve_git_revision(
        repo_root,
        record.input_git_revision.commit,
    )
    if (
        resolved_commit != record.input_git_revision.commit
        or object_format != record.input_git_revision.object_format
    ):
        raise ValueError("historical freeze input Git revision does not match")
    input_snapshot = _capture_git_input_snapshot(
        repo_root,
        resolved_commit,
        record.paths,
        group_source_root=repo_root / PurePosixPath(record.paths.group_source_root),
    )
    bundle, benchmark, obligation_sha256 = _verify_freeze_input_snapshot(input_snapshot)
    _assert_record_evidence(
        record,
        bundle=bundle,
        benchmark=benchmark,
        obligation_sha256=obligation_sha256,
        compiled_artifact_sha256=_sha256_bytes(input_snapshot.compiled_corpus),
        ai_origin_policy_artifact_sha256=(
            _verify_ai_origin_policy_snapshot(input_snapshot.ai_origin_policy)
            if isinstance(record, CorpusFreezeRecordV2)
            else None
        ),
    )


def _assert_record_evidence(
    record: CorpusFreezeRecord,
    *,
    bundle: VerifiedAuthoringBundle,
    benchmark: QualifiedTestSlice,
    obligation_sha256: str,
    compiled_artifact_sha256: str,
    ai_origin_policy_artifact_sha256: str | None = None,
) -> None:
    expected = _record_evidence(
        bundle=bundle,
        benchmark=benchmark,
        obligation_sha256=obligation_sha256,
        compiled_artifact_sha256=compiled_artifact_sha256,
        record=record,
        ai_origin_policy_artifact_sha256=ai_origin_policy_artifact_sha256,
    )
    if record.versions != expected["versions"]:
        raise ValueError("freeze contract versions do not match the live contracts")
    if record.artifacts != expected["artifacts"]:
        raise ValueError("freeze artifact fingerprints do not match the live artifacts")
    if record.benchmark != expected["benchmark"]:
        raise ValueError("freeze benchmark contract does not match the live contract")
    if record.inventory != expected["inventory"]:
        raise ValueError("freeze corpus inventory does not match the live corpus")


def prepare_qualified_test_slice_from_freeze(
    *,
    repo_root: Path,
    record_path: Path,
    previous_record_paths: tuple[Path, ...] = (),
) -> QualifiedTestSlice:
    """Public official preparation boundary; an explicit freeze record is mandatory."""
    return verify_freeze_record(
        repo_root=repo_root,
        record_path=record_path,
        previous_record_paths=previous_record_paths,
    ).benchmark


def score_qualified_test_slice_from_freeze(
    *,
    repo_root: Path,
    record_path: Path,
    previous_record_paths: tuple[Path, ...] = (),
    benchmark: QualifiedTestSlice,
    predictions: tuple[CasePrediction, ...],
) -> EvaluationScores:
    """Revalidate the exact freeze record and benchmark before official scoring."""
    verified = verify_freeze_record(
        repo_root=repo_root,
        record_path=record_path,
        previous_record_paths=previous_record_paths,
    )
    if benchmark != verified.benchmark:
        raise ValueError("qualified benchmark does not match the explicit freeze record")
    return _score_qualified_test_slice(benchmark, predictions)


def load_freeze_record(path: Path) -> CorpusFreezeRecord:
    raw = read_regular_artifact(path, label="freeze record")
    return _parse_freeze_record(raw, label=str(path))


def _parse_freeze_record(raw: bytes, *, label: str) -> CorpusFreezeRecord:
    """Parse one already captured record snapshot without rereading its path."""
    try:
        decoded = normalize_text_tree(json.loads(raw, object_pairs_hook=_object_from_unique_pairs))
        if not isinstance(decoded, dict):
            raise ValueError("freeze record root must be an object")
        version = decoded.get("freeze_record_schema_version")
        if version == FREEZE_RECORD_SCHEMA_VERSION_V1:
            return CorpusFreezeRecordV1.model_validate(decoded)
        if version == FREEZE_RECORD_SCHEMA_VERSION:
            return CorpusFreezeRecordV2.model_validate(decoded)
        raise ValueError("unsupported freeze record schema version")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid freeze record: {label}") from exc


def serialize_freeze_record(record: CorpusFreezeRecord) -> str:
    return (
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def serialize_freeze_record_schema() -> str:
    schema = CorpusFreezeRecordV2.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:freeze-record:v2"
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_new_freeze_record(path: Path, record: CorpusFreezeRecord) -> None:
    """Create one immutable record atomically and refuse every overwrite attempt."""
    _require_absolute_path_without_symlinks(path, label="freeze record output")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"freeze record already exists: {path}")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".writing",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write(serialize_freeze_record(record))
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


@dataclass(frozen=True)
class _FreezeInputSnapshot:
    authoring: AuthoringSourceSnapshot
    compiled_corpus: bytes
    annotation_guideline: bytes
    review_ledger: bytes
    contrast_manifest: bytes
    obligation_manifest: bytes
    ai_origin_policy: bytes | None = None


def _verify_freeze_input_snapshot(
    snapshot: _FreezeInputSnapshot,
) -> tuple[VerifiedAuthoringBundle, QualifiedTestSlice, str]:
    dataset, group_source_fingerprint, split_assignment_fingerprint = (
        verify_compiled_authoring_snapshot(snapshot.authoring, snapshot.compiled_corpus)
    )
    verified_review = verify_review_ledger_snapshot(
        dataset,
        snapshot.annotation_guideline,
        snapshot.review_ledger,
    )
    verified_contrast = verify_contrast_manifest_snapshot(dataset, snapshot.contrast_manifest)
    bundle = VerifiedAuthoringBundle(
        dataset=dataset,
        group_source_fingerprint=group_source_fingerprint,
        split_assignment_fingerprint=split_assignment_fingerprint,
        review=verified_review,
        contrast=verified_contrast,
    )
    expected_obligations = serialize_official_authoring_obligations().encode("utf-8")
    actual_obligations = snapshot.obligation_manifest
    if actual_obligations != expected_obligations:
        raise ValueError("coverage obligation manifest differs from Coverage V3")
    benchmark = _prepare_qualified_test_slice(
        bundle.dataset,
        authoring_source_fingerprint=bundle.group_source_fingerprint,
        split_assignment_fingerprint=bundle.split_assignment_fingerprint,
        annotation_guideline_fingerprint=bundle.review.guideline_fingerprint,
        review_ledger_fingerprint=bundle.review.ledger_fingerprint,
        contrast_manifest_fingerprint=bundle.contrast.fingerprint,
    )
    return bundle, benchmark, _sha256_bytes(actual_obligations)


def _record_evidence(
    *,
    bundle: VerifiedAuthoringBundle,
    benchmark: QualifiedTestSlice,
    obligation_sha256: str,
    compiled_artifact_sha256: str,
    record: CorpusFreezeRecord,
    ai_origin_policy_artifact_sha256: str | None,
) -> dict[str, BaseModel]:
    if isinstance(record, CorpusFreezeRecordV2):
        if ai_origin_policy_artifact_sha256 is None:
            raise ValueError("freeze record V2 requires the AI-origin policy artifact")
        versions: BaseModel = _current_versions()
        artifacts: BaseModel = FreezeArtifactFingerprintsV2(
            group_source_fingerprint=bundle.group_source_fingerprint,
            split_assignment_fingerprint=bundle.split_assignment_fingerprint,
            compiled_artifact_sha256=compiled_artifact_sha256,
            corpus_fingerprint=benchmark.corpus_fingerprint,
            annotation_guideline_fingerprint=bundle.review.guideline_fingerprint,
            review_ledger_fingerprint=bundle.review.ledger_fingerprint,
            contrast_manifest_fingerprint=bundle.contrast.fingerprint,
            obligation_manifest_sha256=obligation_sha256,
            ai_origin_policy_artifact_sha256=ai_origin_policy_artifact_sha256,
            ai_origin_policy_fingerprint=ai_origin_policy_fingerprint_v1(),
        )
    else:
        versions = FreezeContractVersionsV1(
            authoring_schema_version=2,
            split_assignment_schema_version=1,
            dataset_schema_version=STRUCTURED_NLU_DATASET_VERSION,
            state_contract_version=SCENARIO_STATE_VERSION,
            review_ledger_schema_version=1,
            contrast_manifest_schema_version=CONTRAST_MANIFEST_SCHEMA_VERSION,
            coverage_profile_version=3,
        )
        artifacts = FreezeArtifactFingerprintsV1(
            group_source_fingerprint=bundle.group_source_fingerprint,
            split_assignment_fingerprint=bundle.split_assignment_fingerprint,
            compiled_artifact_sha256=compiled_artifact_sha256,
            corpus_fingerprint=benchmark.corpus_fingerprint,
            annotation_guideline_fingerprint=bundle.review.guideline_fingerprint,
            review_ledger_fingerprint=bundle.review.ledger_fingerprint,
            contrast_manifest_fingerprint=bundle.contrast.fingerprint,
            obligation_manifest_sha256=obligation_sha256,
        )
    return {
        "versions": versions,
        "artifacts": artifacts,
        "benchmark": _current_benchmark_contract(),
        "inventory": _build_inventory(bundle),
    }


def _current_versions() -> FreezeContractVersionsV2:
    return FreezeContractVersionsV2(
        authoring_schema_version=2,
        split_assignment_schema_version=1,
        dataset_schema_version=STRUCTURED_NLU_DATASET_VERSION,
        state_contract_version=SCENARIO_STATE_VERSION,
        review_ledger_schema_version=1,
        contrast_manifest_schema_version=CONTRAST_MANIFEST_SCHEMA_VERSION,
        coverage_profile_version=3,
        ai_origin_policy_schema_version=1,
    )


def _current_benchmark_contract() -> FreezeBenchmarkContractV1:
    return FreezeBenchmarkContractV1(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        coverage_contract_id=COVERAGE_CONTRACT_V3_ID,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_policy_fingerprint=contrast_policy_fingerprint(),
        annotation_guideline_id=ANNOTATION_GUIDELINE_V1_ID,
        obligation_count=len(build_official_authoring_obligations()),
    )


def _build_inventory(bundle: VerifiedAuthoringBundle) -> FreezeCorpusInventoryV1:
    cases = bundle.dataset.cases
    group_ids = sorted({case.conversation_group_id for case in cases})
    case_ids = sorted(case.id for case in cases)
    counts = {split: sum(case.split is split for case in cases) for split in DatasetSplit}
    return FreezeCorpusInventoryV1(
        group_count=len(group_ids),
        case_count=len(case_ids),
        development_case_count=counts[DatasetSplit.DEVELOPMENT],
        validation_case_count=counts[DatasetSplit.VALIDATION],
        test_case_count=counts[DatasetSplit.TEST],
        group_ids_fingerprint=_id_set_fingerprint("conversation-group-ids", group_ids),
        case_ids_fingerprint=_id_set_fingerprint("case-ids", case_ids),
    )


def _benchmark_identity_fingerprint(
    *,
    versions: FreezeContractVersionsV1 | FreezeContractVersionsV2,
    artifacts: FreezeArtifactFingerprintsV1 | FreezeArtifactFingerprintsV2,
    benchmark: FreezeBenchmarkContractV1,
) -> str:
    is_v2 = isinstance(artifacts, FreezeArtifactFingerprintsV2)
    payload = {
        "algorithm": (
            BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V2
            if is_v2
            else BENCHMARK_IDENTITY_FINGERPRINT_ALGORITHM_V1
        ),
        "versions": versions.model_dump(mode="json"),
        "semantic_artifacts": {
            "split_assignment_fingerprint": artifacts.split_assignment_fingerprint,
            "corpus_fingerprint": artifacts.corpus_fingerprint,
            "annotation_guideline_fingerprint": artifacts.annotation_guideline_fingerprint,
            "review_ledger_fingerprint": artifacts.review_ledger_fingerprint,
            "contrast_manifest_fingerprint": artifacts.contrast_manifest_fingerprint,
            "obligation_manifest_sha256": artifacts.obligation_manifest_sha256,
        },
        "benchmark": benchmark.model_dump(mode="json"),
    }
    if is_v2:
        payload["semantic_artifacts"].update(
            {
                "ai_origin_policy_fingerprint": artifacts.ai_origin_policy_fingerprint,
                "ai_origin_policy_artifact_sha256": (artifacts.ai_origin_policy_artifact_sha256),
            }
        )
    return _sha256_text(canonical_json_text(payload))


def _record_fingerprint(record: CorpusFreezeRecord) -> str:
    algorithm = (
        FREEZE_RECORD_FINGERPRINT_ALGORITHM_V2
        if isinstance(record, CorpusFreezeRecordV2)
        else FREEZE_RECORD_FINGERPRINT_ALGORITHM_V1
    )
    payload = record.model_dump(mode="json", exclude={"record_fingerprint"})
    return _sha256_text(
        canonical_json_text(
            {
                "algorithm": algorithm,
                "record": payload,
            }
        )
    )


def _id_set_fingerprint(label: str, values: list[str]) -> str:
    return _sha256_text(
        canonical_json_text(
            {
                "algorithm": ID_SET_FINGERPRINT_ALGORITHM_V1,
                "label": label,
                "values": values,
            }
        )
    )


@dataclass(frozen=True)
class _ResolvedFreezeArtifactPaths:
    group_source_root: Path
    split_assignment_path: Path
    compiled_corpus_path: Path
    annotation_guideline_path: Path
    review_ledger_path: Path
    contrast_manifest_path: Path
    obligation_manifest_path: Path
    ai_origin_policy_path: Path | None = None


def _resolve_artifact_paths(
    repo_root: Path,
    paths: FreezeArtifactPathsV1 | FreezeArtifactPathsV2,
) -> _ResolvedFreezeArtifactPaths:
    values = {
        name: _resolve_repo_artifact(repo_root, relative, label=name.replace("_", " "))
        for name, relative in paths.model_dump().items()
    }
    if not values["group_source_root"].is_dir():
        raise ValueError("group source root does not exist")
    for name, path in values.items():
        if name == "group_source_root":
            continue
        if not path.is_file():
            raise ValueError(f"freeze artifact does not exist: {name}")
    return _ResolvedFreezeArtifactPaths(**values)


def _resolve_external_record_path(repo_root: Path, record_path: Path) -> Path:
    if record_path.is_absolute():
        candidate = record_path.absolute()
    else:
        candidate = (repo_root / record_path).absolute()
    if not candidate.is_relative_to(repo_root):
        raise ValueError("freeze record must be inside the repository")
    _require_no_symlink_components(repo_root, candidate, label="freeze record")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(repo_root):
        raise ValueError("freeze record must be inside the repository")
    return resolved


def _resolve_repo_artifact(repo_root: Path, relative: str, *, label: str) -> Path:
    _validate_repo_relative_path(relative)
    candidate = (repo_root / PurePosixPath(relative)).absolute()
    _require_no_symlink_components(repo_root, candidate, label=label)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(repo_root):
        raise ValueError(f"{label} escapes the repository")
    return resolved


def _validate_repo_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or value in {"", "."} or ".." in path.parts or "\\" in value:
        raise ValueError(f"freeze artifact path must be repository-relative: {value}")
    if path.as_posix() != value:
        raise ValueError(f"freeze artifact path must use canonical POSIX form: {value}")


def _require_no_symlink_components(repo_root: Path, path: Path, *, label: str) -> None:
    current = repo_root
    for component in path.relative_to(repo_root).parts:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} path must not contain symbolic links: {path}")


def _require_absolute_path_without_symlinks(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} path must not contain symbolic links: {path}")


def _verified_repo_root(repo_root: Path) -> Path:
    resolved = repo_root.resolve()
    if repo_root.absolute() != resolved:
        raise ValueError("repo_root must be the canonical Git worktree root")
    actual = Path(
        _run_git(resolved, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    ).resolve()
    if actual != resolved:
        raise ValueError("repo_root must be the Git worktree root")
    return resolved


def _resolve_git_revision(repo_root: Path, revision: str) -> tuple[str, str]:
    object_format = _run_git(repo_root, "rev-parse", "--show-object-format").decode().strip()
    commit = _run_git(repo_root, "rev-parse", f"{revision}^{{commit}}").decode().strip()
    return commit, object_format


def _require_clean_worktree(repo_root: Path) -> None:
    status = _run_git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError("freeze creation requires a clean Git worktree")


def _require_git_ancestor(repo_root: Path, ancestor: str, descendant: str) -> None:
    result = subprocess.run(
        ("git", "-C", str(repo_root), "merge-base", "--is-ancestor", ancestor, descendant),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError("freeze input Git revision must be an ancestor of its successor")


def _capture_git_input_snapshot(
    repo_root: Path,
    commit: str,
    paths: FreezeArtifactPathsV1 | FreezeArtifactPathsV2,
    *,
    group_source_root: Path,
) -> _FreezeInputSnapshot:
    source_prefix = paths.group_source_root.rstrip("/") + "/"
    tracked_source_files = tuple(
        raw_path.decode("utf-8")
        for raw_path in _run_git(
            repo_root,
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            commit,
            "--",
            paths.group_source_root,
        )
        .rstrip(b"\0")
        .split(b"\0")
        if raw_path.endswith(b".json")
    )
    authoring_files = tuple(
        AuthoringSourceFile(
            relative_path=relative.removeprefix(source_prefix),
            content=_git_file_bytes(repo_root, commit, relative),
        )
        for relative in tracked_source_files
    )
    return _FreezeInputSnapshot(
        authoring=AuthoringSourceSnapshot(
            source_dir=group_source_root,
            files=authoring_files,
            split_assignments=AuthoringSourceFile(
                relative_path="@split-assignments.v1.json",
                content=_git_file_bytes(repo_root, commit, paths.split_assignment_path),
            ),
        ),
        compiled_corpus=_git_file_bytes(repo_root, commit, paths.compiled_corpus_path),
        annotation_guideline=_git_file_bytes(
            repo_root,
            commit,
            paths.annotation_guideline_path,
        ),
        review_ledger=_git_file_bytes(repo_root, commit, paths.review_ledger_path),
        contrast_manifest=_git_file_bytes(repo_root, commit, paths.contrast_manifest_path),
        obligation_manifest=_git_file_bytes(repo_root, commit, paths.obligation_manifest_path),
        ai_origin_policy=(
            _git_file_bytes(repo_root, commit, paths.ai_origin_policy_path)
            if isinstance(paths, FreezeArtifactPathsV2)
            else None
        ),
    )


def _require_worktree_matches_snapshot(
    resolved: _ResolvedFreezeArtifactPaths,
    snapshot: _FreezeInputSnapshot,
) -> None:
    source_paths = tuple(resolved.group_source_root.rglob("*.json"))
    for path in source_paths:
        _require_no_symlink_components(
            resolved.group_source_root,
            path.absolute(),
            label="group source file",
        )
    current_source_files = {
        path.relative_to(resolved.group_source_root).as_posix(): path.read_bytes()
        for path in source_paths
    }
    expected_source_files = {
        source.relative_path: source.content for source in snapshot.authoring.files
    }
    if current_source_files != expected_source_files:
        raise ValueError("group source files differ from the input Git revision")
    expected_files = {
        resolved.split_assignment_path: snapshot.authoring.split_assignments.content,
        resolved.compiled_corpus_path: snapshot.compiled_corpus,
        resolved.annotation_guideline_path: snapshot.annotation_guideline,
        resolved.review_ledger_path: snapshot.review_ledger,
        resolved.contrast_manifest_path: snapshot.contrast_manifest,
        resolved.obligation_manifest_path: snapshot.obligation_manifest,
    }
    if resolved.ai_origin_policy_path is not None and snapshot.ai_origin_policy is not None:
        expected_files[resolved.ai_origin_policy_path] = snapshot.ai_origin_policy
    for path, expected in expected_files.items():
        if path.read_bytes() != expected:
            raise ValueError(f"governed artifact differs from the input Git revision: {path.name}")


def _git_file_bytes(repo_root: Path, commit: str, relative: str) -> bytes:
    metadata = _run_git(repo_root, "ls-tree", commit, "--", relative).decode("utf-8")
    lines = metadata.splitlines()
    if len(lines) != 1:
        raise ValueError(f"Git input must contain exactly one artifact: {relative}")
    mode, object_type, _remainder = lines[0].split(maxsplit=2)
    if object_type != "blob" or mode not in {"100644", "100755"}:
        raise ValueError(f"Git input artifact must be a regular file: {relative}")
    return _run_git(repo_root, "show", f"{commit}:{relative}")


def _load_committed_freeze_record(
    repo_root: Path,
    record_path: Path,
) -> CorpusFreezeRecord:
    """Parse the immutable HEAD blob and compare the worktree file to those same bytes."""
    relative = record_path.relative_to(repo_root).as_posix()
    committed = _git_file_bytes(repo_root, "HEAD", relative)
    worktree = read_regular_artifact(record_path, label="freeze record")
    if committed != worktree:
        raise ValueError("freeze record differs from the exact Git HEAD blob")
    return _parse_freeze_record(committed, label=f"HEAD:{relative}")


def _load_freeze_record_from_git(
    repo_root: Path,
    revision: str,
    record_path: Path,
) -> CorpusFreezeRecord:
    """Load a predecessor from the successor's immutable Git input snapshot."""
    relative = record_path.relative_to(repo_root).as_posix()
    committed = _git_file_bytes(repo_root, revision, relative)
    return _parse_freeze_record(committed, label=f"{revision}:{relative}")


def _run_git(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ("git", "-C", str(repo_root), *args),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git verification failed: {message}")
    return result.stdout


def _object_from_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"freeze record contains a duplicate JSON key: {key}")
        result[key] = value
    return result


def _verify_ai_origin_policy_snapshot(policy: bytes | None) -> str:
    if policy is None:
        raise ValueError("freeze record V2 requires the AI-origin policy artifact")
    expected = serialize_ai_origin_policy_v1().encode("utf-8")
    if policy != expected:
        raise ValueError("AI-origin policy artifact differs from immutable policy V1")
    if ai_origin_policy_fingerprint_v1() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1:
        raise ValueError("AI-origin policy fingerprint differs from immutable policy V1")
    return _sha256_bytes(policy)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))
