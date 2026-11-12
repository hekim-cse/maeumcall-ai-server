"""Run the two-stage A/S owner-resolution candidate on exposed RE/V cases.

Only the reviewed target mention A is an input oracle. Source B, owner C,
hazard occurrence, and relation remain hidden. This is development work.
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
from pathlib import Path

from scripts.as_safety_completion_v2 import post_completion
from scripts.probe_as_safety_oracle_relation import route_with_reviewed_event
from scripts.probe_as_safety_owner_resolution_v1 import (
    owner_resolution_stage1_messages,
    owner_resolution_stage1_schema,
    owner_resolution_stage2_messages,
    owner_resolution_stage2_schema,
    validate_stage1,
    validate_stage2,
)
from scripts.run_as_safety_compact_relation_development import ENDPOINT, RequestSettings
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_oracle_relation_diagnostic import load_active_cases
from scripts.run_as_safety_owner_evidence_diagnostic import load_reviewed_owner_labels
from scripts.verify_as_safety_owner_resolution_development import expected_manifest_paths

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
    "review": ROOT / "docs/portfolio/nlu_safety_owner_resolution_review.md",
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
        raise ValueError("owner resolution protocol fields differ")
    if (
        protocol.get("kind") != "as_safety_owner_resolution_development_v1"
        or not isinstance(protocol.get("model_repo_revision"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", protocol["model_repo_revision"])
        or protocol.get("claim_scope") != "already_exposed_ai_authored_a_only_development_only"
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
        raise ValueError("owner resolution protocol differs")
    if (
        policy_path.resolve() != INPUT_PATHS["policy"]
        or spans_path.resolve() != INPUT_PATHS["spans"]
        or owner_labels_path.resolve() != INPUT_PATHS["owner_labels"]
    ):
        raise ValueError("owner resolution input path differs")
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
        raise ValueError("owner resolution protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _journal_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _empty_stage1() -> dict:
    return {
        "called": True,
        "status": "response_error",
        "spans": None,
        "owner_kind": None,
        "cue_spans": None,
        "distinct_cue_index": None,
        "finish_reason": None,
        "latency_ms": None,
        "error": None,
    }


def _empty_stage2(*, called: bool) -> dict:
    return {
        "called": called,
        "status": "response_error" if called else "skipped",
        "skip_reason": None,
        "model_relation": None,
        "effective_relation": None,
        "finish_reason": None,
        "latency_ms": None,
        "error": None,
    }


def _request(
    messages: list[dict], schema: dict, policy
) -> tuple[object | None, str, str | None, float]:
    started = time.perf_counter()
    try:
        response = post_completion(ENDPOINT, MODEL_ID, messages, policy, schema)
    except ERRORS:
        return None, "response_error", None, round((time.perf_counter() - started) * 1000, 3)
    finish = response.finish_reason if response.finish_reason in {"stop", "length"} else None
    return (
        response,
        "validated" if finish == "stop" else "response_error",
        finish,
        round((time.perf_counter() - started) * 1000, 3),
    )


def _call(case: dict, span: dict, _owner: dict, policy) -> dict:
    gold = case["expected_relation"]
    started = time.perf_counter()
    stage1 = _empty_stage1()
    stage2 = _empty_stage2(called=False)
    stage2["skip_reason"] = "stage1_invalid"
    messages = owner_resolution_stage1_messages(
        case["user_message"],
        product_index=gold["product_index"],
        target_mention=span["target_mention"],
    )
    response, stage1["status"], stage1["finish_reason"], stage1["latency_ms"] = _request(
        messages, owner_resolution_stage1_schema(case["user_message"]), policy
    )
    validated = None
    if stage1["status"] == "validated":
        try:
            validated = validate_stage1(
                response.content,
                case["user_message"],
                product_index=gold["product_index"],
                target_mention=span["target_mention"],
            )
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            stage1["status"] = "contract_error"
    if stage1["status"] != "validated":
        stage1["error"] = stage1["status"]
    else:
        stage1["spans"] = {
            key: _journal_span(validated[key])
            for key in ("event_span", "subject_span", "owner_span")
        }
        stage1["cue_spans"] = [_journal_span(cue) for cue in validated["cue_spans"]]
        stage1["owner_kind"] = validated["owner_kind"]
        stage1["distinct_cue_index"] = validated["distinct_cue_index"]
        if any(validated[key] is None for key in ("event_span", "subject_span", "owner_span")):
            stage2["skip_reason"] = "missing_event_subject_owner"
        else:
            stage2 = _empty_stage2(called=True)
            messages = owner_resolution_stage2_messages(
                case["user_message"],
                validated,
                product_index=gold["product_index"],
                target_mention=span["target_mention"],
            )
            response2, stage2["status"], stage2["finish_reason"], stage2["latency_ms"] = _request(
                messages, owner_resolution_stage2_schema(), policy
            )
            if stage2["status"] == "validated":
                try:
                    result = validate_stage2(response2.content, validated)
                    stage2["model_relation"] = result["model_relation"]
                    stage2["effective_relation"] = result["effective_relation"]
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
                    stage2["status"] = "contract_error"
            if stage2["status"] != "validated":
                stage2["error"] = stage2["status"]
    relation = stage2["effective_relation"] if stage2["status"] == "validated" else "unknown"
    route = route_with_reviewed_event(
        {"source_relation": relation}, event_status=gold["event_status"]
    )
    return {
        "event": "end",
        "case_id": case["id"],
        "stage1": stage1,
        "stage2": stage2,
        "source_relation": relation,
        "route": route,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 3),
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
