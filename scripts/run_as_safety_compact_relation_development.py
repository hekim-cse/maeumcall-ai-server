"""Compare a compact relation candidate with the baseline on exposed RE/V cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.as_safety_completion_v2 import post_completion
from scripts.as_safety_pair_executor_v3 import Completion
from scripts.as_safety_preflight_v3 import run_frozen_pair
from scripts.probe_as_safety_clause_index import (
    PROMPT as BASE_PROMPT,
)
from scripts.probe_as_safety_clause_index import (
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_compact_relation import (
    PROMPT as COMPACT_PROMPT,
)
from scripts.probe_as_safety_compact_relation import (
    compact_relation_journal_schema,
    compact_relation_schema,
    route_compact_relation,
    validate_compact_relation,
)
from scripts.probe_as_safety_evidence import route_evidence
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
DATASETS = (
    DATA / "as-safety-relation-fresh-reviewed.v1.json",
    DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
)
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"


@dataclass(frozen=True)
class RequestSettings:
    max_tokens: int
    temperature: int
    repeat_penalty: float
    stop: tuple[str, ...]
    timeout_seconds: int
    server_image_digest: str


def load_policy(path: Path) -> RequestSettings:
    """Require the same bounded Q5 request settings as the prior comparison."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload != {
        "kind": "as_safety_grounded_development_request_v1",
        "server_image_digest": IMAGE,
        "max_tokens": 180,
        "temperature": 0,
        "repeat_penalty": 1.05,
        "stop": ["<|eot_id|>"],
        "timeout_seconds": 180,
        "retry_policy": "no_retry_manual_audit_on_interruption",
    }:
        raise ValueError("request policy differs")
    return RequestSettings(
        max_tokens=payload["max_tokens"],
        temperature=payload["temperature"],
        repeat_penalty=payload["repeat_penalty"],
        stop=tuple(payload["stop"]),
        timeout_seconds=payload["timeout_seconds"],
        server_image_digest=payload["server_image_digest"],
    )


def digest(path: Path) -> str:
    """Return the SHA-256 of a frozen input."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exposed_cases() -> list[dict]:
    """Load only the owner-reviewed, already-exposed RE and V cases."""
    cases = []
    for prefix, path in (("RE", DATASETS[0]), ("V", DATASETS[1])):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("provenance") != "ai_authored"
            or payload.get("review_status") != "owner_approved_for_exploration"
        ):
            raise ValueError("development dataset provenance differs")
        part = payload["cases"]
        if [case["id"] for case in part] != [f"{prefix}{index:02}" for index in range(1, 17)]:
            raise ValueError("development case order differs")
        for case in part:
            if len(split_clauses(case["user_message"])) != 2:
                raise ValueError("development case sentence count differs")
        cases.extend(part)
    return cases


def run(args: argparse.Namespace) -> None:
    """Check the committed protocol before starting a no-retry paired run."""
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if (
        protocol.get("kind") != "as_safety_compact_relation_exposed_development_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_development_only"
        or protocol.get("case_order") != "RE01-RE16,V01-V16"
        or protocol.get("pair_order") != "alternating"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != ENDPOINT
        or protocol.get("max_tokens") != 180
        or protocol.get("server_image_digest") != IMAGE
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
        raise ValueError("development protocol differs")
    if subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("tracked checkout changes before model call")
    relative = args.protocol.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != args.protocol.read_bytes():
        raise ValueError("protocol is not committed")
    if digest(args.model_path) != protocol.get("model_sha256"):
        raise ValueError("model digest differs")
    if digest(args.policy) != protocol.get("policy_sha256"):
        raise ValueError("request policy differs")
    verify_container(args.container_name, args.model_path)
    cases = load_exposed_cases()
    policy = load_policy(args.policy)
    if policy.server_image_digest != protocol["server_image_digest"]:
        raise ValueError("request image differs")

    def request(arm: str, message: str):
        clauses = split_clauses(message)
        numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
        response = post_completion(
            ENDPOINT,
            "/models/kanana.gguf",
            [
                {
                    "role": "system",
                    "content": BASE_PROMPT if arm == "baseline" else COMPACT_PROMPT,
                },
                {"role": "user", "content": numbered},
            ],
            policy,
            evidence_schema(len(clauses))
            if arm == "baseline"
            else compact_relation_schema(len(clauses)),
        )
        return Completion(response.content, response.finish_reason)

    def validate(arm: str, raw: str, message: str) -> dict:
        return (
            validate_indexed_evidence(raw, len(split_clauses(message)))
            if arm == "baseline"
            else validate_compact_relation(raw, len(split_clauses(message)))
        )

    def schema(arm: str, message: str) -> dict:
        return (
            evidence_schema(len(split_clauses(message)))
            if arm == "baseline"
            else compact_relation_journal_schema(len(split_clauses(message)))
        )

    def route(arm: str, decision: dict) -> str:
        return route_evidence(decision) if arm == "baseline" else route_compact_relation(decision)

    sources = {
        "runner_sha256": Path(__file__),
        "compact_relation_sha256": ROOT / "scripts/probe_as_safety_compact_relation.py",
        "baseline_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
        "baseline_route_sha256": ROOT / "scripts/probe_as_safety_evidence.py",
        "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
        "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
        "result_verifier_sha256": ROOT / "scripts/verify_as_safety_compact_relation_development.py",
        "re_dataset_sha256": DATASETS[0],
        "v_dataset_sha256": DATASETS[1],
        "model_sha256": args.model_path,
        "policy_sha256": args.policy,
    }
    run_frozen_pair(
        protocol_path=args.protocol,
        additional_sources=sources,
        cases=[(case["id"], case["user_message"]) for case in cases],
        journal=args.output,
        request=request,
        validate=validate,
        decision_schema=schema,
        route=route,
    )


def main() -> None:
    """Parse the local model and frozen protocol paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
