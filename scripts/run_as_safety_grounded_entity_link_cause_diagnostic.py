"""Rerun exposed RE/V cases to decompose model abstention and anchor fallback.

The reviewed target and owner mentions are input oracles. Hazard occurrence,
relation and accepted link kind remain hidden. The journal has no raw text or
literal model quotes; quote offsets and hashes permit independent verification.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import subprocess
import time
import urllib.error
from pathlib import Path

from scripts.as_safety_completion_v2 import post_completion
from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_grounded_entity_link_v1 import (
    grounded_entity_link_messages,
    grounded_entity_link_schema,
)
from scripts.probe_as_safety_grounded_entity_link_v2 import assess_grounded_entity_link
from scripts.probe_as_safety_oracle_relation import route_with_reviewed_event
from scripts.run_as_safety_compact_relation_development import ENDPOINT, RequestSettings
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_oracle_relation_diagnostic import load_active_cases
from scripts.run_as_safety_owner_evidence_diagnostic import load_reviewed_owner_labels

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException)
CASE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 7)), *(f"RE{i:02}" for i in range(8, 12))]
    + [*(f"V{i:02}" for i in range(1, 9)), "V10", "V12", "V14", "V16"]
)
CASE_ORDER = "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
SOURCE_PATHS = {
    "runner_sha256": ROOT / "scripts/run_as_safety_grounded_entity_link_cause_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_grounded_entity_link_v2.py",
    "result_verifier_sha256": ROOT
    / "scripts/verify_as_safety_grounded_entity_link_cause_diagnostic.py",
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "owner_loader_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "oracle_candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_grounded_entity_link_cause_diagnostic.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "owner_labels_sha256": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-entity-link-request.v1.json",
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate protocol JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("nonfinite protocol JSON value")


def _json(raw: bytes) -> dict:
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_grounded_policy(path: Path) -> RequestSettings:
    """Require the isolated 320-token request policy for source quotes."""
    payload = _json(path.read_bytes())
    if payload != {
        "kind": "as_safety_grounded_entity_link_request_v1",
        "server_image_digest": IMAGE,
        "max_tokens": 320,
        "temperature": 0,
        "repeat_penalty": 1.05,
        "stop": ["<|eot_id|>"],
        "timeout_seconds": 180,
        "retry_policy": "no_retry_manual_audit_on_interruption",
    } or (
        type(payload["max_tokens"]) is not int
        or type(payload["temperature"]) is not int
        or type(payload["repeat_penalty"]) is not float
        or type(payload["timeout_seconds"]) is not int
    ):
        raise ValueError("grounded entity link request policy differs")
    return RequestSettings(
        max_tokens=payload["max_tokens"],
        temperature=payload["temperature"],
        repeat_penalty=payload["repeat_penalty"],
        stop=tuple(payload["stop"]),
        timeout_seconds=payload["timeout_seconds"],
        server_image_digest=payload["server_image_digest"],
    )


def load_gold_owner_cases(
    spans_path: Path, owner_labels_path: Path
) -> list[tuple[dict, dict, dict]]:
    """Reject unreviewed or ambiguous inputs before the first model call."""
    paired = load_active_cases(spans_path)
    labels = load_reviewed_owner_labels(owner_labels_path, paired)
    selected = []
    for (case, span), label in zip(paired, labels, strict=True):
        if not label["accepted_owner_spans"]:
            if case["id"] not in {"RE07", "V09"}:
                raise ValueError("unexpected missing gold owner")
            continue
        if len(label["accepted_owner_spans"]) != 1:
            raise ValueError("gold owner must be unique")
        selected.append((case, span, label["accepted_owner_spans"][0]))
    if len(selected) != 22 or tuple(case["id"] for case, _, _ in selected) != CASE_IDS:
        raise ValueError("grounded entity link case selection differs")
    gold = [
        span.get("reviewed_interpretation", {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        for case, span, _ in selected
    ]
    if gold.count("current") != 16 or gold.count("other") != 6:
        raise ValueError("grounded entity link denominators differ")
    return selected


def validate_protocol(
    protocol_path: Path,
    model_path: Path,
    policy_path: Path,
    spans_path: Path,
    owner_labels_path: Path,
) -> str:
    payload = protocol_path.read_bytes()
    protocol = _json(payload)
    if set(protocol) != {
        "kind",
        "claim_scope",
        "case_order",
        "endpoint",
        "retry_policy",
        "max_tokens",
        "local_runtime",
        "server_image_digest",
        "model_repo_revision",
        "model_sha256",
        *SOURCE_PATHS,
    }:
        raise ValueError("grounded entity link protocol fields differ")
    if (
        protocol.get("kind") != "as_safety_grounded_entity_link_cause_diagnostic_v2"
        or not isinstance(protocol.get("model_repo_revision"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", protocol["model_repo_revision"])
        or protocol.get("claim_scope") != "already_exposed_ai_authored_cause_diagnostic_only"
        or protocol.get("case_order") != CASE_ORDER
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != ENDPOINT
        or protocol.get("server_image_digest") != IMAGE
        or protocol.get("max_tokens") != 320
        or protocol.get("local_runtime")
        != {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        }
    ):
        raise ValueError("grounded entity link protocol differs")
    if (
        policy_path.resolve() != SOURCE_PATHS["policy_sha256"]
        or spans_path.resolve() != SOURCE_PATHS["spans_sha256"]
        or owner_labels_path.resolve() != SOURCE_PATHS["owner_labels_sha256"]
    ):
        raise ValueError("grounded entity link input path differs")
    if digest(model_path) != protocol.get("model_sha256"):
        raise ValueError("model digest differs")
    for key, path in SOURCE_PATHS.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
        committed = subprocess.run(
            ("git", "show", f"HEAD:{path.relative_to(ROOT)}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"frozen {key} is not committed")
    if subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("tracked checkout changes before model call")
    relative = protocol_path.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != payload:
        raise ValueError("grounded entity link protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _evidence_spans(user_message: str, evidence: list[dict]) -> list[dict]:
    """Store reproducible quote offsets and hashes without raw quote text."""
    clauses = split_clauses(user_message)
    spans = []
    for item in evidence:
        clause = clauses[item["clause_index"] - 1]
        quote = item["quote"]
        start = clause.index(quote)
        spans.append(
            {
                "clause_index": item["clause_index"],
                "start": start,
                "end": start + len(quote),
                "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            }
        )
    return spans


def _call(case: dict, span: dict, owner: dict, policy) -> dict:
    gold = case["expected_relation"]
    decision = relation = route = error_stage = error_code = finish_reason = http_status = None
    model_entity_link = None
    anchor_status = "not_evaluated"
    evidence_spans = []
    started = time.perf_counter()
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            grounded_entity_link_messages(
                case["user_message"],
                product_index=gold["product_index"],
                target_mention=span["target_mention"],
                owner_clause_index=owner["clause_index"],
                owner_mention=owner["mention"],
            ),
            policy,
            grounded_entity_link_schema(case["user_message"]),
        )
        finish_reason = (
            response.finish_reason if response.finish_reason in {"stop", "length"} else None
        )
        if finish_reason != "stop":
            error_stage, error_code = (
                "response",
                "finish_length" if finish_reason == "length" else "finish_other",
            )
    except ERRORS as error:
        error_stage = "response"
        if isinstance(error, urllib.error.HTTPError):
            error_code = "http_error"
            if type(error.code) is int and 100 <= error.code <= 599:
                http_status = error.code
        elif isinstance(error, (OSError, TimeoutError, http.client.HTTPException)):
            error_code = "transport_error"
        else:
            error_code = "response_error"
    else:
        if error_stage is None:
            try:
                diagnosed = assess_grounded_entity_link(
                    response.content,
                    case["user_message"],
                    product_index=gold["product_index"],
                    target_mention=span["target_mention"],
                    owner_clause_index=owner["clause_index"],
                    owner_mention=owner["mention"],
                )
                model_entity_link = diagnosed["raw_link"]
                anchor_status = diagnosed["anchor_status"]
                decision = diagnosed["effective_link"]
                evidence_spans = _evidence_spans(case["user_message"], diagnosed["evidence"])
                relation = {
                    "same_or_part": "current",
                    "distinct_item": "other",
                    "unresolved": "unknown",
                }[decision]
                route = route_with_reviewed_event(
                    {"source_relation": relation}, event_status=gold["event_status"]
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                decision = relation = route = None
                model_entity_link = None
                anchor_status = "not_evaluated"
                evidence_spans = []
                error_stage, error_code = "contract", "invalid_json"
            except ERRORS:
                decision = relation = route = None
                model_entity_link = None
                anchor_status = "not_evaluated"
                evidence_spans = []
                error_stage, error_code = "contract", "invalid_relation"
    return {
        "event": "end",
        "case_id": case["id"],
        "entity_link": decision,
        "model_entity_link": model_entity_link,
        "anchor_status": anchor_status,
        "evidence_spans": evidence_spans,
        "source_relation": relation,
        "route": route,
        "error_stage": error_stage,
        "error_code": error_code,
        "http_status": http_status,
        "finish_reason": finish_reason,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError("existing journal needs manual audit")
    selected = load_gold_owner_cases(args.spans, args.owner_labels)
    protocol_sha256 = validate_protocol(
        args.protocol, args.model_path, args.policy, args.spans, args.owner_labels
    )
    policy = load_grounded_policy(args.policy)
    verify_container(args.container_name, args.model_path)
    with args.output.open("x", encoding="utf-8") as stream:
        _append(stream, {"event": "header", "protocol_sha256": protocol_sha256})
        descriptor = os.open(args.output.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        for case, span, owner in selected:
            _append(stream, {"event": "begin", "case_id": case["id"]})
            _append(stream, _call(case, span, owner, policy))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "spans", "owner-labels", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
