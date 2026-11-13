"""Independent frozen Git inputs and reviewed-reference reconstruction."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = "evals/structured_nlu/data/ai_heldout/"
INPUTS = {
    "re_dataset": DATA + "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset": DATA + "as-safety-relation-v2-fresh-reviewed.v1.json",
    "labels": DATA + "as-safety-extraction-v2-development-labels.v1.json",
    "spans": DATA + "as-safety-oracle-relation-spans-reviewed.v1.json",
    "subject": DATA + "as-safety-owner-evidence-reviewed.v1.json",
    "owner_review": "docs/portfolio/nlu_safety_owner_resolution_review.md",
}
CASE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 7)), *(f"RE{i:02}" for i in range(8, 12))]
    + [*(f"V{i:02}" for i in range(1, 9)), "V10", "V12", "V14", "V16"]
)
CASE_ORDER = "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
STAGE1_KEYS = {
    "called",
    "status",
    "error_code",
    "error_field",
    "finish_reason",
    "latency_ms",
    "raw_sha256",
    "raw_bytes",
    "spans",
    "owner_kind",
}
STAGE2_KEYS = {
    "called",
    "status",
    "skip_reason",
    "error_code",
    "error_field",
    "finish_reason",
    "latency_ms",
    "raw_sha256",
    "raw_bytes",
    "model_relation",
    "effective_relation",
    "distinct_evidence_span",
}
SPAN_KEYS = {"clause_index", "start", "end", "quote_sha256"}
RELATIONS = {"current", "other", "unknown"}
OWNER_KINDS = {"explicit", "implicit_coreference", "unresolved"}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ERROR_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class ContractError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        self.code, self.field = code, field
        super().__init__(f"{code}: {field}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate_key", "$")
        result[key] = value
    return result


def _json(raw: str | bytes) -> object:
    if not isinstance(raw, (str, bytes)):
        raise ContractError("response_type_invalid", "$")
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ContractError("nonfinite_number", "$")
            ),
        )
    except json.JSONDecodeError as error:
        raise ContractError("invalid_json", "$") from error


def _git_bytes(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or relative.startswith("/") or ".." in Path(relative).parts:
        raise ValueError("invalid frozen Git object reference")
    return subprocess.run(
        ("git", "show", f"{commit}:{relative}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _package_sources(commit: str) -> set[str]:
    paths = subprocess.run(
        ("git", "ls-tree", "-r", "--name-only", commit, "--", "experiments/as_safety_v2"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    selected = {name for name in paths if name.endswith(".py")}
    required = {"experiments/as_safety_v2/run.py", "experiments/as_safety_v2/verify.py"}
    if not required <= selected:
        raise ValueError("frozen package lacks runner or verifier")
    for name in selected:
        tree = ast.parse(_git_bytes(commit, name), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""] if node.level == 0 else []
            else:
                continue
            if any(
                module.split(".")[0] in {"scripts", "services", "evals", "llm", "core"}
                for module in modules
            ):
                raise ValueError(f"unexpected legacy project import: {name}")
    return selected


def _clauses(message: str) -> tuple[str, ...]:
    if type(message) is not str or not message.strip():
        raise ValueError("source utterance differs")
    return tuple(part.strip() for part in re.split(r"(?<=[.!?。])\s+", message) if part.strip())


def _reference(item: object, clauses: tuple[str, ...]) -> dict:
    if type(item) is not dict or set(item) != {"clause_index", "quote"}:
        raise ValueError("reference fields differ")
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or not 1 <= index <= len(clauses) or type(quote) is not str:
        raise ValueError("reference types differ")
    start = clauses[index - 1].find(quote)
    if (
        not quote.strip()
        or quote != quote.strip()
        or start < 0
        or clauses[index - 1].find(quote, start + 1) >= 0
    ):
        raise ValueError("reference quote is not unique in source")
    return {
        "clause_index": index,
        "start": start,
        "end": start + len(quote),
        "quote_sha256": digest(quote.encode("utf-8")),
    }


def _span(item: object, clauses: tuple[str, ...]) -> dict | None:
    if item is None:
        return None
    if type(item) is not dict or set(item) != SPAN_KEYS:
        raise ValueError("recorded span fields differ")
    index, start, end, sha = (item[key] for key in ("clause_index", "start", "end", "quote_sha256"))
    if (
        type(index) is not int
        or type(start) is not int
        or type(end) is not int
        or not 1 <= index <= len(clauses)
        or not 0 <= start < end <= len(clauses[index - 1])
        or type(sha) is not str
        or not SHA_RE.fullmatch(sha)
    ):
        raise ValueError("recorded span location differs")
    quote = clauses[index - 1][start:end]
    if (
        not quote.strip()
        or quote != quote.strip()
        or clauses[index - 1].find(quote) != start
        or clauses[index - 1].find(quote, start + 1) >= 0
    ):
        raise ValueError("recorded span is not unique")
    if digest(quote.encode("utf-8")) != sha:
        raise ValueError("recorded span digest differs")
    return item


def _cases(frozen: dict[str, bytes]) -> list[dict]:
    labels = _json(frozen["labels"])
    if (
        type(labels) is not dict
        or labels.get("kind") != "as_safety_extraction_v2_development_labels_v1"
        or labels.get("provenance") != "ai_authored_already_exposed"
        or labels.get("review_status") != "derived_from_user_approved_development_annotations"
        or labels.get("source_sha256")
        != {
            "spans": digest(frozen["spans"]),
            "subject": digest(frozen["subject"]),
            "owner_review": digest(frozen["owner_review"]),
        }
    ):
        raise ValueError("frozen label provenance differs")
    sources = {}
    for key, kind in (
        ("re_dataset", "as_safety_relation_ai_reviewed_v1"),
        ("v_dataset", "as_safety_relation_v2_ai_reviewed_v1"),
    ):
        dataset = _json(frozen[key])
        if (
            type(dataset) is not dict
            or dataset.get("kind") != kind
            or dataset.get("review_status") != "owner_approved_for_exploration"
        ):
            raise ValueError("frozen source dataset differs")
        for source in dataset["cases"]:
            if source["id"] in sources:
                raise ValueError("duplicate source case")
            sources[source["id"]] = source
    rows = labels.get("cases")
    if (
        type(rows) is not list
        or any(type(row) is not dict for row in rows)
        or tuple(row.get("id") for row in rows) != CASE_IDS
    ):
        raise ValueError("frozen case order differs")
    result = []
    for row in rows:
        if set(row) != {
            "id",
            "utterance_sha256",
            "target",
            "event_reference",
            "subject_reference",
            "owner_reference",
            "relation",
            "event_status",
            "owner_referent",
            "subject_interpretation",
        }:
            raise ValueError("frozen label fields differ")
        source = sources[row["id"]]
        message = source["user_message"]
        clauses = _clauses(message)
        if digest(message.encode("utf-8")) != row["utterance_sha256"]:
            raise ValueError("frozen utterance differs")
        refs = {
            key: _reference(row[key], clauses)
            for key in ("target", "event_reference", "subject_reference", "owner_reference")
        }
        if row["owner_referent"] is not None:
            _reference(row["owner_referent"], clauses)
        if row["owner_referent"] != (
            {"clause_index": 1, "quote": "공기순환기"} if row["id"] == "RE02" else None
        ):
            raise ValueError("owner referent differs")
        if row["subject_interpretation"] != ("믹서기 바닥" if row["id"] == "V07" else None):
            raise ValueError("V07 interpretation differs")
        if row["relation"] not in {"current", "other"} or row["event_status"] not in {
            "observed",
            "uncertain",
        }:
            raise ValueError("frozen gold value differs")
        result.append(
            {
                "id": row["id"],
                "message": message,
                "clauses": clauses,
                "relation": row["relation"],
                "event_status": row["event_status"],
                "references": refs,
            }
        )
    if Counter(row["relation"] for row in result) != {"current": 16, "other": 6}:
        raise ValueError("frozen relation denominators differ")
    return result
