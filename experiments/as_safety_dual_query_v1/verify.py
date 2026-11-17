"""Independent audit of the ES owner-oracle dual-query experiment.

The model's raw text, rather than runner decisions, is the source of truth.
This module intentionally does not import the runner or its contract parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import statistics
import subprocess
from pathlib import Path

from experiments.as_safety_v4.cases import load_cases

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
DATASET = DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json"
REVIEW = ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md"
FIELD_REVIEW = ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md"
KIND = "as_safety_dual_query_v1_development_v1"
SCOPE = "exposed_ai_authored_owner_oracle_dual_query_development_only"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
REQUEST = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
PROTOCOL_KEYS = {
    "kind",
    "claim_scope",
    "case_order",
    "event_order",
    "arm_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "private_output",
    "route_policy",
}
INPUTS = {
    "dataset": DATASET,
    "review": REVIEW,
    "field_review": FIELD_REVIEW,
    "method": ROOT / "docs/portfolio/nlu_safety_event_source_v4_method.md",
    "dual_query_method": ROOT / "docs/portfolio/nlu_safety_dual_query_v1_method.md",
}
ROUTE_POLICY = {
    "implementation": "experiments.as_safety_v4.contract.route_for_events",
    "observed_current": "safety_action_required",
    "uncertain_current": "confirming_safety_status",
    "observed_other": "collecting_service_request",
    "unknown_or_failed": "confirming_safety_status",
    "priority": [
        "safety_action_required",
        "confirming_safety_status",
        "collecting_service_request",
    ],
    "multi_event_example": "ES06: observed current takes priority over other or failed event",
}
CASE_ORDER = tuple(f"ES{i:02}" for i in range(1, 21))
CONTRAST_PAIRS = (("ES01", "ES09"), ("ES02", "ES11"))
CATEGORIES = ("observed_current", "uncertain_current", "observed_other")
REQUIRED_SOURCES = {
    "experiments/as_safety_v4/__init__.py",
    "experiments/as_safety_v4/cases.py",
    "experiments/as_safety_v4/contract.py",
    "experiments/as_safety_v4/run.py",
    "experiments/as_safety_v4/verify.py",
    "experiments/as_safety_dual_query_v1/__init__.py",
    "experiments/as_safety_dual_query_v1/contract.py",
    "experiments/as_safety_dual_query_v1/run.py",
    "experiments/as_safety_dual_query_v1/verify.py",
}
STAGE_KEYS = {
    "called",
    "status",
    "skip_reason",
    "error_code",
    "error_field",
    "finish_reason",
    "latency_ms",
    "request_latency_ms",
    "raw_sha256",
    "raw_bytes",
    "decision",
}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ERROR_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
RELATIONS = {"current", "other", "unknown"}
DECISIONS = {"yes", "no", "unknown"}
ARMS = ("current", "distinct")
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
TRANSPORT_ERRORS = {
    "redirect",
    "request_too_large",
    "response_too_large",
    "http_status",
    "http_error",
    "network_error",
    "timeout",
    "invalid_response_json",
    "response_fields_invalid",
}


class ContractError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate_key", "$")
        result[key] = value
    return result


def _nonfinite(_value: str) -> None:
    raise ContractError("nonfinite_number", "$")


def _json(raw: str) -> object:
    if type(raw) is not str:
        raise ContractError("response_type_invalid", "$")
    try:
        return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    except json.JSONDecodeError as error:
        raise ContractError("invalid_json", "$") from error


def replay_decision(raw: str) -> str:
    """Parse the public one-field contract independently of run.py."""
    value = _json(raw)
    if type(value) is not dict or set(value) != {"decision"}:
        raise ContractError("decision_fields_invalid", "decision")
    decision = value["decision"]
    if type(decision) is not str or decision not in DECISIONS:
        raise ContractError("decision_enum_invalid", "decision")
    return decision


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or not relative or relative.startswith("/"):
        raise ValueError("frozen source reference invalid")
    if ".." in Path(relative).parts:
        raise ValueError("frozen source reference invalid")
    return _git("show", f"{commit}:{relative}")


def _duration(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value < 86_400_000


def _private_dir(path: Path) -> None:
    if (
        path.resolve().is_relative_to(ROOT)
        or path.is_symlink()
        or not path.is_dir()
        or stat.S_IMODE(path.stat().st_mode) != 0o700
    ):
        raise ValueError("private raw directory boundary differs")


def _read_raw(stage: dict, path: Path) -> str | None:
    sha, size = stage["raw_sha256"], stage["raw_bytes"]
    if sha is None:
        if size is not None or path.exists():
            raise ValueError("unexpected private raw response")
        return None
    if (
        type(sha) is not str
        or not SHA_RE.fullmatch(sha)
        or type(size) is not int
        or not 0 < size <= 1_000_000
        or path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != 0o600
    ):
        raise ValueError("private raw metadata differs")
    raw = path.read_bytes()
    if len(raw) != size or _sha(raw) != sha:
        raise ValueError("private raw response differs")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("private raw encoding differs") from error
    if not decoded.strip():
        raise ValueError("private raw content blank")
    return decoded


def _route(events: list[dict], relations: list[str | None], *, overflow: bool, failed: bool) -> str:
    if type(overflow) is not bool or type(failed) is not bool:
        raise ValueError("route flags invalid")
    if any(
        event["occurrence"] == "observed" and relation == "current"
        for event, relation in zip(events, relations, strict=True)
    ):
        return "safety_action_required"
    if (
        overflow
        or failed
        or any(
            event["occurrence"] != "nonoccurring"
            and (
                relation in (None, "unknown")
                or (event["occurrence"] == "uncertain" and relation == "current")
            )
            for event, relation in zip(events, relations, strict=True)
        )
    ):
        return "confirming_safety_status"
    return "collecting_service_request"


def _eligible_events(cases: list[dict]) -> list[tuple[str, str, dict, dict]]:
    if tuple(case["id"] for case in cases) != CASE_ORDER:
        raise ValueError("case order differs")
    result = []
    for case in cases:
        for number, event in enumerate(case["events"], 1):
            if event["occurrence"] == "nonoccurring" or event["hazard_owner_span"] is None:
                continue
            result.append((f"{case['id']}-{number}", case["id"], case, event))
    if len(result) != 18 or len({case_id for _, case_id, _, _ in result}) != 17:
        raise ValueError("eligible event coverage differs")
    counts = {}
    for _, _, _, event in result:
        category = f"{event['occurrence']}_{event['owner_to_target']}"
        counts[category] = counts.get(category, 0) + 1
    if counts != {"observed_current": 8, "uncertain_current": 1, "observed_other": 9}:
        raise ValueError("eligible event categories differ")
    return result


def _source_paths(commit: str) -> set[str]:
    paths = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_dual_query_v1",
    ):
        names = _git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(name for name in names.decode().splitlines() if name.endswith(".py"))
    if not REQUIRED_SOURCES <= paths:
        raise ValueError("frozen source package incomplete")
    return paths


def check_protocol(path: Path, model_path: Path, cases: list[dict]) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = _json(raw.decode("utf-8"))
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    selected = _eligible_events(cases)
    event_order = [key for key, _, _, _ in selected]
    arm_order = [
        {"event_id": key, "arms": list(ARMS if index % 2 == 0 else reversed(ARMS))}
        for index, (key, _, _, _) in enumerate(selected)
    ]
    if (
        type(commit) is not str
        or not COMMIT_RE.fullmatch(commit)
        or protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(dict.fromkeys(case_id for _, case_id, _, _ in selected))
        or protocol["event_order"] != event_order
        or protocol["arm_order"] != arm_order
        or protocol["model_sha256"] != MODEL_SHA
        or protocol["server_image_digest"] != IMAGE
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
        or protocol["route_policy"] != ROUTE_POLICY
    ):
        raise ValueError("protocol identity differs")
    if _file_sha(model_path) != MODEL_SHA:
        raise ValueError("model digest differs")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _source_paths(commit):
        raise ValueError("source manifest paths differ")
    for relative, expected in manifest.items():
        frozen = _frozen(commit, relative)
        if (
            type(expected) is not str
            or not SHA_RE.fullmatch(expected)
            or _sha(frozen) != expected
            or (ROOT / relative).read_bytes() != frozen
        ):
            raise ValueError(f"source manifest differs: {relative}")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest paths differ")
    for key, source in INPUTS.items():
        frozen = _frozen(commit, source.relative_to(ROOT).as_posix())
        expected = hashes[key]
        if (
            type(expected) is not str
            or not SHA_RE.fullmatch(expected)
            or _sha(frozen) != expected
            or source.read_bytes() != frozen
        ):
            raise ValueError(f"input manifest differs: {key}")
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be in repository") from error
    if _git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed")
    return protocol, _sha(raw)


def audit_stage(stage: dict, path: Path) -> dict:
    """Reconstruct the stage decision from private bytes and public metadata."""
    if type(stage) is not dict or set(stage) != STAGE_KEYS:
        raise ValueError("stage fields differ")
    if (
        stage["called"] is not True
        or stage["skip_reason"] is not None
        or stage["status"] not in {"validated", "contract_error", "response_error"}
        or not _duration(stage["latency_ms"])
        or not _duration(stage["request_latency_ms"])
        or stage["request_latency_ms"] > stage["latency_ms"] + 0.01
    ):
        raise ValueError("stage call metadata differs")
    code, field = stage["error_code"], stage["error_field"]
    if code is not None and (type(code) is not str or not ERROR_RE.fullmatch(code)):
        raise ValueError("stage error code differs")
    if field is not None and (type(field) is not str or len(field) > 96):
        raise ValueError("stage error field differs")
    raw = _read_raw(stage, path)
    finish = stage["finish_reason"]
    if finish is None:
        if (
            raw is not None
            or stage["status"] != "response_error"
            or code not in TRANSPORT_ERRORS
            or field is not None
            or stage["decision"] is not None
        ):
            raise ValueError("transport result differs")
        return {
            "status": "response_error",
            "decision": None,
            "request_latency_ms": stage["request_latency_ms"],
        }
    if finish == "length":
        if (
            raw is None
            or stage["status"] != "response_error"
            or code != "finish_length"
            or field is not None
            or stage["decision"] is not None
        ):
            raise ValueError("truncated response result differs")
        return {
            "status": "response_error",
            "decision": None,
            "request_latency_ms": stage["request_latency_ms"],
        }
    if finish != "stop" or raw is None:
        raise ValueError("response finish differs")
    try:
        decision = replay_decision(raw)
    except ContractError as error:
        if (
            stage["status"] != "contract_error"
            or (code, field) != (error.code, error.field)
            or stage["decision"] is not None
        ):
            raise ValueError("contract result differs") from None
        return {
            "status": "contract_error",
            "decision": None,
            "request_latency_ms": stage["request_latency_ms"],
        }
    if (
        stage["status"] != "validated"
        or code is not None
        or field is not None
        or stage["decision"] != decision
    ):
        raise ValueError("validated decision differs")
    return {
        "status": "validated",
        "decision": decision,
        "request_latency_ms": stage["request_latency_ms"],
    }


def _relations(
    audited: dict[tuple[str, str], dict], cases: list[dict]
) -> tuple[dict[str, str], dict[str, bool]]:
    relations = {}
    failed = {}
    for key, _, _, _ in _eligible_events(cases):
        current = audited[(key, "current")]
        distinct = audited[(key, "distinct")]
        has_error = current["status"] != "validated" or distinct["status"] != "validated"
        failed[key] = has_error
        if has_error:
            relations[key] = "unknown"
        elif current["decision"] == "yes" and distinct["decision"] == "no":
            relations[key] = "current"
        elif current["decision"] == "no" and distinct["decision"] == "yes":
            relations[key] = "other"
        else:
            relations[key] = "unknown"
    return relations, failed


def _routes(
    relations: dict[str, str], failed: dict[str, bool], cases: list[dict]
) -> dict[str, str]:
    routes = {}
    for case in cases:
        values = []
        case_failed = False
        present = False
        for index, event in enumerate(case["events"], 1):
            key = f"{case['id']}-{index}"
            if key in relations:
                present = True
                values.append(relations[key])
                case_failed |= failed[key]
            elif event["occurrence"] == "nonoccurring":
                values.append(None)
            elif event["hazard_owner_span"] is None and event["owner_to_target"] == "unknown":
                break  # ES17 is outside this owner-oracle diagnostic.
            else:
                raise ValueError("excluded actionable event in route")
        if present:
            routes[case["id"]] = _route(
                case["events"], values, overflow=case["overflow"], failed=case_failed
            )
    if len(routes) != 17:
        raise ValueError("route denominator differs")
    return routes


def summarize(audited: dict[tuple[str, str], dict], cases: list[dict]) -> dict:
    """Recompute both raw decisions, relation, route and counts without runner code."""
    selected = _eligible_events(cases)
    expected = {(key, arm) for key, _, _, _ in selected for arm in ARMS}
    if set(audited) != expected:
        raise ValueError("event/arm denominator differs")
    relations, failed = _relations(audited, cases)
    routes = _routes(relations, failed, cases)
    category_correct = dict.fromkeys(CATEGORIES, 0)
    output_distribution = {"current": 0, "other": 0, "unknown": 0}
    status_counts = {}
    decisions = {arm: {"yes": 0, "no": 0, "unknown": 0} for arm in ARMS}
    abstention = {"error_pair": 0, "any_unknown": 0, "contradiction": 0, "both_no": 0}
    directional = {
        "observed_current_to_other": 0,
        "observed_current_to_unknown": 0,
        "uncertain_current_to_other": 0,
        "uncertain_current_to_unknown": 0,
        "observed_other_to_current": 0,
        "observed_other_to_unknown": 0,
    }
    correct = {}
    for key, _, _, gold in selected:
        category = f"{gold['occurrence']}_{gold['owner_to_target']}"
        good = not failed[key] and relations[key] == gold["owner_to_target"]
        correct[key] = good
        category_correct[category] += int(good)
        output_distribution[relations[key]] += 1
        if relations[key] != gold["owner_to_target"]:
            directional[f"{category}_to_{relations[key]}"] += 1
        current = audited[(key, "current")]
        distinct = audited[(key, "distinct")]
        if failed[key]:
            abstention["error_pair"] += 1
        elif "unknown" in (current["decision"], distinct["decision"]):
            abstention["any_unknown"] += 1
        elif current["decision"] == distinct["decision"] == "yes":
            abstention["contradiction"] += 1
        elif current["decision"] == distinct["decision"] == "no":
            abstention["both_no"] += 1
        for arm in ARMS:
            stage = audited[(key, arm)]
            status = stage["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "validated":
                decisions[arm][stage["decision"]] += 1
    case_map = {case["id"]: case for case in cases}
    pair_detail = {
        f"{first}/{second}": all(
            routes[case_id] == case_map[case_id]["expected_route"]
            and all(correct[key] for key, _, case, _ in selected if case["id"] == case_id)
            for case_id in (first, second)
        )
        for first, second in CONTRAST_PAIRS
    }
    latencies = sorted(
        sum(audited[(key, arm)]["request_latency_ms"] for arm in ARMS) for key, _, _, _ in selected
    )
    question_latencies = {
        arm: sorted(audited[(key, arm)]["request_latency_ms"] for key, _, _, _ in selected)
        for arm in ARMS
    }
    case_latencies = sorted(
        sum(
            audited[(key, arm)]["request_latency_ms"]
            for key, _, item, _ in selected
            if item["id"] == case_id
            for arm in ARMS
        )
        for case_id in routes
    )
    decided = output_distribution["current"] + output_distribution["other"]
    decided_correct = sum(correct[key] and relations[key] != "unknown" for key in correct)
    route_correct = sum(
        routes[case_id] == case_map[case_id]["expected_route"] for case_id in routes
    )
    return {
        "event": "summary",
        "cases": 17,
        "events": 18,
        "requests": 36,
        "claim_scope": SCOPE,
        "relation_correct": sum(correct.values()),
        "category_denominators": {
            "observed_current": 8,
            "uncertain_current": 1,
            "observed_other": 9,
        },
        "category_correct": category_correct,
        "status_counts": dict(sorted(status_counts.items())),
        "decision_distribution": decisions,
        "output_distribution": output_distribution,
        "abstention_reasons": abstention,
        "directional_relation_errors": directional,
        "contract_errors": status_counts.get("contract_error", 0),
        "response_errors": status_counts.get("response_error", 0),
        "unresolved_pairs": output_distribution["unknown"],
        "decided_relation_count": decided,
        "decided_relation_correct": decided_correct,
        "relation_decision_denominator": 18,
        "relation_decision_rate": round(decided / 18, 6),
        "decided_relation_accuracy_denominator": decided,
        "decided_relation_accuracy": round(decided_correct / decided, 6) if decided else None,
        "route_correct": route_correct,
        "route_predictions": routes,
        "es06_route": routes["ES06"],
        "contrast_pairs_correct": sum(pair_detail.values()),
        "contrast_pairs": pair_detail,
        "missed_direct_current": sum(
            case_map[key]["expected_route"] == "safety_action_required"
            and value != "safety_action_required"
            for key, value in routes.items()
        ),
        "false_direct_other": sum(
            case_map[key]["expected_route"] == "collecting_service_request"
            and value == "safety_action_required"
            for key, value in routes.items()
        ),
        "event_request_latency_count": 18,
        "event_request_latency_p50_ms": round(statistics.median(latencies), 3),
        "event_request_latency_p95_ms": round(latencies[math.ceil(len(latencies) * 0.95) - 1], 3),
        "question_request_latency_ms": {
            arm: {
                "count": 18,
                "p50": round(statistics.median(values), 3),
                "p95": round(values[math.ceil(len(values) * 0.95) - 1], 3),
            }
            for arm, values in question_latencies.items()
        },
        "case_request_latency_count": 17,
        "case_request_latency_p50_ms": round(statistics.median(case_latencies), 3),
        "case_request_latency_p95_ms": round(
            case_latencies[math.ceil(len(case_latencies) * 0.95) - 1], 3
        ),
        "gate_met": (
            category_correct == {"observed_current": 8, "uncertain_current": 1, "observed_other": 9}
            and route_correct == 17
            and sum(pair_detail.values()) == 2
            and status_counts.get("contract_error", 0) == 0
            and status_counts.get("response_error", 0) == 0
        ),
    }


def verify(protocol_path: Path, journal_path: Path, private_dir: Path, *, model_path: Path) -> dict:
    cases = load_cases(DATASET)
    protocol, protocol_sha = check_protocol(protocol_path, model_path, cases)
    _private_dir(private_dir)
    journal_bytes = journal_path.read_bytes()
    rows = [_json(line) for line in journal_bytes.decode("utf-8").splitlines()]
    if len(rows) != 2 + 4 * len(protocol["event_order"]):
        raise ValueError("journal row count differs; interrupted or retried")
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise ValueError("journal header differs")
    audited = {}
    raw_names = set()
    offset = 1
    for assignment in protocol["arm_order"]:
        event_id = assignment["event_id"]
        for arm in assignment["arms"]:
            if rows[offset] != {"event": "begin", "event_id": event_id, "arm": arm}:
                raise ValueError("journal begin order differs")
            end = rows[offset + 1]
            if type(end) is not dict or set(end) != {"event", "event_id", "arm", "stage"}:
                raise ValueError("journal end fields differ")
            if (end["event"], end["event_id"], end["arm"]) != ("end", event_id, arm):
                raise ValueError("journal end order differs")
            name = f"{event_id}-{arm}.json.txt"
            stage = end["stage"]
            audited[(event_id, arm)] = audit_stage(stage, private_dir / name)
            if stage["raw_sha256"] is not None:
                raw_names.add(name)
            offset += 2
    expected_summary = summarize(audited, cases)
    if rows[-1] != expected_summary:
        raise ValueError("journal summary differs")
    if {path.name for path in private_dir.iterdir()} != raw_names:
        raise ValueError("private raw file inventory differs")
    return {
        "kind": KIND,
        "protocol_sha256": protocol_sha,
        "journal_sha256": _sha(journal_bytes),
        "private_raw_count": len(raw_names),
        "summary": {key: value for key, value in expected_summary.items() if key != "event"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.protocol, args.journal, args.private_dir, model_path=args.model_path),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
