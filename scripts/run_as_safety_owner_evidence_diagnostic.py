"""Run the precommitted owner-evidence oracle diagnostic after owner label review.

The 24 exposed RE/V cases are called once each. The journal stores source
offsets rather than utterance, model response, or quoted source text.
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
from scripts.probe_as_safety_oracle_relation import route_with_reviewed_event
from scripts.probe_as_safety_owner_evidence import (
    owner_evidence_messages,
    owner_evidence_schema,
    validate_owner_evidence,
)
from scripts.run_as_safety_compact_relation_development import ENDPOINT, load_policy
from scripts.run_as_safety_event_gate_fresh import IMAGE, verify_container
from scripts.run_as_safety_oracle_relation_diagnostic import (
    ACTIVE_IDS,
    load_active_cases,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
MODEL_ID = "/models/kanana.gguf"
ERRORS = (OSError, TimeoutError, ValueError, KeyError, TypeError, http.client.HTTPException)
SOURCE_PATHS = {
    "runner_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_owner_evidence.py",
    "result_verifier_sha256": ROOT / "scripts/verify_as_safety_owner_evidence_diagnostic.py",
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "oracle_verifier_sha256": ROOT / "scripts/verify_as_safety_oracle_relation_diagnostic.py",
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
    """Hash an input without loading its entire body in memory."""
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_reviewed_owner_labels(path: Path, paired: list[tuple[dict, dict]]) -> list[dict]:
    """Reject AI drafts, missing cases, and owner labels inconsistent with relation gold."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload) != {"kind", "provenance", "review_status", "cases"}
        or payload["kind"] != "as_safety_owner_evidence_reviewed_v1"
        or payload["provenance"] != "ai_authored"
        or payload["review_status"] != "owner_approved_for_exploration"
        or not isinstance(payload["cases"], list)
        or len(payload["cases"]) != 24
    ):
        raise ValueError("owner evidence labels are not reviewed")
    labels = payload["cases"]
    for (case, span), label in zip(paired, labels, strict=True):
        if (
            not isinstance(label, dict)
            or set(label) != {"id", "accepted_owner_spans", "accepted_link_kinds"}
            or label["id"] != case["id"]
        ):
            raise ValueError("owner label order or fields differ")
        gold_relation = span.get("reviewed_interpretation", {}).get(
            "target_relation", case["expected_relation"]["target_relation"]
        )
        allowed_kinds = {
            "current": {"same_entity", "part_or_anaphora"},
            "other": {"explicit_other"},
            "unknown": {"unresolved"},
        }[gold_relation]
        kinds = label["accepted_link_kinds"]
        if (
            not isinstance(kinds, list)
            or not kinds
            or len(kinds) != len(set(kinds))
            or not set(kinds) <= allowed_kinds
        ):
            raise ValueError("owner label link kinds differ")
        accepted = label["accepted_owner_spans"]
        if not isinstance(accepted, list) or bool(accepted) == (gold_relation == "unknown"):
            raise ValueError("owner label span nullability differs")
        clauses = split_clauses(case["user_message"])
        seen = set()
        for item in accepted:
            if not isinstance(item, dict) or set(item) != {"clause_index", "mention"}:
                raise ValueError("owner label span fields differ")
            index, mention = item["clause_index"], item["mention"]
            if (
                type(index) is not int
                or not 1 <= index <= len(clauses)
                or not isinstance(mention, str)
                or not mention.strip()
                or clauses[index - 1].count(mention) != 1
                or (index, mention) in seen
            ):
                raise ValueError("owner label span does not uniquely anchor source")
            seen.add((index, mention))
    return labels


def validate_protocol(
    protocol_path: Path,
    model_path: Path,
    policy_path: Path,
    spans_path: Path,
    owner_labels_path: Path,
) -> str:
    """Require committed settings and all source hashes before any model request."""
    payload = protocol_path.read_bytes()
    protocol = json.loads(payload)
    if (
        protocol.get("kind") != "as_safety_owner_evidence_diagnostic_v1"
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
        raise ValueError("owner evidence protocol differs")
    if (
        policy_path.resolve() != SOURCE_PATHS["policy_sha256"]
        or spans_path.resolve() != SOURCE_PATHS["spans_sha256"]
        or owner_labels_path.resolve() != SOURCE_PATHS["owner_labels_sha256"]
    ):
        raise ValueError("owner evidence input path differs")
    if digest(model_path) != protocol.get("model_sha256"):
        raise ValueError("model digest differs")
    for key, path in SOURCE_PATHS.items():
        if digest(path) != protocol.get(key):
            raise ValueError(f"frozen {key} differs")
        relative_source = path.resolve().relative_to(ROOT)
        committed_source = subprocess.run(
            ("git", "show", f"HEAD:{relative_source}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed_source != path.read_bytes():
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
        raise ValueError("owner evidence protocol is not committed")
    return hashlib.sha256(payload).hexdigest()


def _append(stream, row: dict) -> None:
    """Durably append one bounded journal row."""
    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _call(case: dict, span: dict, policy) -> dict:
    """Make one model request and retain only finite decision metadata and offsets."""
    gold = case["expected_relation"]
    clauses = split_clauses(case["user_message"])
    prediction = route = error_stage = error_type = finish_reason = http_status = None
    index = start = end = link_kind = None
    started = time.perf_counter()
    try:
        response = post_completion(
            ENDPOINT,
            MODEL_ID,
            owner_evidence_messages(
                case["user_message"],
                product_index=gold["product_index"],
                hazard_index=gold["hazard_index"],
                event_status=gold["event_status"],
                target_mention=span["target_mention"],
                hazard_event_mention=span["hazard_event_mention"],
            ),
            policy,
            owner_evidence_schema(len(clauses)),
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
            decision = validate_owner_evidence(response.content, case["user_message"])
            prediction = decision["source_relation"]
            link_kind = decision["link_kind"]
            index = decision["source_clause_index"]
            if index is not None:
                mention = decision["source_mention"]
                start = clauses[index - 1].index(mention)
                end = start + len(mention)
            route = route_with_reviewed_event(
                {"source_relation": prediction}, event_status=gold["event_status"]
            )
        except ERRORS as error:
            prediction = route = index = start = end = link_kind = None
            error_stage, error_type = "contract", type(error).__name__
    return {
        "event": "end",
        "case_id": case["id"],
        "source_clause_index": index,
        "source_start": start,
        "source_end": end,
        "link_kind": link_kind,
        "source_relation": prediction,
        "route": route,
        "error_stage": error_stage,
        "error_type": error_type,
        "http_status": http_status,
        "finish_reason": finish_reason,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def run(args: argparse.Namespace) -> None:
    """Require human reviewed labels and frozen code before creating the journal."""
    if args.output.exists():
        raise FileExistsError("existing journal needs manual audit")
    paired = load_active_cases(args.spans)
    if tuple(case["id"] for case, _span in paired) != ACTIVE_IDS:
        raise ValueError("active order differs")
    load_reviewed_owner_labels(args.owner_labels, paired)
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
        for case, span in paired:
            _append(stream, {"event": "begin", "case_id": case["id"]})
            _append(stream, _call(case, span, policy))


def main() -> None:
    """Parse the frozen experiment inputs and start a single 24-case run."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "policy", "spans", "owner-labels", "model-path", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--container-name", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
