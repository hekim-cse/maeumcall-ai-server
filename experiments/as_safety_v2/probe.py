"""Frozen six-case, two-format development probe; never an accuracy estimate."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from experiments.as_safety_v2.candidate_ids import (
    generate_candidates,
    measure_candidate_coverage,
    stage1_id_messages,
    stage1_id_schema,
    validate_stage1_ids,
)
from experiments.as_safety_v2.cases import load_development_cases
from experiments.as_safety_v2.extraction import (
    stage1_messages,
    stage1_schema,
    validate_stage1,
)
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.run import (
    IMAGE,
    INPUTS,
    ROOT,
    RUNTIME,
    _committed,
    _git,
    _source_paths,
    digest,
    digest_file,
    verify_container,
)
from experiments.as_safety_v2.transport import (
    RequestPolicy,
    TransportError,
    post_json_completion,
)

CASE_IDS = ("RE03", "RE06", "RE09", "V01", "V04", "V07")
ORDER = tuple(
    {"case_id": case_id, "method": method}
    for index, case_id in enumerate(CASE_IDS)
    for method in (("quote", "ids") if index % 2 == 0 else ("ids", "quote"))
)
KIND = "as_safety_extraction_v2_probe_v1"
SCOPE = "already_exposed_ai_authored_development_probe_only"
POLICY = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
CANDIDATE_GENERATION = {"max_window_tokens": 5, "max_candidates": 192}
SELECTION_CRITERIA = [
    "contract_pass",
    "ebc_reference_hits",
    "candidate_recall",
    "latency_ms",
]
PROTOCOL_FIELDS = {
    "kind",
    "claim_scope",
    "case_order",
    "request_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "candidate_generation",
    "selection_criteria",
    "private_output",
}


def load_probe_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Fail before a model call unless protocol and every source byte are frozen."""
    payload = path.read_bytes()
    protocol = json.loads(payload)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("probe protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("probe commit differs")
    if (
        protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(CASE_IDS)
        or protocol["request_order"] != list(ORDER)
        or protocol["server_image_digest"] != IMAGE
        or protocol["request_policy"] != POLICY
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["candidate_generation"] != CANDIDATE_GENERATION
        or protocol["selection_criteria"] != SELECTION_CRITERIA
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("probe identity differs")
    if protocol["model_sha256"] != digest_file(model_path):
        raise ValueError("probe model differs")
    if type(protocol["input_hashes"]) is not dict or set(protocol["input_hashes"]) != set(INPUTS):
        raise ValueError("probe inputs differ")
    if type(protocol["source_manifest"]) is not dict or set(
        protocol["source_manifest"]
    ) != _source_paths(commit):
        raise ValueError("probe source manifest differs")
    current_sources = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "experiments/as_safety_v2").rglob("*.py")
    }
    if set(protocol["source_manifest"]) != current_sources:
        raise ValueError("probe package tree differs")
    for name, source in INPUTS.items():
        relative = source.relative_to(ROOT).as_posix()
        frozen = _committed(commit, relative)
        if protocol["input_hashes"][name] != digest(frozen) or frozen != source.read_bytes():
            raise ValueError(f"probe input differs: {name}")
    for relative, expected in protocol["source_manifest"].items():
        frozen = _committed(commit, relative)
        if expected != digest(frozen) or frozen != (ROOT / relative).read_bytes():
            raise ValueError(f"probe source differs: {relative}")
    relative_protocol = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative_protocol}") != payload:
        raise ValueError("probe protocol must be committed")
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("tracked checkout differs")
    return protocol, digest(payload)


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _save_raw(path: Path, content: str) -> tuple[str, int]:
    encoded = content.encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(encoded), len(encoded)


def _public_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _reference_hits(extraction: dict, case: dict) -> dict[str, bool]:
    return {
        field: extraction[field] is not None
        and (extraction[field]["clause_index"], extraction[field]["quote"])
        == (case[f"{name}_reference"]["clause_index"], case[f"{name}_reference"]["quote"])
        for field, name in (
            ("event_span", "event"),
            ("subject_span", "subject"),
            ("owner_span", "owner"),
        )
    }


def call_probe(case: dict, method: str, private_dir: Path, policy: RequestPolicy) -> dict:
    """Prompt with source and target only; use references after response validation."""
    if method not in {"quote", "ids"} or case["id"] not in CASE_IDS:
        raise ValueError("unsupported probe item")
    message = case["user_message"]
    target = case["target"]
    target_args = {"product_index": target["clause_index"], "target_mention": target["quote"]}
    candidate_set = None
    if method == "quote":
        messages = stage1_messages(message, **target_args)
        schema = stage1_schema(message)
    else:
        candidate_set = generate_candidates(message, **CANDIDATE_GENERATION)
        messages = stage1_id_messages(message, candidate_set, **target_args)
        schema = stage1_id_schema(candidate_set)
    # Candidate coverage is scored only after prompt and schema construction.
    coverage = (
        measure_candidate_coverage(
            candidate_set,
            {
                field: [case[f"{name}_reference"]]
                for field, name in (
                    ("event_span", "event"),
                    ("subject_span", "subject"),
                    ("owner_span", "owner"),
                )
            },
        )
        if candidate_set is not None
        else None
    )
    row = {
        "case_id": case["id"],
        "method": method,
        "status": "response_error",
        "error_code": None,
        "error_field": None,
        "latency_ms": None,
        "finish_reason": None,
        "raw_sha256": None,
        "raw_bytes": None,
        "spans": None,
        "owner_kind": None,
        "selected_ids": None,
        "reference_hits": None,
        "candidate_coverage": coverage,
        "candidate_source_sha256": candidate_set.source_sha256 if candidate_set else None,
    }
    started = time.perf_counter()
    try:
        completion = post_json_completion(messages, schema, policy=policy)
    except TransportError as error:
        row.update(
            error_code=error.code, latency_ms=round((time.perf_counter() - started) * 1000, 3)
        )
        return row
    # Failure to persist raw output aborts the run; the journal then remains incomplete.
    raw_hash, raw_bytes = _save_raw(
        private_dir / f"{case['id']}-{method}.raw.txt", completion.content
    )
    row.update(
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
        finish_reason=completion.finish_reason,
        raw_sha256=raw_hash,
        raw_bytes=raw_bytes,
    )
    if completion.finish_reason != "stop":
        row["error_code"] = "finish_length"
        return row
    try:
        if method == "quote":
            extraction = validate_stage1(completion.content, message, **target_args)
        else:
            validated = validate_stage1_ids(
                completion.content, message, candidate_set, **target_args
            )
            extraction = validated["extraction"]
            row["selected_ids"] = validated["selected_ids"]
    except ValidationError as error:
        row.update(status="contract_error", error_code=error.code, error_field=error.field)
        return row
    row.update(
        status="validated",
        spans={
            field: _public_span(extraction[field])
            for field in ("event_span", "subject_span", "owner_span")
        },
        owner_kind=extraction["owner_kind"],
        reference_hits=_reference_hits(extraction, case),
    )
    return row


def run_probe(
    protocol_path: Path, model_path: Path, private_dir: Path, journal_path: Path, *, container: str
) -> None:
    """Run once with no retry; interruption leaves auditable incomplete journal."""
    if ROOT == private_dir.resolve() or ROOT in private_dir.resolve().parents:
        raise ValueError("private output must be outside repository")
    protocol, protocol_hash = load_probe_protocol(protocol_path, model_path)
    verify_container(container, model_path)
    cases = {
        case["id"]: case
        for case in load_development_cases(
            **{
                "re_dataset": INPUTS["re_dataset"],
                "v_dataset": INPUTS["v_dataset"],
                "labels_path": INPUTS["labels"],
                "spans_path": INPUTS["spans"],
                "subject_path": INPUTS["subject"],
                "owner_review_path": INPUTS["owner_review"],
            }
        )
    }
    private_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    if private_dir.stat().st_mode & 0o077:
        raise ValueError("private directory permissions differ")
    policy = RequestPolicy(
        **{**protocol["request_policy"], "stop": tuple(protocol["request_policy"]["stop"])}
    )
    descriptor = os.open(journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        _append(
            stream, {"kind": KIND, "protocol_sha256": protocol_hash, "expected_calls": len(ORDER)}
        )
        for call_index, item in enumerate(ORDER, 1):
            _append(stream, {"call_index": call_index, **item, "event": "begin"})
            result = call_probe(cases[item["case_id"]], item["method"], private_dir, policy)
            _append(stream, {"call_index": call_index, "event": "end", **result})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    run_probe(args.protocol, args.model, args.private_dir, args.journal, container=args.container)


if __name__ == "__main__":
    main()
