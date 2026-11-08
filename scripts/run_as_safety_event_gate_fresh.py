"""Run one owner-reviewed AI-authored A/S safety gate exploration locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from scripts.probe_as_safety_event_gate import gate_direct_safety
from scripts.probe_as_safety_evidence import post_constrained_completion, route_evidence
from scripts.run_ai_heldout_pair import _loopback_endpoint

ROOT = Path(__file__).resolve().parents[1]
MODEL_ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"
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
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reviewed_cases(path: Path) -> tuple[list[dict[str, str]], str]:
    """Reject unapproved drafts, unexpected fields, and changed case order."""
    data = path.read_bytes()
    payload = json.loads(data)
    if set(payload) != {"kind", "provenance", "review_status", "cases"}:
        raise ValueError("reviewed dataset fields differ")
    if (
        payload["kind"] != "as_safety_event_gate_ai_reviewed_v1"
        or payload["provenance"] != "ai_authored"
        or payload["review_status"] != "owner_approved_for_exploration"
    ):
        raise ValueError("dataset has not been approved for exploratory use")
    cases = payload["cases"]
    if not isinstance(cases, list) or len(cases) != 32:
        raise ValueError("expected exactly 32 reviewed EG cases")
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict) or set(case) != {"id", "user_message", "expected_route"}:
            raise ValueError("reviewed case fields differ")
        if case["id"] != f"EG{index:02}" or not isinstance(case["user_message"], str):
            raise ValueError("reviewed EG order or utterance differs")
        if not case["user_message"].strip() or len(case["user_message"]) > 1000:
            raise ValueError("reviewed utterance is empty or too long")
        if not isinstance(case["expected_route"], str) or case["expected_route"] not in ROUTES:
            raise ValueError("reviewed expected route differs")
    return cases, hashlib.sha256(data).hexdigest()


def verify_container(name: str, model: Path) -> None:
    """Bind the experiment to the declared local model server and resources."""
    observed = json.loads(
        subprocess.run(
            ("docker", "inspect", name), check=True, capture_output=True, text=True
        ).stdout
    )[0]
    host = observed["HostConfig"]
    if not observed["State"]["Running"] or observed["Image"] != IMAGE:
        raise ValueError("model server image differs")
    if host["NanoCpus"] != 2_000_000_000 or host["Memory"] != 4 * 1024**3:
        raise ValueError("model server resource bound differs")
    if host["PortBindings"] != {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18081"}]}:
        raise ValueError("model server port differs")
    if observed["Config"]["Cmd"] != SERVER_ARGS:
        raise ValueError("model server arguments differ")
    if not any(
        mount["Source"] == str(model.resolve())
        and mount["Destination"] == "/models/kanana.gguf"
        and not mount["RW"]
        for mount in observed["Mounts"]
    ):
        raise ValueError("model mount differs")


def summarize(cases: list[dict[str, str]], rows: list[dict]) -> dict:
    """Expose direct hits, false direct, confirmation, and errors separately."""
    if len(cases) != 32 or len(rows) != 32:
        raise ValueError("case and result counts differ")

    def group(start: int, stop: int) -> dict:
        part = rows[start:stop]
        return {
            "denominator": len(part),
            "model_direct": sum(row["model_route"] == "safety_action_required" for row in part),
            "gate_direct": sum(row["gate_route"] == "safety_action_required" for row in part),
            "gate_confirmation": sum(
                row["gate_route"] == "confirming_safety_status" for row in part
            ),
            "gate_normal": sum(row["gate_route"] == "collecting_service_request" for row in part),
            "errors": sum(row["error_type"] is not None for row in part),
        }

    return {
        "confirmed_hazard": group(0, 8),
        "ambiguous_hazard": group(8, 16),
        "other_source": group(16, 24),
        "nonoccurring_hazard": group(24, 32),
    }


def run(args: argparse.Namespace) -> None:
    if args.output.exists() or args.output.with_suffix(".partial.jsonl").exists():
        raise ValueError("result or partial output already exists")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("kind") != "as_safety_event_gate_fresh_protocol_v1":
        raise ValueError("unexpected protocol kind")
    if protocol.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration":
        raise ValueError("unexpected claim scope")
    if protocol.get("local_runtime") != {
        "host_port": 18081,
        "cpu_count": 2,
        "memory_bytes": 4 * 1024**3,
        "context_tokens": 4096,
        "threads": 2,
        "parallel_slots": 1,
    }:
        raise ValueError("local runtime differs from protocol")
    if protocol.get("expected_group_sizes") != {
        "confirmed_hazard": 8,
        "ambiguous_hazard": 8,
        "other_source": 8,
        "nonoccurring_hazard": 8,
    }:
        raise ValueError("reviewed group sizes differ")
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
        (ROOT / "scripts/probe_as_safety_event_gate.py", "gate_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.policy, "policy_sha256"),
        (args.model_path, "model_sha256"),
    ):
        if sha256(path) != protocol[key]:
            raise ValueError(f"{key} differs from frozen protocol")
    cases, dataset_digest = load_reviewed_cases(args.dataset)
    if dataset_digest != protocol["dataset_sha256"]:
        raise ValueError("reviewed dataset digest differs")
    if [case["expected_route"] for case in cases] != (
        ["safety_action_required"] * 8
        + ["confirming_safety_status"] * 8
        + ["collecting_service_request"] * 16
    ):
        raise ValueError("reviewed safety category order differs")
    if _loopback_endpoint(args.endpoint) != MODEL_ENDPOINT:
        raise ValueError("unexpected local endpoint")
    if protocol.get("image_digest") != IMAGE or protocol.get("max_tokens") != 100:
        raise ValueError("runtime or request override differs")
    verify_container(args.container_name, args.model_path)
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes()).model_copy(
        update={"max_tokens": 100}
    )
    rows = []
    partial = args.output.with_suffix(".partial.jsonl")
    with partial.open("x", encoding="utf-8") as file:
        for case in cases:
            clauses = split_clauses(case["user_message"])
            source = "\n".join(f"{number}. {clause}" for number, clause in enumerate(clauses, 1))
            started = time.perf_counter()
            decision = None
            gated = None
            error_type = None
            try:
                raw = post_constrained_completion(
                    MODEL_ENDPOINT,
                    "/models/kanana.gguf",
                    [{"role": "system", "content": PROMPT}, {"role": "user", "content": source}],
                    policy,
                    schema=evidence_schema(len(clauses)),
                )
                decision = validate_indexed_evidence(raw, len(clauses))
                gated = gate_direct_safety(
                    case["user_message"],
                    {
                        "route": route_evidence(decision),
                        "evidence_index": decision["evidence_index"],
                    },
                )
            except (OSError, TimeoutError, ValueError, KeyError, TypeError) as error:
                error_type = type(error).__name__
            row = {
                "case_id": case["id"],
                "clause_count": len(clauses),
                "evidence_index": decision["evidence_index"] if decision else None,
                "target": decision["target"] if decision else None,
                "assertion": decision["assertion"] if decision else None,
                "model_route": route_evidence(decision) if decision else None,
                "gate_route": gated.route if gated else None,
                "gate_reason": gated.reason if gated else None,
                "error_type": error_type,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
            rows.append(row)
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
    result = {
        "kind": "as_safety_event_gate_fresh_result_v1",
        "claim_scope": protocol["claim_scope"],
        "protocol_sha256": sha256(args.protocol),
        "dataset_sha256": dataset_digest,
        "summary": summarize(cases, rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    partial.unlink()
    print(json.dumps(result["summary"], ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "policy", "protocol", "output", "model-path"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
