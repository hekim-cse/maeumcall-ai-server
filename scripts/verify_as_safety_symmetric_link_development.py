"""Independently verify a frozen symmetric A/S entity-link development run."""

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
    "runner_sha256": ROOT / "scripts/run_as_safety_symmetric_link_development.py",
    "candidate_sha256": ROOT / "scripts/probe_as_safety_symmetric_entity_link_v1.py",
    "result_verifier_sha256": Path(__file__),
    "oracle_runner_sha256": ROOT / "scripts/run_as_safety_oracle_relation_diagnostic.py",
    "owner_loader_sha256": ROOT / "scripts/run_as_safety_owner_evidence_diagnostic.py",
    "oracle_candidate_sha256": ROOT / "scripts/probe_as_safety_oracle_relation.py",
    "completion_sha256": ROOT / "scripts/as_safety_completion_v2.py",
    "policy_loader_sha256": ROOT / "scripts/run_as_safety_symmetric_link_development.py",
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
}
ROOT_MODULES = (SOURCES["runner_sha256"], SOURCES["candidate_sha256"], Path(__file__))
DATA_FILES = (
    SOURCES["re_dataset_sha256"],
    SOURCES["v_dataset_sha256"],
    SOURCES["spans_sha256"],
    SOURCES["owner_labels_sha256"],
    SOURCES["policy_sha256"],
)
LOCAL_PACKAGES = frozenset({"scripts", "services", "evals"})
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
    "entity_link",
    "same_or_part_answer",
    "distinct_item_answer",
    "source_relation",
    "route",
    "error_stage",
    "error_code",
    "http_status",
    "finish_reason",
    "latency_ms",
}
LINK_RELATION = {
    "same_or_part": "current",
    "distinct_item": "other",
    "unresolved": "unknown",
}
ANSWER = frozenset({"yes", "no", "uncertain"})
INPUTS = {
    "re_dataset": SOURCES["re_dataset_sha256"],
    "v_dataset": SOURCES["v_dataset_sha256"],
    "spans": SOURCES["spans_sha256"],
    "owner_labels": SOURCES["owner_labels_sha256"],
    "policy": SOURCES["policy_sha256"],
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


def _check_end(row: dict, case: dict) -> None:
    if (
        not isinstance(row, dict)
        or set(row) != END_FIELDS
        or row["event"] != "end"
        or row["case_id"] != case["id"]
    ):
        raise ValueError("end row shape/order differs")
    latency, status = row["latency_ms"], row["http_status"]
    if type(latency) not in {int, float} or not 0 <= latency < 86_400_000:
        raise ValueError("latency differs")
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError("HTTP status differs")
    if row["finish_reason"] not in {None, "stop", "length"}:
        raise ValueError("finish reason differs")
    if row["error_stage"] is None:
        same, distinct = row["same_or_part_answer"], row["distinct_item_answer"]
        if (
            type(same) is not str
            or same not in ANSWER
            or type(distinct) is not str
            or distinct not in ANSWER
        ):
            raise ValueError("nonfinite symmetric answer")
        expected_link = (
            "same_or_part"
            if (same, distinct) == ("yes", "no")
            else "distinct_item"
            if (same, distinct) == ("no", "yes")
            else "unresolved"
        )
        if (
            row["error_code"] is not None
            or status is not None
            or row["finish_reason"] != "stop"
            or row["entity_link"] != expected_link
            or row["source_relation"] != LINK_RELATION[expected_link]
            or row["route"] != _route(row["source_relation"], case["event_status"])
        ):
            raise ValueError("successful decision differs")
        return
    if (
        row["entity_link"] is not None
        or row["same_or_part_answer"] is not None
        or row["distinct_item_answer"] is not None
        or row["source_relation"] is not None
        or row["route"] is not None
    ):
        raise ValueError("failure has decision")
    allowed = {
        "response": {
            "http_error",
            "transport_error",
            "response_error",
            "finish_length",
            "finish_other",
        },
        "contract": {"invalid_json", "invalid_relation"},
    }
    stage, code = row["error_stage"], row["error_code"]
    if (
        type(stage) is not str
        or type(code) is not str
        or stage not in allowed
        or code not in allowed[stage]
    ):
        raise ValueError("nonfinite failure code")
    if stage == "contract" and (row["finish_reason"] != "stop" or status is not None):
        raise ValueError("contract metadata differs")
    if code == "http_error" and status is None:
        raise ValueError("HTTP error lacks status")
    if code != "http_error" and status is not None:
        raise ValueError("unexpected HTTP status")
    if code == "finish_length" and row["finish_reason"] != "length":
        raise ValueError("length failure differs")
    if code == "finish_other" and row["finish_reason"] is not None:
        raise ValueError("other finish failure differs")
    if (
        code in {"http_error", "transport_error", "response_error"}
        and row["finish_reason"] is not None
    ):
        raise ValueError("response exception has finish reason")


def _aggregate(rows: list[dict]) -> dict:
    return {
        "denominator": len(rows),
        "relation_correct": sum(row["predicted_relation"] == row["gold_relation"] for row in rows),
        "route_correct": sum(row["predicted_route"] == row["gold_route"] for row in rows),
        "errors": sum(row["error_stage"] is not None for row in rows),
        "unknown_outputs": sum(row["predicted_relation"] == "unknown" for row in rows),
        "answer_pair_counts": {
            f"{same}:{distinct}": count
            for (same, distinct), count in Counter(
                (row["same_or_part_answer"], row["distinct_item_answer"]) for row in rows
            ).items()
        },
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
        or protocol.get("kind") != "as_safety_symmetric_link_development_v1"
        or protocol.get("claim_scope") != "already_exposed_ai_authored_oracle_development_only"
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
                "same_or_part_answer": end["same_or_part_answer"],
                "distinct_item_answer": end["distinct_item_answer"],
                "predicted_entity_link": end["entity_link"],
                "predicted_relation": end["source_relation"],
                "predicted_route": end["route"],
                "error_stage": end["error_stage"],
                "error_code": end["error_code"],
                "http_status": end["http_status"],
                "latency_ms": end["latency_ms"],
            }
        )
    summary = {
        "all": _aggregate(per_case),
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
                "errors": sum(row["error_stage"] is not None for row in (current, other)),
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
        "claim_scope": "already_exposed_ai_authored_oracle_development_only",
        "historical_comparison_allowed": False,
        "raw_model_output_independently_reproducible": False,
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
