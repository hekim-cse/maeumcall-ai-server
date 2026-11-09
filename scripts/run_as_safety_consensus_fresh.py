"""Run the owner-reviewed V01–V16 safety-consensus exploration locally."""

from __future__ import annotations

import argparse
import hashlib
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
from scripts.probe_as_safety_entailment_v2 import route_entailment, validate_entailment
from scripts.probe_as_safety_evidence import route_evidence
from scripts.probe_as_safety_relation import (
    PROMPT as RELATION_PROMPT,
)
from scripts.probe_as_safety_relation import (
    relation_schema,
    route_relation,
    validate_relation,
)
from scripts.run_as_safety_event_gate_fresh import verify_container

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reviewed(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if set(payload) != {
        "kind",
        "provenance",
        "review_status",
        "reviewed_date",
        "model_exposure_at_freeze",
        "cases",
    } or (
        payload["kind"] != "as_safety_relation_v2_ai_reviewed_v1"
        or payload["provenance"] != "ai_authored"
        or payload["review_status"] != "owner_approved_for_exploration"
        or payload["model_exposure_at_freeze"] != "none"
    ):
        raise ValueError("dataset provenance differs")
    cases = payload["cases"]
    if len(cases) != 16 or [case["id"] for case in cases] != [
        f"V{index:02}" for index in range(1, 17)
    ]:
        raise ValueError("expected V01–V16 in order")
    for case in cases:
        if set(case) != {
            "id",
            "user_message",
            "expected_route",
            "expected_relation",
            "expected_entailment",
        }:
            raise ValueError("reviewed case fields differ")
        message = case["user_message"]
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("reviewed message differs")
        clauses = split_clauses(message)
        if len(clauses) != 2:
            raise ValueError("reviewed clause count differs")
        gold = validate_relation(json.dumps(case["expected_relation"]), len(clauses))
        entailment_gold = validate_entailment(json.dumps(case["expected_entailment"]), len(clauses))
        if (
            route_relation(gold) != case["expected_route"]
            or route_entailment(entailment_gold) != case["expected_route"]
        ):
            raise ValueError("reviewed relation and route disagree")
    return cases


def run(args: argparse.Namespace) -> None:
    protocol = json.loads(args.protocol.read_text())
    if protocol.get("kind") != "as_safety_consensus_fresh_protocol_v1":
        raise ValueError("unexpected protocol")
    if protocol.get("claim_scope") != "ai_authored_owner_reviewed_targeted_exploration":
        raise ValueError("claim scope differs")
    if (
        protocol.get("pair_order") != "alternating"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
    ):
        raise ValueError("pair execution settings differ")
    if protocol.get("max_tokens") != 140 or protocol.get("endpoint") != ENDPOINT:
        raise ValueError("request settings differ")
    if protocol.get("case_order") != "V01-V16" or protocol.get("local_runtime") != {
        "host_port": 18081,
        "cpu_count": 2,
        "memory_bytes": 4 * 1024**3,
        "context_tokens": 4096,
        "threads": 2,
        "parallel_slots": 1,
    }:
        raise ValueError("runtime or case order differs")
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
        (ROOT / "scripts/verify_as_safety_pair_journal_v2.py", "journal_verifier_sha256"),
        (ROOT / "scripts/as_safety_consensus_v1.py", "consensus_sha256"),
        (ROOT / "scripts/probe_as_safety_clause_index.py", "baseline_sha256"),
        (ROOT / "scripts/probe_as_safety_evidence.py", "baseline_route_sha256"),
        (ROOT / "scripts/probe_as_safety_relation.py", "relation_sha256"),
        (ROOT / "scripts/probe_as_safety_entailment_v2.py", "gold_contract_sha256"),
        (ROOT / "scripts/run_as_safety_event_gate_fresh.py", "container_check_sha256"),
        (args.dataset, "dataset_sha256"),
        (args.policy, "policy_sha256"),
        (args.model_path, "model_sha256"),
    ):
        if digest(path) != protocol[key]:
            raise ValueError(f"{key} differs")
    cases = load_reviewed(args.dataset)
    verify_container(args.container_name, args.model_path)
    policy = AIHeldoutRequestPolicy.model_validate_json(args.policy.read_bytes()).model_copy(
        update={"max_tokens": 140}
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
                    "content": BASE_PROMPT if arm == "baseline" else RELATION_PROMPT,
                },
                {"role": "user", "content": numbered},
            ],
            policy,
            evidence_schema(len(clauses)) if arm == "baseline" else relation_schema(len(clauses)),
        )

    def validate(arm: str, raw: str, message: str) -> dict:
        count = len(split_clauses(message))
        return (
            validate_indexed_evidence(raw, count)
            if arm == "baseline"
            else validate_relation(raw, count)
        )

    def route(arm: str, decision: dict) -> str:
        return route_evidence(decision) if arm == "baseline" else route_relation(decision)

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
