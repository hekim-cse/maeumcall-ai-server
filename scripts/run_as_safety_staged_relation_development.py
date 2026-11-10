"""Compare baseline with a two-stage A/S source candidate on exposed RE/V only.

The durable journal stores finite decisions and per-stage metadata, never model
text. A begin event precedes every arm, so interrupted calls are not replayed.
"""

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
from scripts.probe_as_safety_clause_index import (
    PROMPT as BASE_PROMPT,
)
from scripts.probe_as_safety_clause_index import (
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_evidence import route_evidence
from scripts.probe_as_safety_staged_relation import (
    EVENT_PROMPT,
    SOURCE_PROMPT,
    combine_stages,
    event_schema,
    route_staged,
    source_schema,
    validate_event,
    validate_source,
)
from scripts.run_as_safety_compact_relation_development import (
    ENDPOINT,
    load_exposed_cases,
    load_policy,
)
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException)
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
SOURCE_PATHS = {
    "runner_sha256": ROOT / "scripts/run_as_safety_staged_relation_development.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_staged_relation.py",
    "baseline_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "baseline_route_sha256": ROOT / "scripts/probe_as_safety_evidence.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/run_as_safety_compact_relation_development.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_staged_relation_development.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-development-request.v1.json",
}


def digest(path: Path) -> str:
    """Hash large models without reading the whole file into memory."""
    hash_value = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def validate_protocol(protocol_path: Path, model_path: Path, policy_path: Path) -> str:
    """Require a committed, clean, source-hashed protocol before exposure."""
    payload = protocol_path.read_bytes()
    protocol = json.loads(payload)
    if (
        protocol.get("kind") != "as_safety_staged_exposed_development_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_development_only"
        or protocol.get("case_order") != "RE01-RE16,V01-V16"
        or protocol.get("pair_order") != "alternating"
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
        raise ValueError("staged protocol differs")
    if policy_path.resolve() != SOURCE_PATHS["policy_sha256"]:
        raise ValueError("policy path differs")
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


def _skipped(reason: str) -> dict:
    return {
        "called": False,
        "decision": None,
        "error_stage": None,
        "error_type": None,
        "finish_reason": None,
        "latency_ms": None,
        "skip_reason": reason,
    }


def _call_stage(
    *, prompt: str, user: str, schema: dict, validate, clause_count: int, policy
) -> dict:
    """Return only bounded stage output and finite failure metadata."""
    started = time.perf_counter()
    decision = error_stage = error_type = finish_reason = None
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
            policy,
            schema,
        )
        finish_reason = (
            response.finish_reason if response.finish_reason in {"stop", "length"} else None
        )
        if finish_reason != "stop":
            raise ValueError("model did not finish normally")
    except ERRORS as error:
        error_stage, error_type = "response", type(error).__name__
    else:
        try:
            decision = validate(response.content, clause_count)
        except ERRORS as error:
            error_stage, error_type = "contract", type(error).__name__
    return {
        "called": True,
        "decision": decision,
        "error_stage": error_stage,
        "error_type": error_type,
        "finish_reason": finish_reason,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "skip_reason": None,
    }


def _run_arm(arm: str, message: str, policy) -> dict:
    """Call the baseline once or the candidate's conditional stages."""
    clauses = split_clauses(message)
    numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
    started = time.perf_counter()
    error_stage = error_type = None
    if arm == "baseline":
        first = _call_stage(
            prompt=BASE_PROMPT,
            user=numbered,
            schema=evidence_schema(len(clauses)),
            validate=validate_indexed_evidence,
            clause_count=len(clauses),
            policy=policy,
        )
        second = _skipped("baseline_single_call")
        decision = first["decision"]
        route = None
    else:
        first = _call_stage(
            prompt=EVENT_PROMPT,
            user=numbered,
            schema=event_schema(len(clauses)),
            validate=validate_event,
            clause_count=len(clauses),
            policy=policy,
        )
        second = _skipped("upstream_failure")
        decision = route = None
        if first["decision"] is not None:
            event = first["decision"]
            if event["event_status"] in {"observed", "uncertain"}:
                second = _call_stage(
                    prompt=SOURCE_PROMPT,
                    user=f"{numbered}\nevent_index={event['event_index']}",
                    schema=source_schema(len(clauses)),
                    validate=validate_source,
                    clause_count=len(clauses),
                    policy=policy,
                )
                if second["decision"] is not None:
                    try:
                        decision = combine_stages(event, second["decision"])
                    except ERRORS as error:
                        error_stage, error_type = "combination", type(error).__name__
            else:
                second = _skipped("no_active_event")
                try:
                    decision = combine_stages(event, None)
                except ERRORS as error:
                    error_stage, error_type = "combination", type(error).__name__
    if decision is not None:
        try:
            route = route_evidence(decision) if arm == "baseline" else route_staged(decision)
            if route not in ROUTES:
                raise ValueError("route outside finite choices")
        except ERRORS as error:
            decision = route = None
            error_stage, error_type = "routing", type(error).__name__
    if error_stage is None:
        failed = first if first["error_stage"] is not None else second
        if failed["error_stage"] is not None:
            prefix = "stage1" if failed is first else "stage2"
            error_stage = f"{prefix}_{failed['error_stage']}"
            error_type = failed["error_type"]
    return {
        "event": "end",
        "decision": decision,
        "route": route,
        "error_stage": error_stage,
        "error_type": error_type,
        "stage1": first,
        "stage2": second,
        "call_count": int(first["called"]) + int(second["called"]),
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run(args: argparse.Namespace) -> None:
    """Execute 32 exposed pairs once, with durable begin events."""
    if args.output.exists():
        raise FileExistsError("existing journal needs manual audit")
    protocol_sha256 = validate_protocol(args.protocol, args.model_path, args.policy)
    policy = load_policy(args.policy)
    verify_container(args.container_name, args.model_path)
    cases = load_exposed_cases()
    if len(cases) != 32:
        raise ValueError("development case count differs")
    with args.output.open("x", encoding="utf-8") as file:
        _append(file, {"event": "header", "protocol_sha256": protocol_sha256})
        descriptor = os.open(args.output.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        for case_index, case in enumerate(cases):
            order = ("baseline", "candidate") if case_index % 2 == 0 else ("candidate", "baseline")
            for arm in order:
                _append(file, {"event": "begin", "case_id": case["id"], "arm": arm})
                row = _run_arm(arm, case["user_message"], policy)
                _append(file, {"case_id": case["id"], "arm": arm, **row})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
