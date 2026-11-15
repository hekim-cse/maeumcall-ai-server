"""Independent replay of the ES event-oracle graph development journal.

This module deliberately does not import the graph runner or its validator.
Quoted spans prove source provenance and locality, never semantic correctness.
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
LABELS = DATA / "as-safety-evidence-graph-v1-development-reviewed.v1.json"
INPUTS = {
    "dataset": DATASET,
    "review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "graph_method": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_method.md",
    "graph_field_review": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_field_review.md",
    "graph_labels": LABELS,
}
KIND = "as_safety_evidence_graph_v1_development_v1"
SCOPE = "already_exposed_ai_authored_event_oracle_graph_development_only"
CASE_ORDER = tuple(f"ES{i:02}" for i in range(1, 21))
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
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "retry_policy",
    "private_output",
}
GRAPH_FIELDS = {
    "subject_span",
    "event_subject_kind",
    "event_subject_evidence_span",
    "target_edge_kind",
    "target_edge_evidence_span",
}
PUBLIC_SPAN_KEYS = {"clause_index", "start", "end", "quote_sha256"}
STAGE_FIELDS = {
    "event_index",
    "event_span",
    "occurrence",
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
    "subject_span",
    "event_subject_kind",
    "event_subject_evidence_span",
    "target_edge_kind",
    "target_edge_evidence_span",
    "effective_relation",
}
END_FIELDS = {
    "event",
    "case_id",
    "stages",
    "route",
    "request_count",
    "model_call_latency_sum_ms",
    "elapsed_ms",
}
ATTACHMENTS = {"subject", "location", "implicit", "unresolved"}
EDGES = {"same_entity", "part_of", "located_at", "coreference", "distinct", "unresolved"}
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
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ERROR_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class ContractError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_file(path: Path) -> str:
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


def _clauses(message: str) -> tuple[str, ...]:
    if type(message) is not str or not message.strip():
        raise ContractError("source_text_invalid", "user_message")
    clauses = tuple(part.strip() for part in re.split(r"(?<=[.!?。])\s+", message) if part.strip())
    if not clauses:
        raise ContractError("source_text_invalid", "user_message")
    return clauses


def _span(item: object, clauses: tuple[str, ...], field: str) -> dict | None:
    if item is None:
        return None
    if type(item) is not dict or set(item) != {"clause_index", "quote"}:
        raise ContractError("quote_fields_invalid", field)
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or not 1 <= index <= len(clauses):
        raise ContractError("quote_index_invalid", field)
    if type(quote) is not str:
        raise ContractError("quote_type_invalid", field)
    if not quote.strip() or quote != quote.strip():
        raise ContractError("quote_blank", field)
    start = clauses[index - 1].find(quote)
    if start < 0:
        raise ContractError("quote_unanchored", field)
    if clauses[index - 1].find(quote, start + 1) >= 0:
        raise ContractError("quote_nonunique", field)
    return {
        "clause_index": index,
        "quote": quote,
        "start": start,
        "end": start + len(quote),
        "quote_sha256": _digest(quote.encode("utf-8")),
    }


def _public(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {key: item[key] for key in ("clause_index", "start", "end", "quote_sha256")}


def _overlaps(left: dict, right: dict) -> bool:
    return left["clause_index"] == right["clause_index"] and max(
        left["start"], right["start"]
    ) < min(left["end"], right["end"])


def replay_graph(raw: str, message: str, event: dict) -> dict:
    """Independently replay graph contract, without scoring its meaning."""
    clauses = _clauses(message)
    event_span = _span(event, clauses, "event_span")
    if event_span is None:
        raise ContractError("event_missing", "event_span")
    parsed = _json(raw)
    if type(parsed) is not dict or set(parsed) != GRAPH_FIELDS:
        raise ContractError("fields_invalid", "evidence_graph")
    attachment, edge = parsed["event_subject_kind"], parsed["target_edge_kind"]
    if type(attachment) is not str or attachment not in ATTACHMENTS:
        raise ContractError("attachment_kind_invalid", "event_subject_kind")
    if type(edge) is not str or edge not in EDGES:
        raise ContractError("edge_kind_invalid", "target_edge_kind")
    spans = {
        name: _span(parsed[name], clauses, name)
        for name in ("subject_span", "event_subject_evidence_span", "target_edge_evidence_span")
    }
    subject = spans["subject_span"]
    cue = spans["event_subject_evidence_span"]
    resolved = attachment != "unresolved"
    if (subject is not None) != resolved or (cue is not None) != resolved:
        raise ContractError("attachment_consistency_invalid", "event_subject_kind")
    if resolved:
        if not _overlaps(cue, event_span):
            raise ContractError("event_attachment_unlinked", "event_subject_evidence_span")
        if attachment in {"subject", "location"} and not _overlaps(cue, subject):
            raise ContractError("subject_attachment_unlinked", "subject_span")
    edge_cue = spans["target_edge_evidence_span"]
    if edge == "unresolved":
        if edge_cue is not None:
            raise ContractError("edge_consistency_invalid", "target_edge_evidence_span")
    elif subject is None or edge_cue is None:
        raise ContractError("edge_consistency_invalid", "target_edge_kind")
    elif edge == "distinct" and not (
        edge_cue["clause_index"] == subject["clause_index"]
        and edge_cue["start"] <= subject["start"]
        and subject["end"] <= edge_cue["end"]
    ):
        raise ContractError("distinct_subject_unlinked", "target_edge_evidence_span")
    relation = (
        "current"
        if edge in {"same_entity", "part_of", "located_at", "coreference"}
        else "other"
        if edge == "distinct"
        else "unknown"
    )
    return {
        **spans,
        "event_subject_kind": attachment,
        "target_edge_kind": edge,
        "effective_relation": relation,
    }


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, check=True, capture_output=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or not relative or relative.startswith("/"):
        raise ValueError("frozen source reference invalid")
    if ".." in Path(relative).parts:
        raise ValueError("frozen source reference invalid")
    return _git("show", f"{commit}:{relative}")


def _source_paths(commit: str) -> set[str]:
    paths = set()
    for prefix in (
        "experiments/as_safety_v2",
        "experiments/as_safety_v4",
        "experiments/as_safety_evidence_graph_v1",
    ):
        names = _git("ls-tree", "-r", "--name-only", commit, "--", prefix)
        paths.update(name for name in names.decode().splitlines() if name.endswith(".py"))
    compiler = "scripts/build_as_safety_evidence_graph_labels.py"
    if _git("ls-tree", "-r", "--name-only", commit, "--", compiler).decode().strip() != compiler:
        raise ValueError("frozen graph label compiler missing")
    paths.add(compiler)
    required = {
        "experiments/as_safety_evidence_graph_v1/__init__.py",
        "experiments/as_safety_evidence_graph_v1/run.py",
        "experiments/as_safety_evidence_graph_v1/verify.py",
    }
    if not required <= paths:
        raise ValueError("frozen graph source package incomplete")
    return paths


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str]:
    """Verify source/input/model identity from the committed frozen version."""
    raw = path.read_bytes()
    protocol = _json(raw.decode("utf-8"))
    if type(protocol) is not dict or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if (
        type(commit) is not str
        or not COMMIT_RE.fullmatch(commit)
        or protocol["kind"] != KIND
        or protocol["claim_scope"] != SCOPE
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["model_sha256"] != MODEL_SHA
        or protocol["server_image_digest"] != IMAGE
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or protocol["retry_policy"] != "no_retry_manual_audit_on_interruption"
        or protocol["private_output"] != "outside_repository_mode_0700_files_0600"
    ):
        raise ValueError("protocol identity differs")
    if _digest_file(model_path) != MODEL_SHA:
        raise ValueError("model digest differs")
    manifest = protocol["source_manifest"]
    if type(manifest) is not dict or set(manifest) != _source_paths(commit):
        raise ValueError("source manifest paths differ")
    for relative, expected in manifest.items():
        frozen = _frozen(commit, relative)
        if (
            type(expected) is not str
            or not SHA_RE.fullmatch(expected)
            or _digest(frozen) != expected
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
            or _digest(frozen) != expected
            or source.read_bytes() != frozen
        ):
            raise ValueError(f"input manifest differs: {key}")
    relative = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative}") != raw:
        raise ValueError("protocol must be committed")
    return protocol, _digest(raw)


def _review_cell(cell: str, allowed: set[str]) -> tuple[str, dict | None]:
    """Read one reviewed kind and literal quote without using the compiler."""
    values = re.findall(r"`([^`]*)`", cell)
    if len(values) != 2 or values[0] not in allowed:
        raise ValueError("graph review cell differs")
    kind, quote = values
    if quote == "null":
        if kind != "unresolved" or re.search(r"\d+\s+`null`", cell):
            raise ValueError("graph review unresolved cell differs")
        return kind, None
    matches = re.findall(r"(?:^|\s)(\d+)\s+`([^`]+)`", cell)
    if len(matches) != 1 or matches[0][1] != quote:
        raise ValueError("graph review quote differs")
    return kind, {"clause_index": int(matches[0][0]), "quote": quote}


def _review_labels(path: Path, cases: list[dict]) -> list[dict]:
    """Reconstruct all 19 actionable rows directly from the reviewed table."""
    rows: dict[tuple[str, int], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ES"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) != 5 or re.fullmatch(r"ES\d{2}(?:-[12])?", columns[0]) is None:
            raise ValueError("graph review row differs")
        case_id, _, suffix = columns[0].partition("-")
        key = (case_id, int(suffix) if suffix else 1)
        if key in rows:
            raise ValueError("duplicate graph review row")
        attachment, attachment_span = _review_cell(columns[2], ATTACHMENTS)
        edge, edge_span = _review_cell(columns[3], EDGES)
        rows[key] = {
            "event_index": key[1],
            "event_subject_kind": attachment,
            "event_subject_evidence_span": attachment_span,
            "target_edge_kind": edge,
            "target_edge_evidence_span": edge_span,
        }
    assembled = []
    used: set[tuple[str, int]] = set()
    for case in cases:
        events = []
        for index, event in enumerate(case["events"], 1):
            key = (case["id"], index)
            if event["occurrence"] == "nonoccurring":
                if key in rows:
                    raise ValueError("nonoccurring graph review row differs")
                events.append(
                    {
                        "event_index": index,
                        "event_subject_kind": None,
                        "event_subject_evidence_span": None,
                        "target_edge_kind": None,
                        "target_edge_evidence_span": None,
                    }
                )
                continue
            if key not in rows:
                raise ValueError("missing graph review row")
            used.add(key)
            events.append(rows[key])
        assembled.append({"id": case["id"], "events": events})
    if used != set(rows):
        raise ValueError("extra graph review row")
    return assembled


def load_labels(path: Path, cases: list[dict]) -> list[dict]:
    """Require human-approved edge labels consistent with prior reviewed relations."""
    payload = _json(path.read_text(encoding="utf-8"))
    if (
        type(payload) is not dict
        or set(payload) != {"kind", "review_status", "review_sha256", "cases"}
        or payload["kind"] != "as_safety_evidence_graph_v1_labels"
        or payload["review_status"] != "owner_approved_for_exploratory_evaluation"
        or payload["review_sha256"] != _digest(INPUTS["graph_field_review"].read_bytes())
        or type(payload["cases"]) is not list
        or len(payload["cases"]) != len(cases)
    ):
        raise ValueError("graph label provenance differs")
    if payload["cases"] != _review_labels(INPUTS["graph_field_review"], cases):
        raise ValueError("graph labels differ from reviewed table")
    for item, case in zip(payload["cases"], cases, strict=True):
        if (
            type(item) is not dict
            or set(item) != {"id", "events"}
            or item["id"] != case["id"]
            or type(item["events"]) is not list
            or len(item["events"]) != len(case["events"])
        ):
            raise ValueError("graph label case alignment differs")
        clauses = _clauses(case["user_message"])
        for index, (label, event) in enumerate(zip(item["events"], case["events"], strict=True), 1):
            if (
                type(label) is not dict
                or set(label)
                != {
                    "event_index",
                    "event_subject_kind",
                    "event_subject_evidence_span",
                    "target_edge_kind",
                    "target_edge_evidence_span",
                }
                or type(label["event_index"]) is not int
                or label["event_index"] != index
            ):
                raise ValueError("graph label event alignment differs")
            if event["occurrence"] == "nonoccurring":
                if any(
                    label[field] is not None
                    for field in (
                        "event_subject_kind",
                        "event_subject_evidence_span",
                        "target_edge_kind",
                        "target_edge_evidence_span",
                    )
                ):
                    raise ValueError("nonoccurring graph label differs")
                continue
            attachment, edge = label["event_subject_kind"], label["target_edge_kind"]
            if attachment not in ATTACHMENTS or edge not in EDGES:
                raise ValueError("graph label edge code differs")
            attachment_span = _span(
                label["event_subject_evidence_span"], clauses, "label_attachment"
            )
            edge_span = _span(label["target_edge_evidence_span"], clauses, "label_edge")
            subject_null = event["hazard_owner_span"] is None
            if subject_null != (attachment == "unresolved") or subject_null != (
                edge == "unresolved"
            ):
                raise ValueError("graph label conflicts with reviewed subject")
            if (attachment == "unresolved") != (attachment_span is None):
                raise ValueError("graph label attachment consistency differs")
            if (edge == "unresolved") != (edge_span is None):
                raise ValueError("graph label edge consistency differs")
            derived = (
                "current"
                if edge in {"same_entity", "part_of", "located_at", "coreference"}
                else "other"
                if edge == "distinct"
                else "unknown"
            )
            if derived != event["owner_to_target"]:
                raise ValueError("graph label relation contradicts reviewed relation")
            proposed = {
                "subject_span": event["hazard_owner_span"],
                "event_subject_kind": attachment,
                "event_subject_evidence_span": label["event_subject_evidence_span"],
                "target_edge_kind": edge,
                "target_edge_evidence_span": label["target_edge_evidence_span"],
            }
            try:
                replay_graph(
                    json.dumps(proposed, ensure_ascii=False),
                    case["user_message"],
                    event["event_span"],
                )
            except ContractError as error:
                raise ValueError("graph label evidence structure differs") from error
    return payload["cases"]


def _duration(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value < 86_400_000


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
    if len(raw) != size or _digest(raw) != sha:
        raise ValueError("private raw response differs")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("private raw encoding differs") from error
    if not decoded.strip():
        raise ValueError("private raw content blank")
    return decoded


def _check_stage_meta(stage: dict, *, called: bool) -> None:
    if stage["called"] is not called or stage["skip_reason"] != (
        None if called else "nonoccurring"
    ):
        raise ValueError("stage call transition differs")
    if not called:
        if stage["status"] != "skipped" or any(
            stage[name] is not None
            for name in (
                "error_code",
                "error_field",
                "finish_reason",
                "latency_ms",
                "request_latency_ms",
                "raw_sha256",
                "raw_bytes",
            )
        ):
            raise ValueError("skipped stage metadata differs")
        return
    if (
        not _duration(stage["latency_ms"])
        or not _duration(stage["request_latency_ms"])
        or stage["request_latency_ms"] > stage["latency_ms"] + 0.01
        or stage["status"] not in {"validated", "contract_error", "response_error"}
    ):
        raise ValueError("called stage metadata differs")
    code, field = stage["error_code"], stage["error_field"]
    if code is not None and (type(code) is not str or not ERROR_RE.fullmatch(code)):
        raise ValueError("stage error code differs")
    if field is not None and (type(field) is not str or len(field) > 96):
        raise ValueError("stage error field differs")


def _replay_stage(stage: dict, raw: str | None, message: str, event: dict) -> dict | None:
    if stage["finish_reason"] is None:
        if (
            raw is not None
            or stage["status"] != "response_error"
            or stage["error_code"] not in TRANSPORT_ERRORS
            or stage["error_field"] is not None
        ):
            raise ValueError("transport result differs")
        return None
    if stage["finish_reason"] == "length":
        if (
            raw is None
            or stage["status"] != "response_error"
            or stage["error_code"] != "finish_length"
            or stage["error_field"] is not None
        ):
            raise ValueError("truncated response result differs")
        return None
    if stage["finish_reason"] != "stop" or raw is None:
        raise ValueError("response finish differs")
    try:
        result = replay_graph(raw, message, event)
    except ContractError as error:
        if stage["status"] != "contract_error" or (stage["error_code"], stage["error_field"]) != (
            error.code,
            error.field,
        ):
            raise ValueError("contract error differs") from None
        return None
    if (
        stage["status"] != "validated"
        or stage["error_code"] is not None
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
    if (
        failed
        or overflow
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


def audit_end(row: dict, case: dict, private_dir: Path) -> dict:
    """Replay each public event against its private raw bytes and source text."""
    if type(row) is not dict or set(row) != END_FIELDS or row["event"] != "end":
        raise ValueError("journal end fields differ")
    if row["case_id"] != case["id"]:
        raise ValueError("journal case identity differs")
    stages, events = row["stages"], case["events"]
    if type(stages) is not list or len(stages) != len(events):
        raise ValueError("graph event alignment differs")
    clauses = _clauses(case["user_message"])
    relations: list[str | None] = []
    decisions: list[dict | None] = []
    failed = False
    expected_raw: set[str] = set()
    for index, (stage, event) in enumerate(zip(stages, events, strict=True), 1):
        if type(stage) is not dict or set(stage) != STAGE_FIELDS:
            raise ValueError("graph stage fields differ")
        if type(stage["event_index"]) is not int or stage["event_index"] != index:
            raise ValueError("graph event index differs")
        event_span = _span(event["event_span"], clauses, "event_span")
        if stage["event_span"] != _public(event_span) or stage["occurrence"] != event["occurrence"]:
            raise ValueError("oracle event input differs")
        called = event["occurrence"] != "nonoccurring"
        _check_stage_meta(stage, called=called)
        raw_name = f"{case['id']}-graph-{index}.json.txt"
        raw = _read_raw(stage, private_dir / raw_name)
        if raw is not None:
            expected_raw.add(raw_name)
        if not called:
            if any(stage[field] is not None for field in GRAPH_FIELDS | {"effective_relation"}):
                raise ValueError("skipped graph decision differs")
            decisions.append(None)
            relations.append(None)
            continue
        decision = _replay_stage(stage, raw, case["user_message"], event["event_span"])
        if decision is None:
            if any(stage[field] is not None for field in GRAPH_FIELDS | {"effective_relation"}):
                raise ValueError("invalid graph decision differs")
            decisions.append(None)
            relations.append(None)
            failed = True
            continue
        public = {
            "subject_span": _public(decision["subject_span"]),
            "event_subject_kind": decision["event_subject_kind"],
            "event_subject_evidence_span": _public(decision["event_subject_evidence_span"]),
            "target_edge_kind": decision["target_edge_kind"],
            "target_edge_evidence_span": _public(decision["target_edge_evidence_span"]),
            "effective_relation": decision["effective_relation"],
        }
        if any(stage[field] != value for field, value in public.items()):
            raise ValueError("graph public decision differs")
        decisions.append(decision)
        relations.append(decision["effective_relation"])
    route = _route(events, relations, overflow=case["overflow"], failed=failed)
    calls = sum(int(stage["called"]) for stage in stages)
    call_ms = round(sum(stage["request_latency_ms"] or 0 for stage in stages), 3)
    stage_ms = round(sum(stage["latency_ms"] or 0 for stage in stages), 3)
    if (
        row["route"] != route
        or type(row["request_count"]) is not int
        or row["request_count"] != calls
        or not _duration(row["elapsed_ms"])
        or row["model_call_latency_sum_ms"] != call_ms
        or row["elapsed_ms"] + 0.01 < stage_ms
    ):
        raise ValueError("journal route or call metrics differ")
    return {
        "case_id": case["id"],
        "route": route,
        "request_count": calls,
        "relations": relations,
        "decisions": decisions,
        "statuses": [stage["status"] for stage in stages],
        "called": [stage["called"] for stage in stages],
        "request_latencies_ms": [
            stage["request_latency_ms"] for stage in stages if stage["called"]
        ],
        "elapsed_ms": row["elapsed_ms"],
        "raw_files": expected_raw,
    }


def _private_dir(path: Path) -> None:
    if (
        path.resolve().is_relative_to(ROOT)
        or path.is_symlink()
        or not path.is_dir()
        or stat.S_IMODE(path.stat().st_mode) != 0o700
    ):
        raise ValueError("private raw directory boundary differs")


def summarize(audited: list[dict], cases: list[dict], labels: list[dict]) -> dict:
    """Recalculate all published counts from replayed private responses."""
    if len(audited) != len(cases) or len(labels) != len(cases):
        raise ValueError("summary case count differs")
    categories = ("observed_current", "observed_other", "observed_unknown", "uncertain_current")
    category_counts = dict.fromkeys(categories, 0)
    category_correct = dict.fromkeys(categories, 0)
    relation_correct = subject_exact = subject_null_correct = attachment_correct = edge_correct = 0
    attachment_evidence_exact = edge_evidence_exact = all_fields_exact = 0
    label_joint_correct = 0
    attachment_gold_nonnull = edge_gold_nonnull = 0
    case_relation_correct: dict[str, bool] = {}
    for result, case, label_case in zip(audited, cases, labels, strict=True):
        if result["case_id"] != case["id"] or label_case["id"] != case["id"]:
            raise ValueError("summary case order differs")
        clauses = _clauses(case["user_message"])
        all_correct = True
        for index, (event, label, decision, status) in enumerate(
            zip(
                case["events"],
                label_case["events"],
                result["decisions"],
                result["statuses"],
                strict=True,
            )
        ):
            if label["event_index"] != index + 1:
                raise ValueError("summary event order differs")
            if event["occurrence"] == "nonoccurring":
                continue
            category = f"{event['occurrence']}_{event['owner_to_target']}"
            if category not in category_counts:
                raise ValueError("gold relation category differs")
            category_counts[category] += 1
            valid = status == "validated"
            relation_match = valid and decision["effective_relation"] == event["owner_to_target"]
            category_correct[category] += relation_match
            relation_correct += relation_match
            all_correct &= relation_match
            gold_subject = _public(_span(event["hazard_owner_span"], clauses, "gold_subject"))
            predicted_subject = _public(decision["subject_span"]) if valid else None
            subject_match = valid and predicted_subject == gold_subject
            if event["hazard_owner_span"] is not None:
                subject_exact += subject_match
            else:
                subject_null_correct += subject_match
            attachment_match = (
                valid and decision["event_subject_kind"] == label["event_subject_kind"]
            )
            edge_match = valid and decision["target_edge_kind"] == label["target_edge_kind"]
            attachment_correct += attachment_match
            edge_correct += edge_match
            evidence_matches: list[bool] = []
            for field in ("event_subject_evidence_span", "target_edge_evidence_span"):
                expected = _public(_span(label[field], clauses, field))
                if expected is not None:
                    if field == "event_subject_evidence_span":
                        attachment_gold_nonnull += 1
                    else:
                        edge_gold_nonnull += 1
                predicted = _public(decision[field]) if valid else None
                match = valid and predicted == expected
                evidence_matches.append(match)
                if expected is not None and match:
                    if field == "event_subject_evidence_span":
                        attachment_evidence_exact += 1
                    else:
                        edge_evidence_exact += 1
            label_match = subject_match and attachment_match and edge_match and relation_match
            label_joint_correct += label_match
            all_fields_exact += (
                subject_match
                and attachment_match
                and edge_match
                and all(evidence_matches)
                and relation_match
            )
        case_relation_correct[case["id"]] = all_correct
    by_id = {case["id"]: (result, case) for result, case in zip(audited, cases, strict=True)}
    pairs = (("ES01", "ES09"), ("ES02", "ES11"))
    eligible_pairs = [pair for pair in pairs if all(case_id in by_id for case_id in pair)]
    pairs_correct = sum(
        all(
            case_relation_correct[case_id]
            and by_id[case_id][0]["route"] == by_id[case_id][1]["expected_route"]
            for case_id in pair
        )
        for pair in eligible_pairs
    )
    elapsed = sorted(result["elapsed_ms"] for result in audited)
    request_latencies = sorted(
        latency for result in audited for latency in result["request_latencies_ms"]
    )
    normal = "collecting_service_request"
    return {
        "event": "summary",
        "cases": len(audited),
        "gold_event_count": sum(len(case["events"]) for case in cases),
        "actionable_gold_event_count": sum(
            event["occurrence"] != "nonoccurring" for case in cases for event in case["events"]
        ),
        "relation_correct": relation_correct,
        "subject_exact_nonnull": subject_exact,
        "subject_null_correct": subject_null_correct,
        "subject_gold_nonnull_count": sum(
            event["occurrence"] != "nonoccurring" and event["hazard_owner_span"] is not None
            for case in cases
            for event in case["events"]
        ),
        "subject_gold_null_count": sum(
            event["occurrence"] != "nonoccurring" and event["hazard_owner_span"] is None
            for case in cases
            for event in case["events"]
        ),
        "attachment_kind_correct": attachment_correct,
        "attachment_evidence_exact": attachment_evidence_exact,
        "attachment_evidence_gold_nonnull_count": attachment_gold_nonnull,
        "edge_kind_correct": edge_correct,
        "edge_evidence_exact": edge_evidence_exact,
        "edge_evidence_gold_nonnull_count": edge_gold_nonnull,
        "label_joint_correct": label_joint_correct,
        "all_fields_exact": all_fields_exact,
        "category_counts": category_counts,
        "category_relation_correct": category_correct,
        "route_correct": sum(
            result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "model_involved_cases": sum(result["request_count"] > 0 for result in audited),
        "model_involved_route_correct": sum(
            result["request_count"] > 0 and result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "multi_event_cases": sum(len(case["events"]) > 1 for case in cases),
        "multi_event_route_correct": sum(
            len(case["events"]) > 1 and result["route"] == case["expected_route"]
            for result, case in zip(audited, cases, strict=True)
        ),
        "contrast_pair_count": len(eligible_pairs),
        "contrast_pairs_correct": pairs_correct,
        "missed_direct_current": sum(
            case["expected_route"] == "safety_action_required"
            and result["route"] != "safety_action_required"
            for result, case in zip(audited, cases, strict=True)
        ),
        "false_direct_other": sum(
            case["expected_route"] == normal
            and result["route"] == "safety_action_required"
            and any(
                event["occurrence"] == "observed" and event["owner_to_target"] == "other"
                for event in case["events"]
            )
            for result, case in zip(audited, cases, strict=True)
        ),
        "unnecessary_confirm": sum(
            case["expected_route"] == normal and result["route"] == "confirming_safety_status"
            for result, case in zip(audited, cases, strict=True)
        ),
        "graph_errors": sum(
            called and status != "validated"
            for result in audited
            for called, status in zip(result["called"], result["statuses"], strict=True)
        ),
        "request_count": sum(result["request_count"] for result in audited),
        "graph_valid": sum(
            status == "validated" for result in audited for status in result["statuses"]
        ),
        "case_elapsed_p50_ms": round(statistics.median(elapsed), 3) if elapsed else None,
        "case_elapsed_p95_ms": round(elapsed[math.ceil(len(elapsed) * 0.95) - 1], 3)
        if elapsed
        else None,
        "request_latency_p50_ms": round(statistics.median(request_latencies), 3)
        if request_latencies
        else None,
        "request_latency_p95_ms": round(
            request_latencies[math.ceil(len(request_latencies) * 0.95) - 1], 3
        )
        if request_latencies
        else None,
    }


def verify(protocol_path: Path, journal_path: Path, private_dir: Path, *, model_path: Path) -> dict:
    """Reject any journal, raw, source, label or aggregate mismatch."""
    _protocol, protocol_sha = check_protocol(protocol_path, model_path)
    _private_dir(private_dir)
    cases = load_cases(DATASET)
    labels = load_labels(LABELS, cases)
    journal_bytes = journal_path.read_bytes()
    rows = [_json(line) for line in journal_bytes.decode("utf-8").splitlines()]
    if len(rows) != 2 + 2 * len(cases):
        raise ValueError("journal row count differs")
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise ValueError("journal header differs")
    audited = []
    for index, case in enumerate(cases):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case["id"]}:
            raise ValueError("journal begin differs")
        audited.append(audit_end(rows[2 + 2 * index], case, private_dir))
    expected_summary = summarize(audited, cases, labels)
    if rows[-1] != expected_summary:
        raise ValueError("journal summary differs")
    expected_files = set().union(*(result["raw_files"] for result in audited))
    observed_files = {path.name for path in private_dir.iterdir()}
    if observed_files != expected_files:
        raise ValueError("private raw file inventory differs")
    return {
        "kind": KIND,
        "protocol_sha256": protocol_sha,
        "journal_sha256": _digest(journal_bytes),
        "private_raw_count": len(expected_files),
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
