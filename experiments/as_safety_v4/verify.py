"""Independent replay of the frozen ES event-source exploratory journal.

This verifier does not import the v4 runner, prompt, validator, or route
aggregator. Source quotes are independently anchored against the utterance.
Those anchors establish provenance, not semantic correctness.
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

from experiments.as_safety_v2.json_contract import ValidationError, parse_model_json
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v4.cases import load_cases

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
DATASET = DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json"
INPUTS = {
    "dataset": DATASET,
    "review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "method": ROOT / "docs/portfolio/nlu_safety_event_source_v4_method.md",
}
KIND = "as_safety_event_source_v4_exploration_v1"
SCOPE = "ai_authored_user_reviewed_exploratory_not_official_accuracy"
CASE_ORDER = tuple(f"ES{i:02}" for i in range(1, 21))
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
POLICY = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
PROTOCOL_KEYS = {
    "kind", "claim_scope", "case_order", "frozen_code_commit", "input_hashes",
    "source_manifest", "model_sha256", "server_image_digest", "request_policy",
    "local_runtime", "retry_policy", "private_output",
}
BASE_KEYS = {
    "called", "status", "skip_reason", "error_code", "error_field",
    "finish_reason", "latency_ms", "request_latency_ms", "raw_sha256", "raw_bytes",
}
STAGE1_KEYS = BASE_KEYS | {"events", "overflow"}
STAGE2_KEYS = BASE_KEYS | {"event_index", "owner_to_target", "hazard_owner_span"}
END_KEYS = {
    "event", "case_id", "stage1", "stage2", "route", "request_count",
    "model_call_latency_sum_ms", "elapsed_ms",
}
SPAN_KEYS = {"clause_index", "start", "end", "quote_sha256"}
OCCURRENCES = {"observed", "uncertain", "nonoccurring"}
RELATIONS = {"current", "other", "unknown"}
ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
TRANSPORT_ERRORS = {
    "redirect", "request_too_large", "response_too_large", "http_status", "http_error",
    "network_error", "timeout", "invalid_response_json", "response_fields_invalid",
}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ERROR_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, path: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or path.startswith("/") or ".." in Path(path).parts:
        raise ValueError("frozen source reference invalid")
    return _git("show", f"{commit}:{path}")


def _sources(commit: str) -> set[str]:
    result = set()
    for prefix in ("experiments/as_safety_v2", "experiments/as_safety_v4"):
        names = _git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        result.update(name for name in names.decode().splitlines() if name.endswith(".py"))
    required = {
        "experiments/as_safety_v4/__init__.py", "experiments/as_safety_v4/cases.py",
        "experiments/as_safety_v4/contract.py", "experiments/as_safety_v4/run.py",
        "experiments/as_safety_v4/verify.py",
    }
    if not required <= result:
        raise ValueError("frozen v4 source package incomplete")
    return result


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    protocol = parse_model_json(raw.decode("utf-8"))
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str or not COMMIT_RE.fullmatch(commit)
        or protocol["kind"] != KIND or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["server_image_digest"] != IMAGE or protocol["model_sha256"] != MODEL_SHA
        or protocol["request_policy"] != POLICY or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    if _digest_file(model_path) != MODEL_SHA:
        raise ValueError("model digest differs")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _sources(commit):
        raise ValueError("source manifest paths differ")
    for relative, expected in manifest.items():
        frozen = _frozen(commit, relative)
        if (
            type(expected) is not str or not SHA_RE.fullmatch(expected)
            or _digest(frozen) != expected or (ROOT / relative).read_bytes() != frozen
        ):
            raise ValueError(f"source manifest differs: {relative}")
    hashes = protocol["input_hashes"]
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise ValueError("input manifest paths differ")
    for key, source in INPUTS.items():
        frozen = _frozen(commit, source.relative_to(ROOT).as_posix())
        expected = hashes[key]
        if (
            type(expected) is not str or not SHA_RE.fullmatch(expected)
            or _digest(frozen) != expected or source.read_bytes() != frozen
        ):
            raise ValueError(f"input manifest differs: {key}")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed")
    return protocol, _digest(raw)


def _public_span(span: dict | None) -> dict | None:
    if span is None:
        return None
    return {key: span[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _raw_stage1(raw: str, message: str) -> dict:
    """Recompute the event list without using the candidate validator."""
    clauses = split_clauses(message)
    data = parse_model_json(raw)
    if type(data) is not dict or set(data) != {"events", "overflow"}:
        raise ValidationError("fields_invalid", "stage1")
    events, overflow = data["events"], data["overflow"]
    if type(events) is not list or len(events) > 3:
        raise ValidationError("events_invalid", "events")
    if type(overflow) is not bool or (overflow and len(events) != 3):
        raise ValidationError("overflow_invalid", "overflow")
    checked = []
    previous_end: tuple[int, int] | None = None
    for index, item in enumerate(events):
        field = f"events[{index}]"
        if type(item) is not dict or set(item) != {"event_span", "occurrence"}:
            raise ValidationError("event_fields_invalid", field)
        occurrence = item["occurrence"]
        if type(occurrence) is not str or occurrence not in OCCURRENCES:
            raise ValidationError("occurrence_invalid", field)
        span = anchor_span(item["event_span"], clauses, field=f"{field}.event_span")
        if span is None:
            raise ValidationError("event_required", field)
        position = span["clause_index"], span["start"]
        if previous_end is not None and position < previous_end:
            raise ValidationError("event_order_invalid", field)
        previous_end = span["clause_index"], span["end"]
        checked.append({"event_span": span, "occurrence": occurrence})
    return {"events": checked, "overflow": overflow}


def _raw_stage2(raw: str, message: str) -> dict:
    data = parse_model_json(raw)
    if type(data) is not dict or set(data) != {"hazard_owner_span", "owner_to_target"}:
        raise ValidationError("fields_invalid", "stage2")
    relation = data["owner_to_target"]
    if type(relation) is not str or relation not in RELATIONS:
        raise ValidationError("relation_invalid", "owner_to_target")
    owner = anchor_span(data["hazard_owner_span"], split_clauses(message), field="hazard_owner_span")
    if relation != "unknown" and owner is None:
        raise ValidationError("owner_required", "hazard_owner_span")
    return {"owner_to_target": relation, "hazard_owner_span": owner}


def _duration(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and 0 <= value < 86_400_000


def _read_raw(stage: dict, path: Path) -> str | None:
    sha, size = stage["raw_sha256"], stage["raw_bytes"]
    if sha is None:
        if size is not None or path.exists():
            raise ValueError("unexpected private raw response")
        return None
    if (
        type(sha) is not str or not SHA_RE.fullmatch(sha)
        or type(size) is not int or not 0 < size <= 1_000_000
        or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600
    ):
        raise ValueError("private raw metadata differs")
    raw = path.read_bytes()
    if len(raw) != size or _digest(raw) != sha:
        raise ValueError("private raw response differs")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("private raw encoding differs") from error
    if not decoded.strip():
        raise ValueError("private raw content blank")
    return decoded


def _check_common(stage: dict, *, called: bool, skip_reason: str | None) -> None:
    if stage["called"] is not called or stage["skip_reason"] != skip_reason:
        raise ValueError("stage call transition differs")
    if not called:
        if any(stage[key] is not None for key in (
            "error_code", "error_field", "finish_reason", "latency_ms",
            "request_latency_ms", "raw_sha256", "raw_bytes"
        )) or stage["status"] != "skipped":
            raise ValueError("skipped stage metadata differs")
        return
    if (
        not _duration(stage["latency_ms"])
        or not _duration(stage["request_latency_ms"])
        or stage["request_latency_ms"] > stage["latency_ms"] + 0.01
    ):
        raise ValueError("stage latency differs")
    if stage["status"] not in {"validated", "contract_error", "response_error"}:
        raise ValueError("stage status differs")
    code, field = stage["error_code"], stage["error_field"]
    if code is not None and (type(code) is not str or not ERROR_RE.fullmatch(code)):
        raise ValueError("stage error code differs")
    if field is not None and (type(field) is not str or len(field) > 96):
        raise ValueError("stage error field differs")


def _replay_stage(stage: dict, raw: str | None, *, message: str, first: bool) -> dict | None:
    if stage["finish_reason"] is None:
        if (
            raw is not None or stage["status"] != "response_error"
            or stage["error_code"] not in TRANSPORT_ERRORS or stage["error_field"] is not None
        ):
            raise ValueError("transport result differs")
        return None
    if stage["finish_reason"] == "length":
        if (
            raw is None or stage["status"] != "response_error"
            or stage["error_code"] != "finish_length" or stage["error_field"] is not None
        ):
            raise ValueError("truncated response result differs")
        return None
    if stage["finish_reason"] != "stop" or raw is None:
        raise ValueError("response finish differs")
    try:
        result = _raw_stage1(raw, message) if first else _raw_stage2(raw, message)
    except ValidationError as error:
        if (
            stage["status"] != "contract_error"
            or stage["error_code"] != error.code or stage["error_field"] != error.field
        ):
            raise ValueError("contract error differs") from None
        return None
    if (
        stage["status"] != "validated" or stage["error_code"] is not None
        or stage["error_field"] is not None
    ):
        raise ValueError("validated response metadata differs")
    return result


def _route(events: list[dict], relations: list[str | None], *, overflow: bool, failed: bool) -> str:
    if any(
        event["occurrence"] == "observed" and relation == "current"
        for event, relation in zip(events, relations, strict=True)
    ):
        return "safety_action_required"
    if failed or overflow or any(
        (event["occurrence"] != "nonoccurring")
        and (relation == "unknown" or relation is None or (
            event["occurrence"] == "uncertain" and relation == "current"
        ))
        for event, relation in zip(events, relations, strict=True)
    ):
        return "confirming_safety_status"
    return "collecting_service_request"


def audit_end(row: dict, case: dict, private_dir: Path) -> dict:
    """Replay one case from raw files and independently recalculate its route."""
    if type(row) is not dict or set(row) != END_KEYS or row["event"] != "end":
        raise ValueError("journal end fields differ")
    if row["case_id"] != case["id"] or type(row["stage1"]) is not dict:
        raise ValueError("journal case identity differs")
    first = row["stage1"]
    if set(first) != STAGE1_KEYS:
        raise ValueError("Stage1 fields differ")
    _check_common(first, called=True, skip_reason=None)
    first_raw = _read_raw(first, private_dir / f"{case['id']}-stage1.json.txt")
    parsed_first = _replay_stage(first, first_raw, message=case["user_message"], first=True)
    if parsed_first is None:
        if first["events"] is not None or first["overflow"] is not None:
            raise ValueError("invalid Stage1 public events differ")
        events, overflow = [], False
    else:
        expected = [
            {"event_span": _public_span(item["event_span"]), "occurrence": item["occurrence"]}
            for item in parsed_first["events"]
        ]
        if first["events"] != expected or first["overflow"] is not parsed_first["overflow"]:
            raise ValueError("Stage1 public events differ")
        events, overflow = parsed_first["events"], parsed_first["overflow"]
    stages = row["stage2"]
    if type(stages) is not list or len(stages) != len(events):
        raise ValueError("Stage2 event alignment differs")
    failed = parsed_first is None
    relations: list[str | None] = []
    for index, (event, stage) in enumerate(zip(events, stages, strict=True), 1):
        if type(stage) is not dict or set(stage) != STAGE2_KEYS or stage["event_index"] != index:
            raise ValueError("Stage2 fields or event index differ")
        called = event["occurrence"] != "nonoccurring"
        _check_common(stage, called=called, skip_reason=None if called else "nonoccurring")
        raw_path = private_dir / f"{case['id']}-stage2-{index}.json.txt"
        raw = _read_raw(stage, raw_path)
        if not called:
            if stage["owner_to_target"] is not None or stage["hazard_owner_span"] is not None:
                raise ValueError("skipped Stage2 decision differs")
            relations.append(None)
            continue
        result = _replay_stage(stage, raw, message=case["user_message"], first=False)
        if result is None:
            if stage["owner_to_target"] is not None or stage["hazard_owner_span"] is not None:
                raise ValueError("invalid Stage2 decision differs")
            failed = True
            relations.append(None)
        else:
            if (
                stage["owner_to_target"] != result["owner_to_target"]
                or stage["hazard_owner_span"] != _public_span(result["hazard_owner_span"])
            ):
                raise ValueError("Stage2 public decision differs")
            relations.append(result["owner_to_target"])
    route = _route(events, relations, overflow=overflow, failed=failed) if parsed_first else "confirming_safety_status"
    calls = 1 + sum(stage["called"] for stage in stages)
    call_sum = round(first["request_latency_ms"] + sum(
        stage["request_latency_ms"] or 0 for stage in stages
    ), 3)
    total_stage_ms = round(first["latency_ms"] + sum(stage["latency_ms"] or 0 for stage in stages), 3)
    if (
        row["route"] != route or type(row["request_count"]) is not int
        or row["request_count"] != calls or not _duration(row["elapsed_ms"])
        or row["model_call_latency_sum_ms"] != call_sum
        or row["elapsed_ms"] + 0.01 < total_stage_ms
    ):
        raise ValueError("journal route or call metrics differ")
    return {
        "case_id": case["id"], "route": route, "stage1_valid": parsed_first is not None,
        "stage2_valid": sum(stage["status"] == "validated" for stage in stages),
        "request_count": calls, "events": events, "relations": relations,
        "stage1_status": first["status"], "stage1_overflow": overflow,
        "stage2_statuses": [stage["status"] for stage in stages],
        "stage2_called": [stage["called"] for stage in stages],
        "elapsed_ms": row["elapsed_ms"],
    }


def _private_dir(path: Path) -> None:
    if (
        path.resolve().is_relative_to(ROOT) or not path.is_dir()
        or stat.S_IMODE(path.stat().st_mode) != 0o700
    ):
        raise ValueError("private raw directory boundary differs")


def summarize(audited: list[dict], cases: list[dict]) -> dict:
    """Recalculate all published metrics from independently replayed decisions."""
    if len(audited) != len(cases):
        raise ValueError("summary case count differs")
    gold_events = predicted_events = exact_cases = occurrence_correct = 0
    actionable_gold = actionable_on_exact = relation_correct = 0
    other_observed = false_direct_other = missed_direct = unnecessary_confirm = 0
    for result, case in zip(audited, cases, strict=True):
        if result["case_id"] != case["id"]:
            raise ValueError("summary case order differs")
        gold = case["events"]
        gold_events += len(gold)
        actionable_gold += sum(event["occurrence"] != "nonoccurring" for event in gold)
        predicted = [
            {"event_span": _public_span(item["event_span"]), "occurrence": item["occurrence"]}
            for item in result["events"]
        ]
        predicted_events += len(predicted)
        clauses = split_clauses(case["user_message"])
        references = [
            {"event_span": _public_span(anchor_span(item["event_span"], clauses, field="event_span")),
             "occurrence": item["occurrence"]}
            for item in gold
        ]
        occurrence_correct += sum(item in references for item in predicted)
        if result["stage1_valid"] and predicted == references:
            exact_cases += 1
            actionable_on_exact += sum(event["occurrence"] != "nonoccurring" for event in gold)
            relation_correct += sum(
                result["stage2_statuses"][index] == "validated"
                and result["relations"][index] == event["owner_to_target"]
                for index, event in enumerate(gold)
                if event["occurrence"] != "nonoccurring"
            )
        expected = case["expected_route"]
        if expected == "safety_action_required" and result["route"] != expected:
            missed_direct += 1
        if expected == "collecting_service_request" and result["route"] == "confirming_safety_status":
            unnecessary_confirm += 1
        if expected == "collecting_service_request" and any(
            event["occurrence"] == "observed" and event["owner_to_target"] == "other"
            for event in gold
        ):
            other_observed += 1
            false_direct_other += result["route"] == "safety_action_required"
    elapsed = sorted(item["elapsed_ms"] for item in audited)
    return {
        "event": "summary",
        "cases": len(audited),
        "gold_event_count": gold_events,
        "predicted_event_count": predicted_events,
        "stage1_exact_event_cases": exact_cases,
        "occurrence_correct_event_count": occurrence_correct,
        "actionable_gold_event_count": actionable_gold,
        "actionable_gold_on_exact_event_cases": actionable_on_exact,
        "relation_correct_on_exact_event_cases": relation_correct,
        "route_correct": sum(
            item["route"] == case["expected_route"]
            for item, case in zip(audited, cases, strict=True)
        ),
        "other_observed_cases": other_observed,
        "false_direct_other": false_direct_other,
        "missed_direct_current": missed_direct,
        "unnecessary_confirm": unnecessary_confirm,
        "overflow_cases": sum(item["stage1_overflow"] for item in audited),
        "stage1_errors": sum(item["stage1_status"] != "validated" for item in audited),
        "stage2_errors": sum(
            called and status != "validated"
            for item in audited
            for called, status in zip(item["stage2_called"], item["stage2_statuses"], strict=True)
        ),
        "request_count": sum(item["request_count"] for item in audited),
        "stage1_valid": sum(item["stage1_valid"] for item in audited),
        "stage2_valid": sum(item["stage2_valid"] for item in audited),
        "case_elapsed_p50_ms": round(statistics.median(elapsed), 3) if elapsed else None,
        "case_elapsed_p95_ms": round(elapsed[math.ceil(len(elapsed) * 0.95) - 1], 3)
        if elapsed else None,
    }


def verify(protocol_path: Path, journal_path: Path, private_dir: Path, *, model_path: Path) -> dict:
    protocol, protocol_sha = check_protocol(protocol_path, model_path)
    _private_dir(private_dir)
    cases = load_cases(DATASET)
    rows = [parse_model_json(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 2 + 2 * len(cases):
        raise ValueError("journal row count differs")
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise ValueError("journal header differs")
    audited = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("journal case order differs")
        audited.append(audit_end(rows[2 + 2 * index], case, private_dir))
    expected_files = {
        f"{case['id']}-stage1.json.txt"
        for case, row in zip(cases, (rows[2 + 2 * i] for i in range(len(cases))), strict=True)
        if row["stage1"]["raw_sha256"] is not None
    }
    expected_files.update(
        f"{case['id']}-stage2-{stage['event_index']}.json.txt"
        for case, row in zip(cases, (rows[2 + 2 * i] for i in range(len(cases))), strict=True)
        for stage in row["stage2"]
        if stage["raw_sha256"] is not None
    )
    if {item.name for item in private_dir.iterdir()} != expected_files:
        raise ValueError("private raw file inventory differs")
    computed = summarize(audited, cases)
    if rows[-1] != computed:
        raise ValueError("journal summary differs")
    return {
        "kind": KIND, "claim_scope": SCOPE, "protocol_sha256": protocol_sha,
        "journal_sha256": _digest(journal_path.read_bytes()),
        **{key: value for key, value in computed.items() if key != "event"},
        "model_sha256": protocol["model_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.journal, args.private_dir, model_path=args.model_path), sort_keys=True))


if __name__ == "__main__":
    main()
