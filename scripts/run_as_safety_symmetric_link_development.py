"""Run the symmetric A/S entity-link candidate on exposed RE/V cases.

The reviewed target and owner mentions are input oracles. Hazard occurrence and
relation remain hidden. This is development work, not independent evaluation.
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
from scripts.probe_as_safety_oracle_relation import route_with_reviewed_event
from scripts.probe_as_safety_symmetric_entity_link_v1 import (
    symmetric_entity_link_messages,
    symmetric_entity_link_schema,
    validate_symmetric_entity_link,
)
from scripts.run_as_safety_compact_relation_development import ENDPOINT, RequestSettings
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_oracle_relation_diagnostic import load_active_cases
from scripts.run_as_safety_owner_evidence_diagnostic import load_reviewed_owner_labels
from scripts.verify_as_safety_symmetric_link_development import expected_manifest_paths

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException)
CASE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 7)), *(f"RE{i:02}" for i in range(8, 12))]
    + [*(f"V{i:02}" for i in range(1, 9)), "V10", "V12", "V14", "V16"]
)
CASE_ORDER = "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
INPUT_PATHS = {
    "re_dataset": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "owner_labels": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "policy": DATA / "as-safety-grounded-entity-link-request.v1.json",
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
        "input_hashes",
        "source_manifest",
    }:
        raise ValueError("symmetric link protocol fields differ")
    if (
        protocol.get("kind") != "as_safety_symmetric_link_development_v1"
        or not isinstance(protocol.get("model_repo_revision"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", protocol["model_repo_revision"])
        or protocol.get("claim_scope") != "already_exposed_ai_authored_oracle_development_only"
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
        raise ValueError("symmetric link protocol differs")
    if (
        policy_path.resolve() != INPUT_PATHS["policy"]
        or spans_path.resolve() != INPUT_PATHS["spans"]
        or owner_labels_path.resolve() != INPUT_PATHS["owner_labels"]
    ):
        raise ValueError("symmetric link input path differs")
    if digest(model_path) != protocol.get("model_sha256"):
        raise ValueError("model digest differs")
    if set(protocol["input_hashes"]) != set(INPUT_PATHS):
        raise ValueError("input hash fields differ")
    manifest_paths = expected_manifest_paths()
    if set(protocol["source_manifest"]) != manifest_paths:
        raise ValueError("source manifest paths differ")
    for key, path in INPUT_PATHS.items():
        if digest(path) != protocol["input_hashes"][key]:
            raise ValueError(f"frozen input {key} differs")
    for relative in sorted(manifest_paths):
        path = ROOT / relative
        if digest(path) != protocol["source_manifest"][relative]:
            raise ValueError(f"frozen source {relative} differs")
    for path in [*INPUT_PATHS.values(), *(ROOT / p for p in manifest_paths)]:
        committed = subprocess.run(
            ("git", "show", f"HEAD:{path.relative_to(ROOT)}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"frozen {path.relative_to(ROOT)} is not committed")
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
        raise ValueError("symmetric link protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _call(case: dict, span: dict, owner: dict, policy) -> dict:
    gold = case["expected_relation"]
    decision = relation = route = error_stage = error_code = finish_reason = http_status = None
    same_or_part_answer = distinct_item_answer = None
    started = time.perf_counter()
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            symmetric_entity_link_messages(
                case["user_message"],
                product_index=gold["product_index"],
                target_mention=span["target_mention"],
                owner_clause_index=owner["clause_index"],
                owner_mention=owner["mention"],
            ),
            policy,
            symmetric_entity_link_schema(),
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
                validated = validate_symmetric_entity_link(response.content)
                same_or_part_answer = validated["same_or_part_answer"]
                distinct_item_answer = validated["distinct_item_answer"]
                decision = validated["entity_link"]
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
                same_or_part_answer = distinct_item_answer = None
                error_stage, error_code = "contract", "invalid_json"
            except ERRORS:
                decision = relation = route = None
                same_or_part_answer = distinct_item_answer = None
                error_stage, error_code = "contract", "invalid_relation"
    return {
        "event": "end",
        "case_id": case["id"],
        "entity_link": decision,
        "same_or_part_answer": same_or_part_answer,
        "distinct_item_answer": distinct_item_answer,
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
