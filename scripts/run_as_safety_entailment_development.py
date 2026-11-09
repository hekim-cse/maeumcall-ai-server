"""Pair an exposed RE baseline with a focused entailment candidate locally."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts.as_safety_completion_v2 import post_completion
from scripts.as_safety_pair_executor_v2 import run_pair_journal
from scripts.probe_as_safety_clause_index import (
    PROMPT as BASE_PROMPT,
)
from scripts.probe_as_safety_clause_index import (
    evidence_schema,
    split_clauses,
    validate_indexed_evidence,
)
from scripts.probe_as_safety_entailment_v2 import (
    PROMPT as CANDIDATE_PROMPT,
)
from scripts.probe_as_safety_entailment_v2 import (
    entailment_schema,
    route_entailment,
    validate_entailment,
)
from scripts.probe_as_safety_evidence import route_evidence
from scripts.run_as_safety_event_gate_fresh import verify_container
from scripts.run_as_safety_relation_pair import digest, load_reviewed

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"


def run(args: argparse.Namespace) -> None:
    protocol = json.loads(args.protocol.read_text())
    if protocol.get("kind") != "as_safety_entailment_exposed_development_v1":
        raise ValueError("unexpected protocol")
    if protocol.get("claim_scope") != "already_exposed_ai_authored_development_only":
        raise ValueError("unexpected claim scope")
    if protocol.get("max_tokens") != 100 or protocol.get("endpoint") != ENDPOINT:
        raise ValueError("request settings differ")
    if (
        protocol.get("pair_order") != "alternating"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
    ):
        raise ValueError("pair execution settings differ")
    if subprocess.run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("tracked checkout changes")
    relative = args.protocol.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != args.protocol.read_bytes():
        raise ValueError("protocol is not committed")
    for path, key in (
        (Path(__file__), "runner_sha256"),
        (ROOT / "scripts/as_safety_pair_executor_v2.py", "executor_sha256"),
        (ROOT / "scripts/as_safety_completion_v2.py", "completion_sha256"),
        (ROOT / "scripts/verify_as_safety_pair_journal_v2.py", "verifier_sha256"),
        (ROOT / "scripts/probe_as_safety_entailment_v2.py", "candidate_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "baseline_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "baseline_route_sha256"),
        (ROOT / "scripts/run_as_safety_event_gate_fresh.py", "container_check_sha256"),
        (ROOT / "scripts/run_as_safety_relation_pair.py", "reviewed_loader_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.policy, "policy_sha256"),
        (args.model_path, "model_sha256"),
    ):
        if digest(path) != protocol[key]:
            raise ValueError(f"{key} differs")
    cases, _ = load_reviewed(args.dataset)
    verify_container(args.container_name, args.model_path)
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes()).model_copy(
        update={"max_tokens": 100}
    )
    if policy.server_image_digest != protocol["server_image_digest"]:
        raise ValueError("server image differs")

    def request(arm: str, message: str):
        clauses = split_clauses(message)
        numbered = "\n".join(f"{index}. {clause}" for index, clause in enumerate(clauses, 1))
        return post_completion(
            ENDPOINT,
            "/models/kanana.gguf",
            [
                {
                    "role": "system",
                    "content": BASE_PROMPT if arm == "baseline" else CANDIDATE_PROMPT,
                },
                {"role": "user", "content": numbered},
            ],
            policy,
            evidence_schema(len(clauses)) if arm == "baseline" else entailment_schema(len(clauses)),
        )

    def validate(arm: str, raw: str, message: str) -> dict:
        count = len(split_clauses(message))
        return (
            validate_indexed_evidence(raw, count)
            if arm == "baseline"
            else validate_entailment(raw, count)
        )

    def route(arm: str, decision: dict) -> str:
        return route_evidence(decision) if arm == "baseline" else route_entailment(decision)

    run_pair_journal(
        cases=[(case["id"], case["user_message"]) for case in cases],
        journal=args.output,
        protocol_sha256=digest(args.protocol),
        request=request,
        validate=validate,
        route=route,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "policy", "protocol", "output", "model-path"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
