"""Separate review gate for AI-authored, human-adjudicated heldout cases.

This is not the human-authored official benchmark or its V4 freeze boundary.
The ledger records a human decision; a hash cannot prove who actually reviewed it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import (
    DatasetSplit,
    GoldLabels,
    NonEmptyText,
    NonEmptyUserMessage,
    ReviewStatus,
    validate_evaluation_case_semantics,
)
from evals.structured_nlu.semantics import DifficultyTag
from services.flow.common.state_contract import SCENARIO_STATE_VERSION

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
CaseId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]
GitCommit = Annotated[str, Field(pattern=r"^[0-9a-f]{40,64}$")]


class AIHeldoutCase(BaseModel):
    """One fictional, AI-authored case; never masquerade as human-authored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: CaseId
    conversation_group_id: CaseId
    split: DatasetSplit
    scenario_key: NonEmptyText
    conversation_state: NonEmptyText
    current_fields: dict[str, NonEmptyText | None]
    offered_alternative_times: tuple[NonEmptyText, ...]
    user_message: NonEmptyUserMessage
    labels: GoldLabels
    tags: tuple[DifficultyTag, ...] = Field(min_length=1)
    provenance: Literal["ai_authored"]
    review_status: ReviewStatus

    @model_validator(mode="after")
    def follows_live_contract(self) -> AIHeldoutCase:
        validate_evaluation_case_semantics(
            scenario_key=self.scenario_key,
            conversation_state=self.conversation_state,
            current_fields=self.current_fields,
            offered_alternative_times=self.offered_alternative_times,
            labels=self.labels,
            tags=self.tags,
        )
        return self


class AIHeldoutDataset(BaseModel):
    """Separate corpus format; the official GoldDataset does not accept it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_authored_heldout_dataset_v1"]
    dataset_version: Literal[1]
    state_contract_version: Literal[SCENARIO_STATE_VERSION]
    declared_model_exposure: Literal["not_run"]
    cases: tuple[AIHeldoutCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases_and_inputs(self) -> AIHeldoutDataset:
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("AI heldout case IDs must be unique")
        groups: dict[str, set[DatasetSplit]] = {}
        inputs: set[str] = set()
        for case in self.cases:
            groups.setdefault(case.conversation_group_id, set()).add(case.split)
            payload = {
                "scenario_key": case.scenario_key,
                "conversation_state": case.conversation_state,
                "current_fields": case.current_fields,
                "offered_alternative_times": case.offered_alternative_times,
                "user_message": case.user_message,
            }
            fingerprint = json.dumps(
                _normalize_nfc(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            if fingerprint in inputs:
                raise ValueError("duplicate AI heldout model inputs are not allowed")
            inputs.add(fingerprint)
        if any(len(splits) > 1 for splits in groups.values()):
            raise ValueError("AI heldout conversation groups must not cross splits")
        return self


class AIHeldoutReviewLedger(BaseModel):
    """One explicit decision over the exact raw dataset bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_authored_heldout_review_v1"]
    reviewed_for: Literal["ai_authored_heldout_accuracy"]
    dataset_sha256: Sha256
    accepted_case_ids: tuple[CaseId, ...] = Field(min_length=1)
    adjudicator_id: CaseId
    adjudicated_at: datetime
    rationale: NonEmptyText

    @model_validator(mode="after")
    def decision_is_well_formed(self) -> AIHeldoutReviewLedger:
        if self.adjudicated_at.tzinfo is None:
            raise ValueError("adjudicated_at must include a timezone")
        if list(self.accepted_case_ids) != sorted(set(self.accepted_case_ids)):
            raise ValueError("accepted_case_ids must be unique and sorted")
        return self


class ReviewedAIHeldout(BaseModel):
    """Validated input bundle for a future AI-heldout prediction runner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: AIHeldoutDataset
    dataset_sha256: Sha256
    review_ledger: AIHeldoutReviewLedger
    scenario_counts: dict[str, int]


class AIHeldoutFreezeRecord(BaseModel):
    """Bind reviewed inputs and the comparison protocol to one Git snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["ai_authored_heldout_pre_exposure_freeze_v1"]
    input_git_revision: GitCommit
    dataset_path: NonEmptyText
    dataset_sha256: Sha256
    review_ledger_path: NonEmptyText
    review_ledger_sha256: Sha256
    protocol_path: NonEmptyText
    protocol_sha256: Sha256
    exposure_record_path: NonEmptyText


class VerifiedAIHeldoutFreeze(BaseModel):
    """A committed freeze checked immediately before the first model call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: AIHeldoutFreezeRecord
    reviewed: ReviewedAIHeldout


def verify_ai_heldout_review(dataset_bytes: bytes, review_ledger_bytes: bytes) -> ReviewedAIHeldout:
    """Reject draft, mismatched, or incomplete 16-scenario heldout inputs."""
    dataset = AIHeldoutDataset.model_validate_json(dataset_bytes)
    ledger = AIHeldoutReviewLedger.model_validate_json(review_ledger_bytes)
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    if ledger.dataset_sha256 != digest:
        raise ValueError("review ledger does not match the exact AI heldout dataset bytes")
    if any(case.split is not DatasetSplit.TEST for case in dataset.cases):
        raise ValueError("AI heldout scoring requires test cases only")
    if any(case.review_status is not ReviewStatus.ADJUDICATED for case in dataset.cases):
        raise ValueError("AI heldout scoring requires adjudicated cases only")
    case_ids = tuple(sorted(case.id for case in dataset.cases))
    if ledger.accepted_case_ids != case_ids:
        raise ValueError("review ledger case IDs must exactly match the AI heldout dataset")
    counts = Counter(case.scenario_key for case in dataset.cases)
    if set(counts) != set(EVALUATION_CONTRACTS):
        raise ValueError("AI heldout evaluation requires cases from all 16 detailed scenarios")
    return ReviewedAIHeldout(
        dataset=dataset,
        dataset_sha256=digest,
        review_ledger=ledger,
        scenario_counts={key: counts[key] for key in sorted(counts)},
    )


def load_reviewed_ai_heldout(dataset_path: Path, review_ledger_path: Path) -> ReviewedAIHeldout:
    """Read each artifact once so review and execution share exact bytes."""
    return verify_ai_heldout_review(dataset_path.read_bytes(), review_ledger_path.read_bytes())


def build_ai_heldout_pre_exposure_freeze(
    *,
    repo_root: Path,
    input_git_revision: str,
    dataset_path: str,
    review_ledger_path: str,
    protocol_path: str,
    exposure_record_path: str,
) -> AIHeldoutFreezeRecord:
    """Create a proposed record from committed reviewed inputs, before exposure.

    The caller must commit the returned record before verification or model use.
    """
    root = _verified_repo_root(repo_root)
    commit = _resolve_commit(root, input_git_revision)
    if commit != _resolve_commit(root, "HEAD"):
        raise ValueError("freeze creation requires input_git_revision to be HEAD")
    paths = _checked_artifact_paths(
        root, dataset_path, review_ledger_path, protocol_path, exposure_record_path
    )
    _require_no_exposure(root, exposure_record_path, paths[3])
    dataset_bytes = _matching_input_blob(root, commit, dataset_path, paths[0])
    ledger_bytes = _matching_input_blob(root, commit, review_ledger_path, paths[1])
    protocol_bytes = _matching_input_blob(root, commit, protocol_path, paths[2])
    verify_ai_heldout_review(dataset_bytes, ledger_bytes)
    if not protocol_bytes.strip():
        raise ValueError("AI heldout comparison protocol must not be blank")
    return AIHeldoutFreezeRecord(
        kind="ai_authored_heldout_pre_exposure_freeze_v1",
        input_git_revision=commit,
        dataset_path=dataset_path,
        dataset_sha256=_sha256(dataset_bytes),
        review_ledger_path=review_ledger_path,
        review_ledger_sha256=_sha256(ledger_bytes),
        protocol_path=protocol_path,
        protocol_sha256=_sha256(protocol_bytes),
        exposure_record_path=exposure_record_path,
    )


def verify_ai_heldout_pre_exposure_freeze(
    *, repo_root: Path, record_path: str
) -> VerifiedAIHeldoutFreeze:
    """Require a committed record and unchanged inputs before any model call."""
    root = _verified_repo_root(repo_root)
    record_file = _checked_relative_file(root, record_path)
    head = _resolve_commit(root, "HEAD")
    committed_record_bytes = _git_regular_blob(root, head, record_path)
    if _read_regular_file(root, record_file) != committed_record_bytes:
        raise ValueError("AI heldout freeze record differs from the Git HEAD blob")
    record = AIHeldoutFreezeRecord.model_validate_json(committed_record_bytes)
    commit = _resolve_commit(root, record.input_git_revision)
    if commit != record.input_git_revision or commit == head:
        raise ValueError("freeze input must be an earlier explicit Git commit")
    if _git(root, "merge-base", "--is-ancestor", commit, head, check=False).returncode != 0:
        raise ValueError("freeze input Git commit must be an ancestor of HEAD")
    paths = _checked_artifact_paths(
        root,
        record.dataset_path,
        record.review_ledger_path,
        record.protocol_path,
        record.exposure_record_path,
    )
    if record_path in {
        record.dataset_path,
        record.review_ledger_path,
        record.protocol_path,
        record.exposure_record_path,
    }:
        raise ValueError("freeze record path must differ from governed artifacts")
    _require_no_exposure(root, record.exposure_record_path, paths[3])
    dataset_bytes = _matching_input_blob(root, commit, record.dataset_path, paths[0])
    ledger_bytes = _matching_input_blob(root, commit, record.review_ledger_path, paths[1])
    protocol_bytes = _matching_input_blob(root, commit, record.protocol_path, paths[2])
    if (
        _sha256(dataset_bytes) != record.dataset_sha256
        or _sha256(ledger_bytes) != record.review_ledger_sha256
        or _sha256(protocol_bytes) != record.protocol_sha256
    ):
        raise ValueError("AI heldout freeze input hashes do not match committed artifacts")
    if not protocol_bytes.strip():
        raise ValueError("AI heldout comparison protocol must not be blank")
    reviewed = verify_ai_heldout_review(dataset_bytes, ledger_bytes)
    return VerifiedAIHeldoutFreeze(record=record, reviewed=reviewed)


def _verified_repo_root(repo_root: Path) -> Path:
    root = repo_root.resolve(strict=True)
    if repo_root.absolute() != root:
        raise ValueError("repo_root must be the canonical Git worktree root")
    actual = Path(_git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if actual != root:
        raise ValueError("repo_root must be the Git worktree root")
    return root


def _checked_artifact_paths(root: Path, *relative_paths: str) -> tuple[Path, ...]:
    if len(set(relative_paths)) != len(relative_paths):
        raise ValueError("AI heldout governed artifact paths must be distinct")
    return tuple(_checked_relative_file(root, relative) for relative in relative_paths)


def _checked_relative_file(root: Path, relative: str) -> Path:
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or PurePosixPath(relative).is_absolute()
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ValueError(f"invalid repository-relative artifact path: {relative}")
    path = root / relative
    for component in (root, *path.relative_to(root).parts):
        # Do not follow a linked directory or file into another location.
        if isinstance(component, Path):
            current = component
        else:
            current = current / component
        if current.is_symlink():
            raise ValueError(f"artifact path must not contain symlinks: {relative}")
    return path


def _read_regular_file(root: Path, path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or not path.is_relative_to(root):
        raise ValueError(f"AI heldout artifact must be a regular file: {path}")
    return path.read_bytes()


def _matching_input_blob(root: Path, commit: str, relative: str, path: Path) -> bytes:
    committed = _git_regular_blob(root, commit, relative)
    if _read_regular_file(root, path) != committed:
        raise ValueError(f"AI heldout artifact differs from input Git commit: {relative}")
    return committed


def _require_no_exposure(root: Path, relative: str, path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("AI heldout model exposure record already exists")
    if _git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", relative).stdout.strip():
        raise ValueError("AI heldout model exposure record is already committed")


def _git_regular_blob(root: Path, commit: str, relative: str) -> bytes:
    metadata = _git(root, "ls-tree", commit, "--", relative).stdout.decode().splitlines()
    if len(metadata) != 1:
        raise ValueError(f"Git commit must contain exactly one artifact: {relative}")
    mode, kind, _rest = metadata[0].split(maxsplit=2)
    if mode not in {"100644", "100755"} or kind != "blob":
        raise ValueError(f"Git artifact must be a regular file: {relative}")
    return _git(root, "show", f"{commit}:{relative}").stdout


def _resolve_commit(root: Path, revision: str) -> str:
    return _git(root, "rev-parse", f"{revision}^{{commit}}").stdout.decode().strip()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(("git", "-C", str(root), *args), capture_output=True, check=False)
    if check and result.returncode != 0:
        raise ValueError(f"Git command failed: git {' '.join(args)}")
    return result


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _normalize_nfc(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {key: _normalize_nfc(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_nfc(item) for item in value]
    return value
