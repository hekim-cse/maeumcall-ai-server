from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from evals.structured_nlu.schema import DatasetSplit, EvaluationCase, GoldDataset, ReviewStatus

ANNOTATION_GUIDELINE_V1_ID = "maeumcall-structured-nlu-annotation-v1"
ANNOTATION_GUIDELINE_V1_FINGERPRINT = (
    "0c9bc1760500fd353213b25da88b65fb40efa5f801800c4f6b3f55e20c119d0f"
)
EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1 = "evaluation-case-canonical-json-sha256-v1"
REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1 = "review-ledger-canonical-json-sha256-v1"
GOVERNED_REVIEW_SPLITS = (DatasetSplit.VALIDATION, DatasetSplit.TEST)

Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AdjudicatorId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")]
CaseId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")]
ReviewRationale = Annotated[str, Field(min_length=1, max_length=1000, pattern=r"\S")]


class ReviewLedgerEntry(BaseModel):
    """Bind one approved label decision to the exact case content that was reviewed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: CaseId
    case_fingerprint: Sha256Fingerprint
    adjudicator_id: AdjudicatorId
    adjudicated_at: AwareDatetime
    rationale: ReviewRationale
    decision: Literal["approved"]


class ReviewLedgerV1(BaseModel):
    """Immutable V1 contract for final validation and test label decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_ledger_schema_version: Literal[1]
    dataset_version: Literal[2]
    state_contract_version: Literal[2]
    annotation_guideline_id: Literal[ANNOTATION_GUIDELINE_V1_ID]
    annotation_guideline_fingerprint: Literal[ANNOTATION_GUIDELINE_V1_FINGERPRINT]
    case_fingerprint_algorithm: Literal[EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1]
    ledger_fingerprint_algorithm: Literal[REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1]
    governed_splits: tuple[Literal["validation"], Literal["test"]]
    entries: tuple[ReviewLedgerEntry, ...] = Field(
        min_length=1,
        description=(
            "Entries must be unique and sorted by case_id; the authoritative runtime "
            "validator enforces these cross-entry invariants."
        ),
    )

    @model_validator(mode="after")
    def has_one_sorted_entry_per_case(self) -> ReviewLedgerV1:
        case_ids = [entry.case_id for entry in self.entries]
        duplicates = sorted(case_id for case_id, count in Counter(case_ids).items() if count > 1)
        if duplicates:
            raise ValueError(f"review ledger case ids must be unique: {duplicates}")
        if case_ids != sorted(case_ids):
            raise ValueError("review ledger entries must be sorted by case_id")
        return self

    @property
    def fingerprint(self) -> str:
        payload = {
            "algorithm": REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1,
            "ledger": self.model_dump(mode="json"),
        }
        return _sha256_text(canonical_json_text(payload))


@dataclass(frozen=True)
class VerifiedReviewLedger:
    ledger: ReviewLedgerV1
    ledger_fingerprint: str
    guideline_fingerprint: str


def evaluation_case_fingerprint(case: EvaluationCase) -> str:
    """Identify the exact final case content approved by a ledger entry."""
    payload = {
        "algorithm": EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
        "case": case.model_dump(mode="json"),
    }
    return _sha256_text(canonical_json_text(payload))


def verify_review_ledger(
    dataset: GoldDataset,
    annotation_guideline_path: Path,
    review_ledger_path: Path,
) -> VerifiedReviewLedger:
    """Require exact, current human approval for every validation and test case."""
    guideline_bytes = read_regular_artifact(
        annotation_guideline_path,
        label="annotation guideline",
    )
    guideline_fingerprint = hashlib.sha256(guideline_bytes).hexdigest()
    if guideline_fingerprint != ANNOTATION_GUIDELINE_V1_FINGERPRINT:
        raise ValueError("annotation guideline differs from the versioned guideline fingerprint")

    ledger_bytes = read_regular_artifact(review_ledger_path, label="review ledger")
    try:
        decoded = normalize_text_tree(
            json.loads(ledger_bytes, object_pairs_hook=_object_from_unique_pairs)
        )
        if not isinstance(decoded, dict):
            raise ValueError("review ledger root must be an object")
        schema_version = decoded.get("review_ledger_schema_version")
        if schema_version != 1:
            raise ValueError(f"unsupported review ledger schema version: {schema_version}")
        ledger = ReviewLedgerV1.model_validate(decoded)
    except ValueError as exc:
        raise ValueError(f"invalid review ledger: {review_ledger_path}") from exc
    if ledger.annotation_guideline_fingerprint != guideline_fingerprint:
        raise ValueError("review ledger annotation guideline fingerprint does not match")

    governed_cases = tuple(case for case in dataset.cases if case.split in GOVERNED_REVIEW_SPLITS)
    present_governed_splits = {case.split for case in governed_cases}
    required_governed_splits = set(GOVERNED_REVIEW_SPLITS)
    if present_governed_splits != required_governed_splits:
        missing_splits = sorted(
            split.value for split in required_governed_splits - present_governed_splits
        )
        raise ValueError(
            f"review ledger requires validation and test cases: missing splits={missing_splits}"
        )
    non_adjudicated = sorted(
        case.id for case in governed_cases if case.review_status is not ReviewStatus.ADJUDICATED
    )
    if non_adjudicated:
        raise ValueError(
            f"review ledger requires adjudicated validation and test cases: {non_adjudicated}"
        )

    cases_by_id = {case.id: case for case in governed_cases}
    entries_by_id = {entry.case_id: entry for entry in ledger.entries}
    missing_entries = sorted(set(cases_by_id) - set(entries_by_id))
    unused_entries = sorted(set(entries_by_id) - set(cases_by_id))
    if missing_entries or unused_entries:
        raise ValueError(
            "review ledger must match validation and test cases exactly: "
            f"missing={missing_entries}, unused={unused_entries}"
        )

    stale_entries = sorted(
        case_id
        for case_id, case in cases_by_id.items()
        if entries_by_id[case_id].case_fingerprint != evaluation_case_fingerprint(case)
    )
    if stale_entries:
        raise ValueError(
            f"review ledger contains approvals for different case content: {stale_entries}"
        )
    return VerifiedReviewLedger(
        ledger=ledger,
        ledger_fingerprint=ledger.fingerprint,
        guideline_fingerprint=guideline_fingerprint,
    )


def serialize_review_ledger_schema() -> str:
    """Export the editor-facing review ledger schema from the code contract."""
    schema = ReviewLedgerV1.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:maeumcall:structured-nlu:review-ledger:v1"
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_regular_artifact(path: Path, *, label: str) -> bytes:
    _require_path_without_symlink_components(path, label=label)
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link: {path}")
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read {label}: {path}") from exc


def _require_path_without_symlink_components(path: Path, *, label: str) -> None:
    current = Path(path.absolute().anchor)
    for component in path.absolute().parts[1:]:
        current /= component
        if current.is_symlink():
            raise ValueError(f"{label} path must not contain symbolic links: {path}")


def normalize_text_tree(value):
    """Normalize every string and reject mapping keys that collide after NFC."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized_key = normalize_text_tree(key)
            if normalized_key in normalized:
                raise ValueError(f"text normalization produced a duplicate key: {normalized_key}")
            normalized[normalized_key] = normalize_text_tree(item)
        return normalized
    if isinstance(value, list):
        return [normalize_text_tree(item) for item in value]
    return value


def _object_from_unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"review ledger contains a duplicate JSON key: {key}")
        value[key] = item
    return value


def canonical_json_text(value) -> str:
    """Serialize semantic JSON with NFC text, stable keys, and no layout noise."""
    return json.dumps(
        normalize_text_tree(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
