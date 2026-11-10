"""Replicate only exposed RE/V candidate calls to diagnose contract failures."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import time
from pathlib import Path

from scripts.as_safety_completion_v2 import post_completion
from scripts.classify_as_safety_typed_relation_failure import classify_candidate
from scripts.probe_as_safety_clause_index import split_clauses
from scripts.probe_as_safety_typed_relation import (
    PROMPT,
    route_typed_relation,
    typed_relation_schema,
)
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_typed_relation_development import (
    ENDPOINT,
    load_exposed_cases,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
SOURCE_PATHS = {
    "runner_sha256": ROOT / "scripts/run_as_safety_typed_relation_diagnostic.py",
    "classifier_sha256": ROOT / "scripts/classify_as_safety_typed_relation_failure.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_typed_relation.py",
    "frozen_adapter_sha256": ROOT / "scripts/run_as_safety_typed_relation_development.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_typed_relation_diagnostic.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
    "prior_journal_sha256": DATA / "as-safety-typed-relation-exposed-development-result.v1.jsonl",
}
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}


def digest(path: Path) -> str:
    """Hash a frozen input file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_protocol(protocol_path: Path, model_path: Path) -> tuple[dict, str]:
    """Reject changed or uncommitted conditions before any model call."""
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if (
        protocol.get("kind") != "as_safety_typed_relation_diagnostic_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_diagnostic_replicate_only"
        or protocol.get("case_order") != "RE01-RE16,V01-V16"
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
        raise ValueError("diagnostic protocol differs")
    if digest(model_path) != protocol.get("model_sha256"):
        raise ValueError("frozen model differs")
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
    if committed != protocol_bytes:
        raise ValueError("protocol is not committed")
    return protocol, hashlib.sha256(protocol_bytes).hexdigest()


def _append(file, event: dict) -> None:
    file.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
    file.flush()
    os.fsync(file.fileno())


def run(args: argparse.Namespace) -> None:
    """Make 32 candidate-only calls and journal only finite decisions and reasons."""
    if args.output.exists():
        raise FileExistsError("existing diagnostic journal needs manual audit")
    _protocol, protocol_sha256 = validate_protocol(args.protocol, args.model_path)
    if args.policy.resolve() != SOURCE_PATHS["policy_sha256"]:
        raise ValueError("diagnostic policy path differs")
    policy = load_policy(args.policy)
    verify_container(args.container_name, args.model_path)
    cases = load_exposed_cases()
    if len(cases) != 32:
        raise ValueError("diagnostic case count differs")
    with args.output.open("x", encoding="utf-8") as file:
        _append(file, {"event": "header", "protocol_sha256": protocol_sha256})
        directory = os.open(args.output.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        for case in cases:
            case_id = case["id"]
            clauses = split_clauses(case["user_message"])
            _append(file, {"event": "begin", "case_id": case_id})
            started = time.perf_counter()
            decision = route = reason_code = finish_reason = None
            try:
                response = post_completion(
                    ENDPOINT,
                    MODEL_ID,
                    [
                        {"role": "system", "content": PROMPT},
                        {
                            "role": "user",
                            "content": "\n".join(
                                f"{index}. {clause}" for index, clause in enumerate(clauses, 1)
                            ),
                        },
                    ],
                    policy,
                    typed_relation_schema(len(clauses)),
                )
            except (OSError, TimeoutError, ValueError, TypeError, http.client.HTTPException):
                reason_code = "response_failure"
            else:
                finish_reason = (
                    response.finish_reason if response.finish_reason in {"stop", "length"} else None
                )
                if finish_reason != "stop":
                    reason_code = "response_incomplete"
                else:
                    decision, reason_code = classify_candidate(response.content, len(clauses))
                    if decision is not None:
                        schema = typed_relation_schema(len(clauses))["properties"]
                        if any(
                            not any(
                                type(value) is type(allowed) and value == allowed
                                for allowed in schema[field]["enum"]
                            )
                            for field, value in decision.items()
                        ):
                            decision, reason_code = None, "bounded_decision"
                        else:
                            route = route_typed_relation(decision)
                            if route not in ROUTES:
                                decision, route, reason_code = None, None, "other_contract"
            _append(
                file,
                {
                    "event": "end",
                    "case_id": case_id,
                    "decision": decision,
                    "route": route,
                    "reason_code": reason_code,
                    "finish_reason": finish_reason,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )


def main() -> None:
    """Parse the frozen diagnostic inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
