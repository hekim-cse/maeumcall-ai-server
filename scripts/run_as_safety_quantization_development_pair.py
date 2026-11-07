"""Pair Q4 and Q5 on already exposed A/S evidence cases for development only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import time
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts.probe_as_safety_clause_index import (
    PROMPT,
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_evidence import (
    load_reviewed_cf_dataset,
    post_constrained_completion,
    route_evidence,
)
from scripts.run_ai_heldout_pair import _loopback_endpoint

ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCOPE = "already_exposed_ai_authored_cf_development_quantization_pair_only"
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
SERVER_ARGS = [
    "-m",
    "/models/kanana.gguf",
    "-c",
    "4096",
    "-t",
    "2",
    "-np",
    "1",
    "--host",
    "0.0.0.0",
    "--port",
    "8080",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_container(name: str, port: int, model: Path) -> None:
    """Fail closed if a different server, model mount, or resource bound is used."""
    observed = json.loads(
        subprocess.run(
            ("docker", "inspect", name), check=True, capture_output=True, text=True
        ).stdout
    )[0]
    host = observed["HostConfig"]
    if not observed["State"]["Running"] or observed["Image"] != IMAGE:
        raise ValueError("local model server image differs")
    if host["NanoCpus"] != 2_000_000_000 or host["Memory"] != 4 * 1024**3:
        raise ValueError("local model server resource bound differs")
    if host["PortBindings"] != {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}:
        raise ValueError("local model server loopback port differs")
    if observed["Config"]["Cmd"] != SERVER_ARGS:
        raise ValueError("local model server arguments differ")
    if not any(
        mount["Source"] == str(model.resolve())
        and mount["Destination"] == "/models/kanana.gguf"
        and not mount["RW"]
        for mount in observed["Mounts"]
    ):
        raise ValueError("local model file mount differs")


def summarize(rows: list[dict]) -> dict:
    """Keep contract, route, and latency denominators explicit by reviewed group."""

    def group(items: list[dict]) -> dict:
        valid = [row["latency_ms"] for row in items if row["error_type"] is None]
        return {
            "denominator": len(items),
            "contract_valid": len(valid),
            "direct_safety": sum(row["route"] == "safety_action_required" for row in items),
            "safety_confirmation": sum(row["route"] == "confirming_safety_status" for row in items),
            "normal_collection": sum(row["route"] == "collecting_service_request" for row in items),
            "errors": sum(row["error_type"] is not None for row in items),
            "median_valid_latency_ms": round(statistics.median(valid), 3) if valid else None,
        }

    return {
        "confirmed_hazard": group(rows[:12]),
        "ambiguous_hazard": group(rows[12:20]),
        "no_current_hazard": group(rows[20:]),
    }


def run(args: argparse.Namespace) -> None:
    """Verify frozen inputs before alternating model request order for each case."""
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial result already exists")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("kind") != "as_safety_exposed_quantization_pair_protocol_v1":
        raise ValueError("unexpected development protocol")
    if protocol.get("claim_scope") != CLAIM_SCOPE or protocol.get("image_digest") != IMAGE:
        raise ValueError("development claim or model image differs")
    if protocol.get("local_runtime") != {
        "host_ports": {"q4": 18081, "q5": 18082},
        "cpu_per_container": 2,
        "memory_bytes_per_container": 4 * 1024**3,
        "context_tokens": 4096,
        "threads": 2,
        "parallel_slots": 1,
    } or protocol.get("request_override") != {"max_tokens": 100}:
        raise ValueError("development runtime or request override differs")
    if subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("evaluation checkout has tracked changes")
    relative = args.protocol.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != args.protocol.read_bytes():
        raise ValueError("protocol differs from committed version")
    for path, key in (
        (Path(__file__), "runner_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "indexed_probe_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "evidence_probe_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.policy, "policy_sha256"),
        (args.q4_model, "q4_model_sha256"),
        (args.q5_model, "q5_model_sha256"),
    ):
        if sha256(path) != protocol[key]:
            raise ValueError(f"{key} differs from frozen protocol")
    dataset, digest = load_reviewed_cf_dataset(args.dataset)
    if digest != protocol["dataset_sha256"]:
        raise ValueError("reviewed dataset differs")
    cases = dataset.cases
    if len(cases) != 32 or [case.id[-4:] for case in cases] != [f"cf{i:02}" for i in range(1, 33)]:
        raise ValueError("expected CF01–CF32 in order")
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes()).model_copy(
        update={"max_tokens": 100}
    )
    endpoints = {
        "q4": _loopback_endpoint(args.q4_endpoint),
        "q5": _loopback_endpoint(args.q5_endpoint),
    }
    if endpoints != {
        "q4": "http://127.0.0.1:18081/v1/chat/completions",
        "q5": "http://127.0.0.1:18082/v1/chat/completions",
    }:
        raise ValueError("unexpected local model endpoints")
    verify_container(args.q4_container, 18081, args.q4_model)
    verify_container(args.q5_container, 18082, args.q5_model)
    rows: dict[str, list[dict]] = {"q4": [], "q5": []}
    order: list[dict[str, str]] = []
    partial = args.output.with_suffix(".partial.jsonl")
    with partial.open("x", encoding="utf-8") as file:
        for index, case in enumerate(cases):
            clauses = split_clauses(case.user_message)
            source = "\n".join(f"{number}. {clause}" for number, clause in enumerate(clauses, 1))
            for role in ("q4", "q5") if index % 2 == 0 else ("q5", "q4"):
                started = time.perf_counter()
                decision = None
                error_type = None
                try:
                    raw = post_constrained_completion(
                        endpoints[role],
                        "/models/kanana.gguf",
                        [
                            {"role": "system", "content": PROMPT},
                            {"role": "user", "content": source},
                        ],
                        policy,
                        schema=evidence_schema(len(clauses)),
                    )
                    decision = validate_indexed_evidence(raw, len(clauses))
                except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
                    error_type = type(error).__name__
                row = {
                    "case_id": case.id,
                    "clause_count": len(clauses),
                    "evidence_index": decision["evidence_index"] if decision else None,
                    "target": decision["target"] if decision else None,
                    "assertion": decision["assertion"] if decision else None,
                    "route": route_evidence(decision) if decision else None,
                    "error_type": error_type,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                }
                rows[role].append(row)
                order.append({"case_id": case.id, "role": role})
                file.write(json.dumps({"role": role, "row": row}, ensure_ascii=False) + "\n")
                file.flush()
                os.fsync(file.fileno())
    result = {
        "kind": "as_safety_exposed_quantization_pair_result_v1",
        "claim_scope": CLAIM_SCOPE,
        "protocol_sha256": sha256(args.protocol),
        "dataset_sha256": digest,
        "execution_order": order,
        "summaries": {role: summarize(items) for role, items in rows.items()},
        "results": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    partial.unlink()
    print(json.dumps(result["summaries"], ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("q4-model", "q5-model", "dataset", "policy", "protocol", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("q4-endpoint", "q5-endpoint", "q4-container", "q5-container"):
        parser.add_argument(f"--{name}", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
