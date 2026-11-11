"""Run the precommitted gold-owner, link-only RE/V diagnostic once per case.

The reviewed owner mention is an input oracle. The relation and accepted link
kind remain hidden from the model. The journal contains no utterance or output.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import time
import urllib.error
from pathlib import Path

from scripts.as_safety_completion_v2 import post_completion
from scripts.probe_as_safety_gold_owner_link import (
    gold_owner_link_messages,
    gold_owner_link_schema,
    validate_gold_owner_link,
)
from scripts.probe_as_safety_oracle_relation import route_with_reviewed_event
from scripts.run_as_safety_compact_relation_development import ENDPOINT, load_policy
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_oracle_relation_diagnostic import load_active_cases
from scripts.run_as_safety_owner_evidence_diagnostic import load_reviewed_owner_labels
from scripts.verify_as_safety_gold_owner_link_diagnostic import _json

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
    "runner_sha256": ROOT / "scripts/run_as_safety_gold_owner_link_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_gold_owner_link.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_gold_owner_link_diagnostic.py",
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "owner_loader_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "oracle_candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "owner_labels_sha256": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


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
        raise ValueError("gold owner case selection differs")
    gold = [
        span.get("reviewed_interpretation", {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        for case, span, _ in selected
    ]
    if gold.count("current") != 16 or gold.count("other") != 6:
        raise ValueError("gold owner denominators differ")
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
        raise ValueError("gold owner protocol fields differ")
    if (
        protocol.get("kind") != "as_safety_gold_owner_link_diagnostic_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_oracle_diagnostic_only"
        or protocol.get("case_order") != CASE_ORDER
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != ENDPOINT
        or protocol.get("server_image_digest") != IMAGE
        or protocol.get("max_tokens") != 180
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
        raise ValueError("gold owner protocol differs")
    if (
        policy_path.resolve() != SOURCE_PATHS["policy_sha256"]
        or spans_path.resolve() != SOURCE_PATHS["spans_sha256"]
        or owner_labels_path.resolve() != SOURCE_PATHS["owner_labels_sha256"]
    ):
        raise ValueError("gold owner input path differs")
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
        raise ValueError("gold owner protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(stream, row: dict) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _call(case: dict, span: dict, owner: dict, policy) -> dict:
    gold = case["expected_relation"]
    decision = route = error_stage = error_code = finish_reason = http_status = None
    started = time.perf_counter()
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            gold_owner_link_messages(
                case["user_message"],
                product_index=gold["product_index"],
                hazard_index=gold["hazard_index"],
                event_status=gold["event_status"],
                target_mention=span["target_mention"],
                hazard_event_mention=span["hazard_event_mention"],
                owner_clause_index=owner["clause_index"],
                owner_mention=owner["mention"],
            ),
            policy,
            gold_owner_link_schema(),
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
                decision = validate_gold_owner_link(response.content)["source_relation"]
                route = route_with_reviewed_event(
                    {"source_relation": decision}, event_status=gold["event_status"]
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                decision = route = None
                error_stage, error_code = "contract", "invalid_json"
            except ERRORS:
                decision = route = None
                error_stage, error_code = "contract", "invalid_relation"
    return {
        "event": "end",
        "case_id": case["id"],
        "source_relation": decision,
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
    policy = load_policy(args.policy)
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
