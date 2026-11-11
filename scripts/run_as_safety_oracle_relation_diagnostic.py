"""Run a precommitted, exposed RE/V source-relation oracle diagnostic.

Only 24 reviewed active-event cases are called once. The journal never stores
utterances, reviewed mention text, model response bodies, or exception messages.
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
from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_oracle_relation import (
    relation_messages,
    relation_schema,
    route_with_reviewed_event,
    validate_relation,
)
from scripts.run_as_safety_compact_relation_development import ENDPOINT, load_policy
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException)
ACTIVE_IDS = tuple(
    [*(f"RE{index:02}" for index in range(1, 12))]
    + [*(f"V{index:02}" for index in range(1, 11)), "V12", "V14", "V16"]
)
SOURCE_PATHS = {
    "runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_oracle_relation_diagnostic.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_active_cases(spans_path: Path) -> list[tuple[dict, dict]]:
    """Verify all reviewed oracle inputs before any model request."""
    datasets = [
        json.loads(SOURCE_PATHS[key].read_text(encoding="utf-8"))["cases"]
        for key in ("re_dataset_sha256", "v_dataset_sha256")
    ]
    cases = [case for dataset in datasets for case in dataset]
    if [case["id"] for case in cases] != [
        *(f"RE{index:02}" for index in range(1, 17)),
        *(f"V{index:02}" for index in range(1, 17)),
    ]:
        raise ValueError("RE/V case order differs")
    active = [case for case in cases if case["expected_relation"]["event_status"] != "nonoccurring"]
    if len(active) != 24 or tuple(case["id"] for case in active) != ACTIVE_IDS:
        raise ValueError("oracle active case selection differs")
    spans_payload = json.loads(spans_path.read_text(encoding="utf-8"))
    if (
        set(spans_payload) != {"kind", "cases"}
        or spans_payload["kind"] != "as_safety_oracle_relation_spans_reviewed_v1"
        or not isinstance(spans_payload["cases"], list)
        or len(spans_payload["cases"]) != 24
    ):
        raise ValueError("reviewed span file differs")
    paired = []
    for case, span in zip(active, spans_payload["cases"], strict=True):
        required = {"id", "target_mention", "hazard_event_mention"}
        if case["id"] == "V04":
            required.add("reviewed_interpretation")
        if not isinstance(span, dict) or set(span) != required or span["id"] != case["id"]:
            raise ValueError("reviewed span order or fields differ")
        if case["id"] == "V04" and (
            span["target_mention"] != "토스터"
            or span["reviewed_interpretation"]
            != {
                "version": "v2_target_review",
                "target_relation": "current",
                "expected_route": "safety_action_required",
            }
        ):
            raise ValueError("V04 reviewed interpretation differs")
        clauses = split_clauses(case["user_message"])
        relation = case["expected_relation"]
        if relation["event_status"] not in {"observed", "uncertain"} or relation[
            "target_relation"
        ] not in {"current", "other", "unknown"}:
            raise ValueError("active oracle gold differs")
        for field, index_name in (
            ("target_mention", "product_index"),
            ("hazard_event_mention", "hazard_index"),
        ):
            mention = span[field]
            clause_index = relation[index_name]
            if (
                not isinstance(mention, str)
                or not mention.strip()
                or type(clause_index) is not int
                or not 1 <= clause_index <= len(clauses)
                or clauses[clause_index - 1].count(mention) != 1
            ):
                raise ValueError("reviewed mention does not uniquely anchor gold clause")
        paired.append((case, span))
    return paired


def validate_protocol(
    protocol_path: Path, model_path: Path, policy_path: Path, spans_path: Path
) -> str:
    """Require committed sources, settings, and model hash before exposure."""
    payload = protocol_path.read_bytes()
    protocol = json.loads(payload)
    if (
        protocol.get("kind") != "as_safety_oracle_relation_diagnostic_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_oracle_diagnostic_only"
        or protocol.get("case_order") != "RE01-RE11,V01-V10,V12,V14,V16"
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
        raise ValueError("oracle protocol differs")
    if (
        policy_path.resolve() != SOURCE_PATHS["policy_sha256"]
        or spans_path.resolve() != SOURCE_PATHS["spans_sha256"]
    ):
        raise ValueError("input path differs")
    if digest(model_path) != protocol.get("model_sha256"):
        raise ValueError("model digest differs")
    for key, path in SOURCE_PATHS.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
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
        raise ValueError("protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(file, row: dict) -> None:
    file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    file.flush()
    os.fsync(file.fileno())


def _call(case: dict, span: dict, policy) -> dict:
    """Persist only one finite decision and bounded call metadata."""
    relation = case["expected_relation"]
    decision = route = error_stage = error_type = finish_reason = http_status = None
    started = time.perf_counter()
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            relation_messages(
                case["user_message"],
                product_index=relation["product_index"],
                hazard_index=relation["hazard_index"],
                event_status=relation["event_status"],
                target_mention=span["target_mention"],
                hazard_event_mention=span["hazard_event_mention"],
            ),
            policy,
            relation_schema(),
        )
        finish_reason = (
            response.finish_reason if response.finish_reason in {"stop", "length"} else None
        )
        if finish_reason != "stop":
            raise ValueError("model did not finish normally")
    except ERRORS as error:
        error_stage, error_type = "response", type(error).__name__
        if (
            isinstance(error, urllib.error.HTTPError)
            and type(error.code) is int
            and 100 <= error.code <= 599
        ):
            http_status = error.code
    else:
        try:
            decision = validate_relation(response.content)["source_relation"]
            route = route_with_reviewed_event(
                {"source_relation": decision}, event_status=relation["event_status"]
            )
        except ERRORS as error:
            decision = route = None
            error_stage, error_type = "contract", type(error).__name__
    return {
        "event": "end",
        "case_id": case["id"],
        "source_relation": decision,
        "route": route,
        "error_stage": error_stage,
        "error_type": error_type,
        "http_status": http_status,
        "finish_reason": finish_reason,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError("existing journal needs manual audit")
    paired = load_active_cases(args.spans)
    protocol_sha256 = validate_protocol(args.protocol, args.model_path, args.policy, args.spans)
    policy = load_policy(args.policy)
    verify_container(args.container_name, args.model_path)
    with args.output.open("x", encoding="utf-8") as file:
        _append(file, {"event": "header", "protocol_sha256": protocol_sha256})
        descriptor = os.open(args.output.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        for case, span in paired:
            _append(file, {"event": "begin", "case_id": case["id"]})
            _append(file, _call(case, span, policy))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "spans", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
