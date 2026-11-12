"""Independently verify a frozen A/S owner-resolution development run."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from scripts.probe_as_safety_clause_index import split_clauses

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
CASE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 7)), *(f"RE{i:02}" for i in range(8, 12))]
    + [*(f"V{i:02}" for i in range(1, 9)), "V10", "V12", "V14", "V16"]
)
SOURCES = {
    "runner_sha256": ROOT / "scripts/run_as_safety_owner_resolution_development.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_owner_resolution_v1.py",
    "result_verifier_sha256": Path(__file__),
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "owner_loader_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "oracle_candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_owner_resolution_development.py",
    "completion_type_sha256": ROOT / "scripts/as_safety_pair_executor_v2.py",
    "endpoint_guard_sha256": ROOT / "scripts/run_ai_heldout_pair.py",
    "request_policy_type_sha256": ROOT / "evals/structured_nlu/ai_heldout.py",
    "container_check_sha256": ROOT / "scripts/run_as_safety_event_gate_fresh.py",
    "case_loader_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "re_dataset_sha256": DATA / "as-safety-relation-fresh-reviewed.v1.json",
    "v_dataset_sha256": DATA / "as-safety-relation-v2-fresh-reviewed.v1.json",
    "spans_sha256": DATA / "as-safety-oracle-relation-spans-reviewed.v1.json",
    "owner_labels_sha256": DATA / "as-safety-owner-evidence-reviewed.v1.json",
    "policy_sha256": DATA / "as-safety-grounded-entity-link-request.v1.json",
    "review_sha256": ROOT / "docs/portfolio/nlu_safety_owner_resolution_review.md",
}
ROOT_MODULES = (SOURCES["runner_sha256"], SOURCES["candidate_sha256"], Path(__file__))
DATA_FILES = (
    SOURCES["re_dataset_sha256"],
    SOURCES["v_dataset_sha256"],
    SOURCES["spans_sha256"],
    SOURCES["owner_labels_sha256"],
    SOURCES["policy_sha256"],
    SOURCES["review_sha256"],
)
LOCAL_PACKAGES = frozenset({"scripts", "services", "evals", "llm", "core"})
# This legacy helper is imported for shared constants/types only. Its _run_case
# dynamic analyzer dispatch is not invoked by the symmetric diagnostic.
INACTIVE_DYNAMIC_IMPORTS = {
    "scripts/run_ai_heldout_pair.py": {
        "importlib.import_module('services.flow.service_workflow.structured')",
        "importlib.import_module(module_name)",
    },
    "scripts/probe_gguf_structured_nlu.py": {
        "importlib.import_module('services.flow.service_workflow.structured')",
        "importlib.import_module(module_name)",
    },
}
END_FIELDS = {
    "event",
    "case_id",
    "stage1",
    "stage2",
    "source_relation",
    "route",
    "total_latency_ms",
}
STAGE1_FIELDS = {
    "called",
    "status",
    "spans",
    "owner_kind",
    "cue_spans",
    "distinct_cue_index",
    "finish_reason",
    "latency_ms",
    "error",
}
STAGE2_FIELDS = {
    "called",
    "status",
    "skip_reason",
    "model_relation",
    "effective_relation",
    "finish_reason",
    "latency_ms",
    "error",
}
SPAN_FIELDS = {"clause_index", "start", "end", "quote_sha256"}
OWNER_KINDS = frozenset({"explicit", "implicit_coreference", "unresolved"})
RELATIONS = frozenset({"current", "other", "unknown"})
INPUTS = {
    "re_dataset": SOURCES["re_dataset_sha256"],
    "v_dataset": SOURCES["v_dataset_sha256"],
    "spans": SOURCES["spans_sha256"],
    "owner_labels": SOURCES["owner_labels_sha256"],
    "policy": SOURCES["policy_sha256"],
    "review": SOURCES["review_sha256"],
}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: str | bytes):
    return json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite JSON value")),
    )


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _module_files(name: str, *, strict: bool = True) -> set[Path]:
    """Resolve an absolute project-local module, including package initializers."""
    parts = name.split(".")
    if parts[0] not in LOCAL_PACKAGES:
        return set()
    base = ROOT.joinpath(*parts)
    selected = set()
    module_file = base.with_suffix(".py")
    package_file = base / "__init__.py"
    if module_file.is_file():
        selected.add(module_file)
    if package_file.is_file():
        selected.add(package_file)
    for depth in range(1, len(parts)):
        initializer = ROOT.joinpath(*parts[:depth]) / "__init__.py"
        if initializer.is_file():
            selected.add(initializer)
    if not selected and base.is_dir():
        return set()
    if not selected and strict:
        raise ValueError(f"missing project-local import: {name}")
    return selected


def _imported_files(path: Path) -> set[Path]:
    """Include static imports and reject executable dynamic import calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[Path] = set()
    relative = path.relative_to(ROOT).with_suffix("")
    package = list(relative.parts if path.name == "__init__.py" else relative.parts[:-1])
    if path.name == "__init__.py":
        package.pop()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "import_module"}
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            relative_name = path.relative_to(ROOT).as_posix()
            if ast.unparse(node) not in INACTIVE_DYNAMIC_IMPORTS.get(relative_name, set()):
                raise ValueError(f"dynamic import in {relative_name}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.update(_module_files(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level > len(package):
                    raise ValueError(f"relative import escapes source root: {path}")
                prefix = package[: len(package) - node.level + 1]
                base = ".".join([*prefix, *(node.module.split(".") if node.module else [])])
            else:
                base = node.module or ""
            if base:
                imported.update(_module_files(base))
            for alias in node.names:
                if alias.name != "*":
                    imported.update(_module_files(f"{base}.{alias.name}", strict=False))
    return imported


def expected_manifest_paths() -> set[str]:
    """Return the exact file set the protocol must hash before model calls."""
    pending = list(ROOT_MODULES)
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        if not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"missing source dependency: {path}")
        seen.add(path)
        pending.extend(_imported_files(path) - seen)
    return {path.relative_to(ROOT).as_posix() for path in seen}


def _require_committed(path: Path) -> None:
    relative = path.resolve().relative_to(ROOT)
    committed = subprocess.run(
        ("git", "show", f"HEAD:{relative}"), cwd=ROOT, check=True, capture_output=True
    ).stdout
    if committed != path.read_bytes():
        raise ValueError(f"frozen {relative} is not committed")


def _route(source_relation: str, status: str) -> str:
    if source_relation == "other":
        return "collecting_service_request"
    if source_relation == "current" and status == "observed":
        return "safety_action_required"
    return "confirming_safety_status"


def _reviewed_cases() -> list[dict]:
    datasets = [
        _json(SOURCES[key].read_text(encoding="utf-8"))["cases"]
        for key in ("re_dataset_sha256", "v_dataset_sha256")
    ]
    all_cases = [case for dataset in datasets for case in dataset]
    if [case["id"] for case in all_cases] != [
        *(f"RE{i:02}" for i in range(1, 17)),
        *(f"V{i:02}" for i in range(1, 17)),
    ]:
        raise ValueError("RE/V source order differs")
    active = [
        case for case in all_cases if case["expected_relation"]["event_status"] != "nonoccurring"
    ]
    if len(active) != 24:
        raise ValueError("active source denominator differs")
    spans = _json(SOURCES["spans_sha256"].read_text(encoding="utf-8"))
    owners = _json(SOURCES["owner_labels_sha256"].read_text(encoding="utf-8"))
    if (
        set(spans) != {"kind", "cases"}
        or spans["kind"] != "as_safety_oracle_relation_spans_reviewed_v1"
        or set(owners) != {"kind", "provenance", "review_status", "cases"}
        or owners["kind"] != "as_safety_owner_evidence_reviewed_v1"
        or owners["provenance"] != "ai_authored"
        or owners["review_status"] != "owner_approved_for_exploration"
        or len(spans["cases"]) != 24
        or len(owners["cases"]) != 24
    ):
        raise ValueError("reviewed source shape differs")
    selected = []
    for case, span, owner in zip(active, spans["cases"], owners["cases"], strict=True):
        case_id = case["id"]
        if span["id"] != case_id or owner["id"] != case_id:
            raise ValueError("reviewed source order differs")
        if set(span) != (
            {"id", "target_mention", "hazard_event_mention", "reviewed_interpretation"}
            if case_id == "V04"
            else {"id", "target_mention", "hazard_event_mention"}
        ):
            raise ValueError("reviewed span fields differ")
        if set(owner) != {"id", "accepted_owner_spans", "accepted_link_kinds"}:
            raise ValueError("reviewed owner fields differ")
        if case_id == "V04" and (
            span["target_mention"] != "토스터"
            or span["reviewed_interpretation"]
            != {
                "version": "v2_target_review",
                "target_relation": "current",
                "expected_route": "safety_action_required",
            }
        ):
            raise ValueError("V04 reviewed overlay differs")
        gold = case["expected_relation"]
        relation = span.get("reviewed_interpretation", {}).get(
            "target_relation", gold["target_relation"]
        )
        status = gold["event_status"]
        if relation not in {"current", "other", "unknown"} or status not in {
            "observed",
            "uncertain",
        }:
            raise ValueError("active relation/status differs")
        if case["expected_route"] != _route(gold["target_relation"], status):
            raise ValueError("source relation/route differs")
        if case_id == "V04" and span["reviewed_interpretation"]["expected_route"] != _route(
            relation, status
        ):
            raise ValueError("V04 overlay route differs")
        if case_id == "RE06" and (relation != "current" or status != "uncertain"):
            raise ValueError("RE06 conditional gold differs")
        clauses = split_clauses(case["user_message"])
        for name, index_name in (
            ("target_mention", "product_index"),
            ("hazard_event_mention", "hazard_index"),
        ):
            mention, index = span[name], gold[index_name]
            if (
                not isinstance(mention, str)
                or not mention.strip()
                or type(index) is not int
                or not 1 <= index <= len(clauses)
                or clauses[index - 1].count(mention) != 1
            ):
                raise ValueError("reviewed oracle mention differs")
        accepted = owner["accepted_owner_spans"]
        if case_id in {"RE07", "V09"}:
            if (
                relation != "unknown"
                or accepted != []
                or owner["accepted_link_kinds"] != ["unresolved"]
            ):
                raise ValueError("excluded unknown gold differs")
            continue
        if not isinstance(accepted, list) or len(accepted) != 1:
            raise ValueError("selected owner cardinality differs")
        entry = accepted[0]
        if not isinstance(entry, dict) or set(entry) != {"clause_index", "mention"}:
            raise ValueError("owner span fields differ")
        index, mention = entry["clause_index"], entry["mention"]
        if (
            type(index) is not int
            or not 1 <= index <= len(clauses)
            or not isinstance(mention, str)
            or not mention.strip()
            or clauses[index - 1].count(mention) != 1
        ):
            raise ValueError("owner mention anchor differs")
        allowed_kinds = {
            "current": {"same_entity", "part_or_anaphora"},
            "other": {"explicit_other"},
        }[relation]
        kinds = owner["accepted_link_kinds"]
        if (
            not isinstance(kinds, list)
            or not kinds
            or len(kinds) != len(set(kinds))
            or not set(kinds) <= allowed_kinds
        ):
            raise ValueError("owner link annotation differs")
        selected.append(
            {
                "id": case_id,
                "user_message": case["user_message"],
                "gold_relation": relation,
                "gold_route": _route(relation, status),
                "event_status": status,
            }
        )
    if tuple(item["id"] for item in selected) != CASE_IDS or Counter(
        item["gold_relation"] for item in selected
    ) != {"current": 16, "other": 6}:
        raise ValueError("selected denominator differs")
    if Counter((item["gold_relation"], item["event_status"]) for item in selected) != {
        ("current", "observed"): 13,
        ("current", "uncertain"): 3,
        ("other", "observed"): 5,
        ("other", "uncertain"): 1,
    }:
        raise ValueError("selected relation/status denominators differ")
    return selected


def _latency(value: object, *, allow_zero: bool = False) -> float:
    if type(value) not in {int, float} or not (0 <= value < 86_400_000):
        raise ValueError("nonfinite stage latency")
    if not allow_zero and value == 0:
        raise ValueError("called stage has zero latency")
    return float(value)


def _span_quote(span: object, clauses: tuple[str, ...]) -> str | None:
    if span is None:
        return None
    if not isinstance(span, dict) or set(span) != SPAN_FIELDS:
        raise ValueError("source span fields differ")
    index, start, end = span["clause_index"], span["start"], span["end"]
    quote_hash = span["quote_sha256"]
    if (
        type(index) is not int
        or not 1 <= index <= len(clauses)
        or type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(clauses[index - 1])
        or type(quote_hash) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", quote_hash)
    ):
        raise ValueError("source span index or hash differs")
    quote = clauses[index - 1][start:end]
    if (
        not quote.strip()
        or quote != quote.strip()
        or clauses[index - 1].count(quote) != 1
        or hashlib.sha256(quote.encode("utf-8")).hexdigest() != quote_hash
    ):
        raise ValueError("source quote anchor differs")
    return quote


def _check_end(row: dict, case: dict) -> None:
    if (
        not isinstance(row, dict)
        or set(row) != END_FIELDS
        or row["event"] != "end"
        or row["case_id"] != case["id"]
    ):
        raise ValueError("end row shape/order differs")
    first, second = row["stage1"], row["stage2"]
    if not isinstance(first, dict) or set(first) != STAGE1_FIELDS:
        raise ValueError("stage one fields differ")
    if not isinstance(second, dict) or set(second) != STAGE2_FIELDS:
        raise ValueError("stage two fields differ")
    if (
        first["called"] is not True
        or type(first["status"]) is not str
        or first["status"]
        not in {
            "validated",
            "response_error",
            "contract_error",
        }
    ):
        raise ValueError("stage one call/status differs")
    first_latency = _latency(first["latency_ms"], allow_zero=True)
    total_latency = _latency(row["total_latency_ms"])
    if first["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("stage one finish reason differs")
    if first["status"] == "validated":
        if first["error"] is not None or first["finish_reason"] != "stop":
            raise ValueError("validated stage one metadata differs")
        spans = first["spans"]
        if not isinstance(spans, dict) or set(spans) != {
            "event_span",
            "subject_span",
            "owner_span",
        }:
            raise ValueError("stage one span fields differ")
        kind = first["owner_kind"]
        cues = first["cue_spans"]
        cue_index = first["distinct_cue_index"]
        if type(kind) is not str or kind not in OWNER_KINDS:
            raise ValueError("owner kind differs")
        if not isinstance(cues, list) or len(cues) > 2 or any(cue is None for cue in cues):
            raise ValueError("cue span count differs")
        clauses = split_clauses(case["user_message"])
        for span in (*spans.values(), *cues):
            _span_quote(span, clauses)
        if cue_index is not None and (
            type(cue_index) is not int or not 0 <= cue_index < len(cues) or kind != "explicit"
        ):
            raise ValueError("distinct cue index differs")
        if (spans["owner_span"] is None) != (kind == "unresolved"):
            raise ValueError("owner span/kind differs")
    elif (
        first["error"] != first["status"]
        or first["spans"] is not None
        or first["owner_kind"] is not None
        or first["cue_spans"] is not None
        or first["distinct_cue_index"] is not None
    ):
        raise ValueError("failed stage one has extraction")
    if first["status"] == "contract_error" and first["finish_reason"] != "stop":
        raise ValueError("stage one contract finish differs")
    if first["status"] == "response_error" and first["finish_reason"] == "stop":
        raise ValueError("stage one response finish differs")

    should_call_second = first["status"] == "validated" and all(
        first["spans"][key] is not None for key in ("event_span", "subject_span", "owner_span")
    )
    if type(second["called"]) is not bool or second["called"] != should_call_second:
        raise ValueError("stage two call gate differs")
    if not should_call_second:
        expected_skip = (
            "stage1_invalid" if first["status"] != "validated" else "missing_event_subject_owner"
        )
        if (
            second["status"] != "skipped"
            or second["skip_reason"] != expected_skip
            or second["model_relation"] is not None
            or second["effective_relation"] is not None
            or second["finish_reason"] is not None
            or second["error"] is not None
            or second["latency_ms"] is not None
        ):
            raise ValueError("stage two skip state differs")
        second_latency = 0.0
        expected_relation = "unknown"
    else:
        second_latency = _latency(second["latency_ms"], allow_zero=True)
        if (
            second["skip_reason"] is not None
            or type(second["status"]) is not str
            or second["status"]
            not in {
                "validated",
                "response_error",
                "contract_error",
            }
        ):
            raise ValueError("stage two status differs")
        if second["finish_reason"] not in {None, "stop", "length"}:
            raise ValueError("stage two finish reason differs")
        if second["status"] == "validated":
            model_relation = second["model_relation"]
            if (
                second["error"] is not None
                or second["finish_reason"] != "stop"
                or type(model_relation) is not str
                or model_relation not in RELATIONS
            ):
                raise ValueError("validated stage two decision differs")
            expected_relation = (
                "unknown"
                if model_relation == "other"
                and not (
                    first["owner_kind"] == "explicit" and first["distinct_cue_index"] is not None
                )
                else model_relation
            )
            if second["effective_relation"] != expected_relation:
                raise ValueError("stage two effective relation differs")
        else:
            if (
                second["error"] != second["status"]
                or second["model_relation"] is not None
                or second["effective_relation"] is not None
            ):
                raise ValueError("failed stage two has decision")
            if second["status"] == "contract_error" and second["finish_reason"] != "stop":
                raise ValueError("stage two contract finish differs")
            if second["status"] == "response_error" and second["finish_reason"] == "stop":
                raise ValueError("stage two response finish differs")
            expected_relation = "unknown"
    if total_latency + 2 < first_latency + second_latency:
        raise ValueError("total latency shorter than staged calls")
    if row["source_relation"] != expected_relation or row["route"] != _route(
        expected_relation, case["event_status"]
    ):
        raise ValueError("final relation/route differs")


def _aggregate(rows: list[dict]) -> dict:
    return {
        "denominator": len(rows),
        "relation_correct": sum(row["predicted_relation"] == row["gold_relation"] for row in rows),
        "route_correct": sum(row["predicted_route"] == row["gold_route"] for row in rows),
        "errors": sum(row["stage1_error"] or row["stage2_error"] for row in rows),
        "stage1_errors": sum(row["stage1_error"] for row in rows),
        "stage2_errors": sum(row["stage2_error"] for row in rows),
        "stage2_skipped": sum(row["stage2_skipped"] for row in rows),
        "calls": sum(row["calls"] for row in rows),
        "stage1_status_counts": dict(Counter(row["stage1_status"] for row in rows)),
        "stage2_status_counts": dict(Counter(row["stage2_status"] for row in rows)),
        "stage2_skip_reason_counts": dict(
            Counter(row["stage2_skip_reason"] for row in rows if row["stage2_skipped"])
        ),
        "stage1_event_present": sum(row["stage1_event_present"] for row in rows),
        "stage1_subject_present": sum(row["stage1_subject_present"] for row in rows),
        "stage1_owner_present": sum(row["stage1_owner_present"] for row in rows),
        "unknown_outputs": sum(row["predicted_relation"] == "unknown" for row in rows),
        "gold_relation_counts": dict(Counter(row["gold_relation"] for row in rows)),
        "predicted_relation_counts": dict(Counter(row["predicted_relation"] for row in rows)),
    }


def verify(protocol_path: Path, journal_path: Path) -> dict:
    protocol_bytes = protocol_path.read_bytes()
    protocol = _json(protocol_bytes)
    if (
        set(protocol)
        != {
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
            "input_hashes",
            "source_manifest",
        }
        or not isinstance(protocol.get("model_repo_revision"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", protocol["model_repo_revision"])
        or protocol.get("kind") != "as_safety_owner_resolution_development_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_a_only_development_only"
        or protocol.get("case_order") != "RE01-RE06,RE08-RE11,V01-V08,V10,V12,V14,V16"
        or protocol.get("retry_policy") != "no_retry_manual_audit_on_interruption"
        or protocol.get("endpoint") != "http://127.0.0.1:18081/v1/chat/completions"
        or protocol.get("server_image_digest")
        != "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
        or protocol.get("max_tokens") != 320
        or protocol.get("local_runtime")
        != {
            "host_port": 18081,
            "cpu_count": 2,
            "memory_bytes": 4 * 1024**3,
            "context_tokens": 4096,
            "threads": 2,
            "parallel_slots": 1,
        }
        or not isinstance(protocol.get("model_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", protocol["model_sha256"])
    ):
        raise ValueError("symmetric link protocol differs")
    inputs = protocol["input_hashes"]
    manifest = protocol["source_manifest"]
    expected_paths = expected_manifest_paths()
    if (
        not isinstance(inputs, dict)
        or set(inputs) != set(INPUTS)
        or not isinstance(manifest, dict)
        or set(manifest) != expected_paths
    ):
        raise ValueError("symmetric source manifest paths differ")
    for key, path in INPUTS.items():
        if inputs[key] != digest(path):
            raise ValueError(f"frozen input {key} differs")
        _require_committed(path)
    for relative, expected_hash in manifest.items():
        path = ROOT / relative
        if expected_hash != digest(path):
            raise ValueError(f"frozen source {relative} differs")
        _require_committed(path)
    policy = _json(SOURCES["policy_sha256"].read_text(encoding="utf-8"))
    if policy != {
        "kind": "as_safety_grounded_entity_link_request_v1",
        "server_image_digest": protocol["server_image_digest"],
        "max_tokens": 320,
        "temperature": 0,
        "repeat_penalty": 1.05,
        "stop": ["<|eot_id|>"],
        "timeout_seconds": 180,
        "retry_policy": "no_retry_manual_audit_on_interruption",
    } or (
        type(policy["max_tokens"]) is not int
        or type(policy["temperature"]) is not int
        or type(policy["repeat_penalty"]) is not float
        or type(policy["timeout_seconds"]) is not int
    ):
        raise ValueError("grounded request policy differs")
    _require_committed(protocol_path)
    cases = _reviewed_cases()
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 45:
        raise ValueError("journal row count differs")
    rows = [_json(line) for line in lines]
    if rows[0] != {
        "event": "header",
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
    }:
        raise ValueError("journal header differs")
    per_case = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("journal call order differs")
        end = rows[2 + 2 * index]
        _check_end(end, case)
        per_case.append(
            {
                "id": case["id"],
                "gold_relation": case["gold_relation"],
                "gold_route": case["gold_route"],
                "event_status": case["event_status"],
                "predicted_relation": end["source_relation"],
                "predicted_route": end["route"],
                "stage1_status": end["stage1"]["status"],
                "stage2_status": end["stage2"]["status"],
                "stage1_error": end["stage1"]["error"] is not None,
                "stage2_error": end["stage2"]["error"] is not None,
                "stage2_skipped": end["stage2"]["status"] == "skipped",
                "stage2_skip_reason": end["stage2"]["skip_reason"],
                "calls": 1 + int(end["stage2"]["called"]),
                "stage1_event_present": end["stage1"]["spans"] is not None
                and end["stage1"]["spans"]["event_span"] is not None,
                "stage1_subject_present": end["stage1"]["spans"] is not None
                and end["stage1"]["spans"]["subject_span"] is not None,
                "stage1_owner_present": end["stage1"]["spans"] is not None
                and end["stage1"]["spans"]["owner_span"] is not None,
                "total_latency_ms": end["total_latency_ms"],
                "stage1_latency_ms": end["stage1"]["latency_ms"],
                "stage2_latency_ms": end["stage2"]["latency_ms"],
            }
        )
    summary = {
        "all": _aggregate(per_case),
        "stage2_called": _aggregate([row for row in per_case if row["calls"] == 2]),
        "RE": _aggregate([row for row in per_case if row["id"].startswith("RE")]),
        "V": _aggregate([row for row in per_case if row["id"].startswith("V")]),
        "observed": _aggregate([row for row in per_case if row["event_status"] == "observed"]),
        "uncertain": _aggregate([row for row in per_case if row["event_status"] == "uncertain"]),
        "current_observed": _aggregate(
            [
                row
                for row in per_case
                if row["gold_relation"] == "current" and row["event_status"] == "observed"
            ]
        ),
        "sensitivity_excluding_V03_V04": _aggregate(
            [row for row in per_case if row["id"] not in {"V03", "V04"}]
        ),
        "sensitivity_excluding_RE06": _aggregate([row for row in per_case if row["id"] != "RE06"]),
    }
    by_gold_relation = {
        relation: _aggregate([row for row in per_case if row["gold_relation"] == relation])
        for relation in ("current", "other")
    }
    by_id = {row["id"]: row for row in per_case}
    contrast_pairs = []
    for current_id, other_id in (("V01", "V02"), ("V05", "V06"), ("V07", "V08")):
        current, other = by_id[current_id], by_id[other_id]
        if (current["gold_relation"], other["gold_relation"]) != ("current", "other"):
            raise ValueError("contrast gold differs")
        contrast_pairs.append(
            {
                "case_ids": [current_id, other_id],
                "predicted_relations": [current["predicted_relation"], other["predicted_relation"]],
                "prediction_flipped": current["predicted_relation"] is not None
                and other["predicted_relation"] is not None
                and current["predicted_relation"] != other["predicted_relation"],
                "expected_flip_recovered": current["predicted_relation"] == "current"
                and other["predicted_relation"] == "other",
                "errors": sum(
                    row["stage1_error"] or row["stage2_error"] for row in (current, other)
                ),
            }
        )
    thresholds = {
        "current_min_correct": 15,
        "current_observed_min_correct": 13,
        "other_min_correct": 6,
        "max_errors": 0,
        "contrast_min_recovered": 3,
        "met": by_gold_relation["current"]["relation_correct"] >= 15
        and summary["current_observed"]["relation_correct"] == 13
        and by_gold_relation["other"]["relation_correct"] == 6
        and summary["all"]["errors"] == 0
        and sum(pair["expected_flip_recovered"] for pair in contrast_pairs) == 3,
    }
    return {
        "claim_scope": "already_exposed_ai_authored_a_only_development_only",
        "historical_comparison_allowed": False,
        "raw_model_output_independently_reproducible": False,
        "quoted_relationship_semantics_independently_verified": False,
        "stage1_subject_owner_semantic_accuracy_measured": False,
        "latency_nearest_rank_ms": {
            name: {
                "denominator": len(values),
                "p50": sorted(values)[(len(values) - 1) // 2] if values else None,
                "p95": sorted(values)[(95 * len(values) + 99) // 100 - 1] if values else None,
            }
            for name, values in {
                "total": [row["total_latency_ms"] for row in per_case],
                "stage1": [row["stage1_latency_ms"] for row in per_case],
                "stage2_called": [
                    row["stage2_latency_ms"] for row in per_case if row["calls"] == 2
                ],
            }.items()
        },
        "summary": summary,
        "by_gold_relation": by_gold_relation,
        "contrast_pairs": contrast_pairs,
        "development_thresholds": thresholds,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
