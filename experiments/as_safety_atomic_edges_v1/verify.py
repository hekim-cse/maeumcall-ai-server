"""Independently replay an ES E→B diagnostic journal and private responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/structured_nlu/data/ai_heldout"
INPUTS = {
    "dataset": DATA / "as-safety-event-source-v4-exploration-reviewed.v1.json",
    "utterance_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_review.md",
    "field_review": ROOT / "docs/portfolio/nlu_safety_event_source_v4_field_review.md",
    "method": ROOT / "docs/portfolio/nlu_safety_atomic_edge_v1_method.md",
    "edge_review": ROOT / "docs/portfolio/nlu_safety_evidence_graph_v1_field_review.md",
}
SOURCE_PATHS = {
    "experiments/as_safety_atomic_edges_v1/event_owner.py",
    "experiments/as_safety_atomic_edges_v1/run.py",
    "experiments/as_safety_atomic_edges_v1/verify.py",
    "experiments/as_safety_v2/evidence_graph.py",
    "experiments/as_safety_v2/extraction.py",
    "experiments/as_safety_v2/json_contract.py",
    "experiments/as_safety_v2/quotes.py",
    "experiments/as_safety_v2/transport.py",
    "experiments/as_safety_v4/cases.py",
    "experiments/as_safety_v4/contract.py",
    "experiments/as_safety_v4/run.py",
}
KIND = "as_safety_atomic_edge_v1_development_v1"
SCOPE = "already_exposed_ai_authored_user_reviewed_es_development_diagnostic_only"
CASE_ORDER = tuple(f"ES{index:02}" for index in range(1, 21))
CALL_ORDER = tuple(
    f"ES{case:02}:{event}"
    for case, event in (
        [(index, 1) for index in range(1, 6)]
        + [(6, 1), (6, 2)]
        + [(index, 1) for index in range(7, 16)]
        + [(index, 1) for index in range(16, 19)]
    )
)
SKIP_ORDER = ("ES15:2", "ES19:1", "ES20:1")
IMAGE = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
MODEL_SHA = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
ENDPOINT = "http://127.0.0.1:18081/v1/chat/completions"
MODEL_ID = "/models/kanana.gguf"
CONTAINER_NAME = "as-safety-atomic-edge-v1"
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
SERVER_ARGS = (
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
)
REQUEST_POLICY = {
    "max_tokens": 320,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "seed": 0,
}
PROTOCOL_FIELDS = {
    "kind",
    "claim_scope",
    "case_order",
    "call_order",
    "skip_order",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "container_name",
    "endpoint",
    "model_id",
    "server_args",
    "local_runtime",
    "request_policy",
    "retry_policy",
    "private_output",
    "score_scope",
}
KINDS = {"subject", "location", "implicit", "unresolved"}
FIELDS = {"subject_span", "event_subject_kind", "event_subject_evidence_span"}
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


class VerificationError(ValueError):
    """A bounded, non-content-bearing verification failure."""


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


def _committed(commit: str, relative: str) -> bytes:
    if not COMMIT_RE.fullmatch(commit) or not relative or relative.startswith("/"):
        raise VerificationError("frozen source reference differs")
    if ".." in Path(relative).parts:
        raise VerificationError("frozen source reference differs")
    return _git("show", f"{commit}:{relative}")


def _expected_protocol() -> dict:
    return {
        "kind": KIND,
        "claim_scope": SCOPE,
        "case_order": list(CASE_ORDER),
        "call_order": list(CALL_ORDER),
        "skip_order": list(SKIP_ORDER),
        "model_sha256": MODEL_SHA,
        "server_image_digest": IMAGE,
        "container_name": CONTAINER_NAME,
        "endpoint": ENDPOINT,
        "model_id": MODEL_ID,
        "server_args": list(SERVER_ARGS),
        "local_runtime": RUNTIME,
        "request_policy": REQUEST_POLICY,
        "retry_policy": "no_retry_manual_audit_on_interruption",
        "private_output": "outside_repository_mode_0700_files_0600",
        "score_scope": (
            "event_owner_only; reviewed_current_label_for_failure_stratification_only; "
            "no B_to_A scoring; no route calculation"
        ),
    }


def check_protocol(path: Path, model_path: Path) -> tuple[dict, str, dict[str, bytes]]:
    """Verify frozen commit blobs and return the exact reviewed input bytes.

    The replay verifier may evolve after the frozen run; its own hash is reported
    separately rather than requiring the current working tree to match that run.
    """
    raw = path.read_bytes()
    protocol = _json(raw.decode("utf-8"))
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise VerificationError("protocol fields differ")
    if any(protocol.get(key) != value for key, value in _expected_protocol().items()):
        raise VerificationError("protocol identity differs")
    commit = protocol.get("frozen_code_commit")
    if type(commit) is not str or not COMMIT_RE.fullmatch(commit):
        raise VerificationError("frozen code commit differs")
    if not model_path.is_file() or _digest_file(model_path) != MODEL_SHA:
        raise VerificationError("model file is missing or its SHA-256 differs")
    manifest = protocol.get("source_manifest")
    if type(manifest) is not dict or set(manifest) != SOURCE_PATHS:
        raise VerificationError("source manifest paths differ")
    for relative, expected in manifest.items():
        frozen = _committed(commit, relative)
        if (
            type(expected) is not str
            or not SHA_RE.fullmatch(expected)
            or _digest(frozen) != expected
            or (
                relative
                not in {
                    "experiments/as_safety_atomic_edges_v1/run.py",
                    "experiments/as_safety_atomic_edges_v1/verify.py",
                }
                and (ROOT / relative).read_bytes() != frozen
            )
        ):
            raise VerificationError("frozen source differs")
    hashes = protocol.get("input_hashes")
    if type(hashes) is not dict or set(hashes) != set(INPUTS):
        raise VerificationError("input manifest paths differ")
    verified_inputs = {}
    for key, source in INPUTS.items():
        frozen = _committed(commit, source.relative_to(ROOT).as_posix())
        expected = hashes[key]
        current = source.read_bytes()
        if (
            type(expected) is not str
            or not SHA_RE.fullmatch(expected)
            or _digest(frozen) != expected
            or current != frozen
        ):
            raise VerificationError("frozen input differs")
        verified_inputs[key] = current
    relative = path.resolve().relative_to(ROOT).as_posix()
    if _git("show", f"HEAD:{relative}") != raw:
        raise VerificationError("protocol is not the committed version")
    return protocol, _digest(raw), verified_inputs


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise VerificationError("nonfinite JSON value")


def _json(raw: str) -> object:
    try:
        return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VerificationError("invalid JSON") from error


def _clauses(message: str) -> tuple[str, ...]:
    if type(message) is not str or not message.strip():
        raise VerificationError("source text invalid")
    clauses = tuple(part.strip() for part in re.split(r"(?<=[.!?。])\s+", message) if part.strip())
    if not clauses:
        raise VerificationError("source text invalid")
    return clauses


def _span(item: object, clauses: tuple[str, ...]) -> dict | None:
    if item is None:
        return None
    if type(item) is not dict or set(item) != {"clause_index", "quote"}:
        raise VerificationError("quote fields invalid")
    index, quote = item["clause_index"], item["quote"]
    if type(index) is not int or not 1 <= index <= len(clauses):
        raise VerificationError("quote index invalid")
    if type(quote) is not str or not quote or quote != quote.strip():
        raise VerificationError("quote blank or invalid")
    first = clauses[index - 1].find(quote)
    if first < 0 or clauses[index - 1].find(quote, first + 1) >= 0:
        raise VerificationError("quote is not uniquely anchored")
    return {"clause_index": index, "quote": quote, "start": first, "end": first + len(quote)}


def _contains(outer: dict, inner: dict) -> bool:
    return (
        outer["clause_index"] == inner["clause_index"]
        and outer["start"] <= inner["start"]
        and inner["end"] <= outer["end"]
    )


def _same_quote(actual: dict | None, expected: dict | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return (
        actual["clause_index"] == expected["clause_index"] and actual["quote"] == expected["quote"]
    )


def load_scoring_cases(path: Path, *, raw: bytes | None = None) -> list[dict]:
    """Load E→B gold plus a current-risk stratum; never score B→A or routes."""
    payload = _json((path.read_bytes() if raw is None else raw).decode("utf-8"))
    if type(payload) is not dict or set(payload) != {
        "kind",
        "provenance",
        "review_status",
        "review_date",
        "source_sha256",
        "cases",
    }:
        raise VerificationError("reviewed dataset fields differ")
    if (
        payload["kind"] != "as_safety_event_source_v4_exploration_reviewed_v1"
        or payload["provenance"] != "ai_authored_user_reviewed_exploration"
        or payload["review_status"] != "owner_approved_for_exploratory_evaluation"
        or payload["review_date"] != "2026-11-15"
        or payload["source_sha256"]
        != {
            "utterances": _digest(INPUTS["utterance_review"].read_bytes()),
            "fields": _digest(INPUTS["field_review"].read_bytes()),
        }
    ):
        raise VerificationError("reviewed dataset provenance differs")
    source_cases = payload["cases"]
    if (
        type(source_cases) is not list
        or tuple(case.get("id") for case in source_cases if type(case) is dict) != CASE_ORDER
    ):
        raise VerificationError("reviewed case order differs")
    cases = []
    for source_case in source_cases:
        if type(source_case) is not dict:
            raise VerificationError("reviewed case invalid")
        case_id = source_case["id"]
        message = source_case["user_message"]
        if (
            type(message) is not str
            or source_case["utterance_sha256"] != _digest(message.encode("utf-8"))
            or type(source_case["events"]) is not list
        ):
            raise VerificationError("reviewed source message differs")
        clauses = _clauses(message)
        events = []
        for source_event in source_case["events"]:
            event_span = source_event["event_span"]
            occurrence = source_event["occurrence"]
            _span(event_span, clauses)
            if occurrence not in {"observed", "uncertain", "nonoccurring"}:
                raise VerificationError("reviewed occurrence differs")
            owner_span = source_event["hazard_owner_span"]
            if owner_span is not None:
                _span(owner_span, clauses)
            events.append(
                {
                    "event_span": event_span,
                    "occurrence": occurrence,
                    "hazard_owner_span": owner_span,
                    "is_current_product_risk": source_event["owner_to_target"] == "current",
                }
            )
        cases.append({"id": case_id, "user_message": message, "events": events})
    actual_calls = tuple(
        f"{case['id']}:{index}"
        for case in cases
        for index, event in enumerate(case["events"], 1)
        if event["occurrence"] != "nonoccurring"
    )
    skipped = tuple(
        f"{case['id']}:{index}"
        for case in cases
        for index, event in enumerate(case["events"], 1)
        if event["occurrence"] == "nonoccurring"
    )
    if actual_calls != CALL_ORDER or skipped != SKIP_ORDER:
        raise VerificationError("reviewed event order differs")
    return cases


def replay_event_owner(raw: str, message: str, event_span: dict) -> dict:
    """Reimplement the E→B wire contract without importing its candidate code."""
    clauses = _clauses(message)
    event = _span(event_span, clauses)
    if event is None:
        raise VerificationError("event missing")
    parsed = _json(raw)
    if type(parsed) is not dict or set(parsed) != FIELDS:
        raise VerificationError("output fields differ")
    kind = parsed["event_subject_kind"]
    if type(kind) is not str or kind not in KINDS:
        raise VerificationError("event subject kind invalid")
    subject = _span(parsed["subject_span"], clauses)
    evidence = _span(parsed["event_subject_evidence_span"], clauses)
    resolved = kind != "unresolved"
    if (subject is not None) != resolved or (evidence is not None) != resolved:
        raise VerificationError("unresolved spans inconsistent")
    if kind in {"subject", "location"} and (
        not _contains(evidence, event) or not _contains(evidence, subject)
    ):
        raise VerificationError("direct evidence does not contain event and subject")
    return {
        "subject_span": subject,
        "event_subject_kind": kind,
        "event_subject_evidence_span": evidence,
    }


def _review_cell(cell: str) -> tuple[str, dict | None]:
    match = re.fullmatch(
        r"`(subject|location|implicit|unresolved)`\s*·\s*(?:(\d+)\s+`([^`]+)`|`null`)",
        cell,
    )
    if match is None:
        raise VerificationError("reviewed E→B cell differs")
    kind, clause, quote = match.groups()
    if kind == "unresolved":
        if clause is not None or quote is not None or "`null`" not in cell:
            raise VerificationError("reviewed unresolved cell differs")
        return kind, None
    if clause is None or quote is None:
        raise VerificationError("reviewed quote missing")
    return kind, {"clause_index": int(clause), "quote": quote}


def load_edge_labels(path: Path, *, raw: bytes | None = None) -> dict[tuple[str, int], dict]:
    """Read only the E→B column; the B→A column is deliberately ignored."""
    labels = {}
    for line in (path.read_bytes() if raw is None else raw).decode("utf-8").splitlines():
        if not line.startswith("| ES"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) != 5 or re.fullmatch(r"ES\d{2}(?:-[12])?", columns[0]) is None:
            raise VerificationError("reviewed edge row differs")
        case_id, _, suffix = columns[0].partition("-")
        key = (case_id, int(suffix) if suffix else 1)
        if key in labels:
            raise VerificationError("duplicate reviewed edge row")
        kind, evidence = _review_cell(columns[2])
        labels[key] = {"event_subject_kind": kind, "event_subject_evidence_span": evidence}
    return labels


def _read_journal(path: Path, protocol_sha: str) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                raise VerificationError("blank journal line")
            row = _json(line)
            if type(row) is not dict:
                raise VerificationError("journal row invalid")
            rows.append(row)
    if not rows or rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise VerificationError("journal header differs")
    expected_order = tuple(
        sorted(
            CALL_ORDER + SKIP_ORDER,
            key=lambda key: (int(key.split(":")[0][2:]), int(key.split(":")[1])),
        )
    )
    result_rows = rows[1:]
    actual = tuple(f"{row.get('case_id')}:{row.get('event_index')}" for row in result_rows)
    if len(result_rows) != 22 or actual != expected_order:
        raise VerificationError("journal event order differs")
    fields = {
        "event",
        "case_id",
        "event_index",
        "called",
        "finish_reason",
        "error_code",
        "http_status",
        "raw_sha256",
        "raw_bytes",
        "request_latency_ms",
    }
    for row in result_rows:
        if set(row) not in (fields, fields | {"skip_reason"}) or row["event"] != "result":
            raise VerificationError("journal result fields differ")
        if (
            type(row["case_id"]) is not str
            or row["case_id"] not in CASE_ORDER
            or type(row["event_index"]) is not int
            or row["event_index"] < 1
        ):
            raise VerificationError("journal event identity differs")
        called = row["called"]
        if type(called) is not bool:
            raise VerificationError("journal call state differs")
        key = f"{row['case_id']}:{row['event_index']}"
        if called != (key in CALL_ORDER):
            raise VerificationError("journal call/skip assignment differs")
        latency = row["request_latency_ms"]
        if called:
            finish_reason = row["finish_reason"]
            error_code = row["error_code"]
            http_status = row["http_status"]
            has_raw = row["raw_sha256"] is not None and row["raw_bytes"] is not None
            if type(latency) not in {int, float} or not math.isfinite(latency) or latency < 0:
                raise VerificationError("journal response metadata differs")
            if finish_reason == "stop":
                valid_response = error_code is None and http_status is None and has_raw
            elif finish_reason == "length":
                valid_response = error_code == "finish_length" and http_status is None and has_raw
            elif finish_reason is None:
                transport_codes = {
                    "redirect",
                    "request_too_large",
                    "http_status",
                    "http_error",
                    "network_error",
                    "timeout",
                    "response_too_large",
                    "invalid_response_json",
                    "response_fields_invalid",
                }
                valid_response = (
                    type(error_code) is str
                    and error_code in transport_codes
                    and row["raw_sha256"] is None
                    and row["raw_bytes"] is None
                    and (
                        type(http_status) is int and 100 <= http_status <= 599
                        if error_code in {"http_status", "http_error"}
                        else http_status is None
                    )
                )
            else:
                valid_response = False
            if not valid_response:
                raise VerificationError("journal response metadata differs")
        elif latency is not None:
            raise VerificationError("skipped event has latency")
        if called:
            if "skip_reason" in row:
                raise VerificationError("called event has skip reason")
        elif (
            row.get("skip_reason") != "nonoccurring"
            or row["finish_reason"] is not None
            or row["error_code"] is not None
            or row["http_status"] is not None
            or row["raw_sha256"] is not None
            or row["raw_bytes"] is not None
        ):
            raise VerificationError("skipped event fields differ")
    return result_rows


def _private_raw(private_dir: Path, row: dict, case_id: str, event_index: int) -> str | None:
    if row["raw_sha256"] is None:
        if row["raw_bytes"] is not None:
            raise VerificationError("raw response metadata differs")
        return None
    expected_name = f"{case_id}-event-{event_index}.json.txt"
    if (
        row["raw_sha256"] is None
        or type(row["raw_sha256"]) is not str
        or not SHA_RE.fullmatch(row["raw_sha256"])
        or type(row["raw_bytes"]) is not int
        or row["raw_bytes"] <= 0
    ):
        raise VerificationError("raw response metadata invalid")
    path = private_dir / expected_name
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise VerificationError("private response file or permissions differ")
    raw = path.read_bytes()
    if len(raw) != row["raw_bytes"] or _digest(raw) != row["raw_sha256"]:
        raise VerificationError("private response digest differs")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError("private response encoding differs") from error


def verify_result(
    protocol_path: Path,
    model_path: Path,
    journal_path: Path,
    private_dir: Path,
) -> dict:
    protocol, protocol_sha, verified_inputs = check_protocol(protocol_path, model_path)
    if private_dir.is_symlink() or private_dir.resolve().is_relative_to(ROOT):
        raise VerificationError("private responses must be outside the repository")
    if stat.S_IMODE(private_dir.stat().st_mode) != 0o700:
        raise VerificationError("private response directory permissions differ")
    rows = _read_journal(journal_path, protocol_sha)
    cases = load_scoring_cases(INPUTS["dataset"], raw=verified_inputs["dataset"])
    labels = load_edge_labels(INPUTS["edge_review"], raw=verified_inputs["edge_review"])
    result_by_key = {(row["case_id"], row["event_index"]): row for row in rows}
    expected_raw_files = {
        f"{row['case_id']}-event-{row['event_index']}.json.txt"
        for row in rows
        if row["raw_sha256"] is not None
    }
    expected_keys = set(labels)
    for case in cases:
        for index, event in enumerate(case["events"], 1):
            if event["occurrence"] == "nonoccurring":
                if (case["id"], index) in expected_keys:
                    raise VerificationError("nonoccurring event has E→B label")
            elif (case["id"], index) not in expected_keys:
                raise VerificationError("actionable event lacks E→B label")
    if len(labels) != 19:
        raise VerificationError("reviewed E→B denominator differs")

    case_by_id = {case["id"]: case for case in cases}
    contract_pass = 0
    contract_errors: dict[str, int] = {}
    transport_errors: dict[str, int] = {}
    b_denominator = 0
    b_exact = 0
    unresolved_denominator = 0
    unresolved_exact = 0
    kind_exact = 0
    evidence_exact = 0
    current_product_risk_extraction_failures = []
    resolved_evidence_denominator = 0
    resolved_evidence_exact = 0

    for key in CALL_ORDER:
        case_id, index_text = key.split(":")
        event_index = int(index_text)
        case = case_by_id[case_id]
        event = case["events"][event_index - 1]
        row = result_by_key[(case_id, event_index)]
        raw = _private_raw(private_dir, row, case_id, event_index)
        decision = None
        if row["error_code"] is not None:
            transport_errors[row["error_code"]] = transport_errors.get(row["error_code"], 0) + 1
        elif row["finish_reason"] != "stop" or raw is None:
            transport_errors["response_incomplete"] = (
                transport_errors.get("response_incomplete", 0) + 1
            )
        else:
            try:
                decision = replay_event_owner(raw, case["user_message"], event["event_span"])
            except VerificationError as error:
                code = str(error).replace(" ", "_")
                contract_errors[code] = contract_errors.get(code, 0) + 1
            else:
                contract_pass += 1

        label = labels[(case_id, event_index)]
        gold_subject = event["hazard_owner_span"]
        if gold_subject is not None:
            b_denominator += 1
            if (
                decision is not None
                and decision["subject_span"] is not None
                and _same_quote(decision["subject_span"], gold_subject)
            ):
                b_exact += 1
        else:
            unresolved_denominator += 1
            if (
                decision is not None
                and decision["event_subject_kind"] == "unresolved"
                and decision["subject_span"] is None
                and decision["event_subject_evidence_span"] is None
            ):
                unresolved_exact += 1
        gold_evidence = label["event_subject_evidence_span"]
        if gold_evidence is not None:
            resolved_evidence_denominator += 1
        if decision is not None:
            kind_exact += decision["event_subject_kind"] == label["event_subject_kind"]
            evidence = decision["event_subject_evidence_span"]
            exact_evidence = _same_quote(evidence, gold_evidence)
            evidence_exact += exact_evidence
            if gold_evidence is not None:
                resolved_evidence_exact += exact_evidence

        # This reviewed label only selects the requested E→B failure slice.
        if event["is_current_product_risk"]:
            triple_exact = (
                decision is not None
                and decision["subject_span"] is not None
                and gold_subject is not None
                and _same_quote(decision["subject_span"], gold_subject)
                and decision["event_subject_kind"] == label["event_subject_kind"]
                and decision["event_subject_evidence_span"] is not None
                and label["event_subject_evidence_span"] is not None
                and _same_quote(
                    decision["event_subject_evidence_span"],
                    label["event_subject_evidence_span"],
                )
            )
            if not triple_exact:
                reasons = []
                if decision is None:
                    reasons.append("contract_or_transport_failure")
                else:
                    if decision["subject_span"] is None or (
                        gold_subject is None
                        or not _same_quote(decision["subject_span"], gold_subject)
                    ):
                        reasons.append("subject_span_mismatch")
                    if decision["event_subject_kind"] != label["event_subject_kind"]:
                        reasons.append("event_subject_kind_mismatch")
                    actual_evidence = decision["event_subject_evidence_span"]
                    expected_evidence = label["event_subject_evidence_span"]
                    if not _same_quote(actual_evidence, expected_evidence):
                        reasons.append("event_subject_evidence_mismatch")
                current_product_risk_extraction_failures.append(
                    {"case_id": case_id, "event_index": event_index, "reasons": reasons}
                )

    if b_denominator != 18 or unresolved_denominator != 1:
        raise VerificationError("B or unresolved denominator differs")
    if (unresolved_denominator != 1) or not any(
        case["id"] == "ES17" and case["events"][0]["hazard_owner_span"] is None for case in cases
    ):
        raise VerificationError("ES17 unresolved reference differs")
    if {entry.name for entry in private_dir.iterdir()} != expected_raw_files:
        raise VerificationError("unexpected private response file")
    return {
        "claim_scope": SCOPE,
        "protocol_sha256": protocol_sha,
        "replay_verifier_sha256": _digest_file(Path(__file__)),
        "case_count": len(cases),
        "event_calls": len(CALL_ORDER),
        "nonoccurring_skips": list(SKIP_ORDER),
        "contract_pass": {"matched": contract_pass, "denominator": 19},
        "contract_errors": contract_errors,
        "transport_errors": transport_errors,
        "B_exact_match": {"matched": b_exact, "denominator": b_denominator},
        "ES17_unresolved": {"matched": unresolved_exact, "denominator": unresolved_denominator},
        "E_to_B_kind_exact_match": {"matched": kind_exact, "denominator": 19},
        "E_to_B_evidence_exact_match": {"matched": evidence_exact, "denominator": 19},
        "E_to_B_resolved_evidence_exact_match": {
            "matched": resolved_evidence_exact,
            "denominator": resolved_evidence_denominator,
        },
        "current_product_risk_E_to_B_extraction_failures": (
            current_product_risk_extraction_failures
        ),
        "current_product_risk_stratification": ("reviewed current label only; no B→A model score"),
        "B_to_A_evaluated": False,
        "final_safety_route_evaluated": False,
        "official_accuracy_or_improvement_claim": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_result(args.protocol, args.model_path, args.journal, args.private_dir),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
