"""Independently verify the exposed AH development baseline artifact.

This is a development diagnostic, not a new held-out or official test score.
The committed protocol and immutable prediction artifact are checked without
importing the experiment runner. Raw completions are replayed through the same
frozen live analyzer, so this proves the recorded output follows those bytes,
not that the analyzer's semantics are independently correct. A recorded
``transport_error`` means no completion text was received; without raw bytes
the original HTTP or response-shape failure cannot be independently recreated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction
from scripts.run_ai_heldout_pair import _run_case

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json"
LEDGER = ROOT / "evals/structured_nlu/data/ai_heldout/ai-heldout-review-ledger.v1.json"
PROTOCOL_KIND = "nlu_current_baseline_v1_development"
RESULT_KIND = "nlu_current_baseline_v1_result"
SCOPE = "exposed_ai_authored_user_adjudicated_development_only"
MODEL_SHA256 = "644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d"
IMAGE_DIGEST = "sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35"
CASE_ORDER = tuple(f"ai-heldout-ah{index:02}" for index in range(1, 33))
REQUEST = {
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
    "timeout_seconds": 180,
    "retry_policy": "one_retry_after_contract_failure",
    "cache_policy": "mixed",
    "endpoint": "http://127.0.0.1:18081/v1/chat/completions",
    "model_id": "kanana-q5",
}
RUNTIME = {
    "host_port": 18081,
    "cpu_count": 2,
    "memory_bytes": 4 * 1024**3,
    "context_tokens": 4096,
    "threads": 2,
    "parallel_slots": 1,
}
PROTOCOL_FIELDS = {
    "kind",
    "scope",
    "frozen_code_commit",
    "input_hashes",
    "source_manifest",
    "model_sha256",
    "server_image_digest",
    "request_policy",
    "local_runtime",
    "case_order",
}
RESULT_FIELDS = {"kind", "protocol_sha256", "journal_sha256", "predictions", "summary"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
ERROR = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
NON_FLOW_SOURCES = {
    "evals/structured_nlu/ai_heldout.py",
    "evals/structured_nlu/contracts.py",
    "evals/structured_nlu/metrics.py",
    "evals/structured_nlu/schema.py",
    "evals/structured_nlu/semantics.py",
    "llm/structured_output.py",
    "scripts/probe_gguf_structured_nlu.py",
    "scripts/run_ai_heldout_pair.py",
    "experiments/as_safety_v4/run.py",
    "experiments/nlu_current_baseline_v1/run.py",
    "experiments/nlu_current_baseline_v1/verify.py",
}


def _expected_source_paths() -> set[str]:
    """Reconstruct the exact prompt/analyzer/source set independently of run.py."""
    return NON_FLOW_SOURCES | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "services/flow").rglob("*.py")
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True, check=True).stdout


def _frozen(commit: str, relative: str) -> bytes:
    if not COMMIT.fullmatch(commit) or not relative or relative.startswith("/"):
        raise ValueError("frozen reference differs")
    if ".." in Path(relative).parts:
        raise ValueError("frozen reference differs")
    return _git("show", f"{commit}:{relative}")


def _strict_json(data: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def finite(_value: str) -> None:
        raise ValueError("nonfinite JSON number")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=finite)


def check_protocol(protocol_path: Path, model_path: Path) -> tuple[dict, str]:
    raw = protocol_path.read_bytes()
    protocol = _strict_json(raw)
    if type(protocol) is not dict or set(protocol) != PROTOCOL_FIELDS:
        raise ValueError("protocol fields differ")
    commit = protocol["frozen_code_commit"]
    if type(commit) is not str or not COMMIT.fullmatch(commit):
        raise ValueError("frozen commit differs")
    if (
        protocol["kind"] != PROTOCOL_KIND
        or protocol["scope"] != SCOPE
        or protocol["case_order"] != list(CASE_ORDER)
        or protocol["model_sha256"] != MODEL_SHA256
        or protocol["server_image_digest"] != IMAGE_DIGEST
        or protocol["request_policy"] != REQUEST
        or protocol["local_runtime"] != RUNTIME
        or _file_sha(model_path) != MODEL_SHA256
    ):
        raise ValueError("protocol identity differs")
    inputs = protocol["input_hashes"]
    if type(inputs) is not dict or set(inputs) != {"dataset", "review_ledger"}:
        raise ValueError("input manifest differs")
    for key, path in (("dataset", DATASET), ("review_ledger", LEDGER)):
        relative = path.relative_to(ROOT).as_posix()
        frozen = _frozen(commit, relative)
        expected = inputs[key]
        if (
            type(expected) is not str
            or not SHA.fullmatch(expected)
            or _sha(frozen) != expected
            or path.read_bytes() != frozen
        ):
            raise ValueError(f"frozen input differs: {key}")
    sources = protocol["source_manifest"]
    if type(sources) is not dict or set(sources) != _expected_source_paths():
        raise ValueError("source manifest paths differ")
    for relative, expected in sources.items():
        if type(relative) is not str or type(expected) is not str or not SHA.fullmatch(expected):
            raise ValueError("source manifest invalid")
        frozen = _frozen(commit, relative)
        if _sha(frozen) != expected or (ROOT / relative).read_bytes() != frozen:
            raise ValueError(f"frozen source differs: {relative}")
    try:
        relative_protocol = protocol_path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("protocol must be in repository") from error
    if _git("show", f"HEAD:{relative_protocol}") != raw:
        raise ValueError("protocol must be committed")
    return protocol, _sha(raw)


def _private_dir(path: Path) -> None:
    if (
        path.is_symlink()
        or not path.is_dir()
        or path.resolve().is_relative_to(ROOT)
        or stat.S_IMODE(path.stat().st_mode) != 0o700
    ):
        raise ValueError("private raw directory boundary differs")


def _replay_raw_attempts(
    case, prediction: CasePrediction, raw_attempts: object, private_dir: Path, request: dict
) -> set[str]:
    if type(raw_attempts) is not list or len(raw_attempts) != len(prediction.attempts):
        raise ValueError("raw attempt count differs")
    responses: list[tuple[str, str | None, str | None]] = []
    observed_names: set[str] = set()
    for ordinal, item in enumerate(raw_attempts, 1):
        if type(item) is not dict or set(item) != {
            "attempt",
            "status",
            "raw_sha256",
            "raw_bytes",
            "error_type",
        }:
            raise ValueError("raw attempt fields differ")
        if type(item["attempt"]) is not int or item["attempt"] != ordinal:
            raise ValueError("raw attempt order differs")
        path = private_dir / f"{case.id}-attempt{ordinal}.txt"
        if item["status"] == "received":
            digest, size = item["raw_sha256"], item["raw_bytes"]
            if (
                item["error_type"] is not None
                or type(digest) is not str
                or not SHA.fullmatch(digest)
                or type(size) is not int
                or not 0 <= size <= 1_000_000
                or path.is_symlink()
                or not path.is_file()
                or stat.S_IMODE(path.stat().st_mode) != 0o600
            ):
                raise ValueError("raw response metadata differs")
            raw = path.read_bytes()
            if len(raw) != size or _sha(raw) != digest:
                raise ValueError("private raw response differs")
            decoded = raw.decode("utf-8")
            responses.append(("received", decoded, None))
            observed_names.add(path.name)
        elif item["status"] == "transport_error":
            name = item["error_type"]
            if (
                item["raw_sha256"] is not None
                or item["raw_bytes"] is not None
                or type(name) is not str
                or not ERROR.fullmatch(name)
                or path.exists()
            ):
                raise ValueError("transport error metadata differs")
            responses.append(("transport_error", None, name))
        else:
            raise ValueError("raw attempt status differs")

    call_index = 0

    def offline_completion(_endpoint, _model_id, _messages, _policy):
        nonlocal call_index
        if call_index >= len(responses):
            raise RuntimeError("offline replay requested an unrecorded call")
        status, raw, name = responses[call_index]
        call_index += 1
        if status == "transport_error":
            assert name is not None
            raise type(name, (ValueError,), {})()
        assert raw is not None
        return raw

    replay = _run_case(
        case,
        endpoint=request["endpoint"],
        model_id=request["model_id"],
        policy=SimpleNamespace(**request),
        completion_post=offline_completion,
    )
    if call_index != len(responses) or replay.case_id != prediction.case_id:
        raise ValueError("offline replay attempt count differs")
    for actual, recorded in zip(replay.attempts, prediction.attempts, strict=True):
        if (
            actual.contract_valid != recorded.contract_valid
            or actual.output != recorded.output
            or actual.error_type != recorded.error_type
        ):
            raise ValueError("raw-to-prediction replay differs")
    return observed_names


def _check_journal(
    path: Path,
    *,
    protocol_sha: str,
    predictions: tuple[CasePrediction, ...],
    summary: dict,
    private_dir: Path,
    cases: tuple,
    request: dict,
) -> str:
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("journal incomplete")
    rows = [_strict_json(line) for line in raw.splitlines()]
    if len(rows) != 2 + 2 * len(CASE_ORDER):
        raise ValueError("journal call count differs")
    if rows[0] != {"event": "header", "protocol_sha256": protocol_sha}:
        raise ValueError("journal header differs")
    raw_names: set[str] = set()
    for index, (case_id, prediction, case) in enumerate(
        zip(CASE_ORDER, predictions, cases, strict=True)
    ):
        if rows[1 + 2 * index] != {"event": "begin", "case_id": case_id}:
            raise ValueError("journal call order differs")
        end = rows[2 + 2 * index]
        if type(end) is not dict or set(end) != {"event", "case_id", "prediction", "raw_attempts"}:
            raise ValueError("journal end fields differ")
        if (
            end["event"] != "end"
            or end["case_id"] != case_id
            or end["prediction"] != prediction.model_dump(mode="json")
        ):
            raise ValueError("journal prediction differs")
        raw_names.update(
            _replay_raw_attempts(case, prediction, end["raw_attempts"], private_dir, request)
        )
    if rows[-1] != {"event": "summary", "summary": summary}:
        raise ValueError("journal summary differs")
    if {item.name for item in private_dir.iterdir()} != raw_names:
        raise ValueError("private raw file inventory differs")
    return _sha(raw)


def verify(
    protocol_path: Path,
    result_path: Path,
    journal_path: Path,
    private_dir: Path,
    model_path: Path,
) -> dict:
    protocol, protocol_sha = check_protocol(protocol_path, model_path)
    _private_dir(private_dir)
    reviewed = load_reviewed_ai_heldout(DATASET, LEDGER)
    if tuple(case.id for case in reviewed.dataset.cases) != CASE_ORDER:
        raise ValueError("reviewed case order differs")
    raw = result_path.read_bytes()
    result = _strict_json(raw)
    if type(result) is not dict or set(result) != RESULT_FIELDS:
        raise ValueError("result fields differ")
    if result["kind"] != RESULT_KIND or result["protocol_sha256"] != protocol_sha:
        raise ValueError("result identity differs")
    items = result["predictions"]
    if type(items) is not list or len(items) != len(CASE_ORDER):
        raise ValueError("prediction count differs")
    predictions = tuple(CasePrediction.model_validate(item) for item in items)
    if tuple(prediction.case_id for prediction in predictions) != CASE_ORDER:
        raise ValueError("prediction order differs")
    for prediction in predictions:
        for attempt in prediction.attempts:
            if attempt.error_type is not None and not ERROR.fullmatch(attempt.error_type):
                raise ValueError("unbounded error detail in public result")
    summary = score_predictions(reviewed.dataset.cases, predictions).to_dict()
    if result["summary"] != summary:
        raise ValueError("result summary differs")
    journal_sha = _check_journal(
        journal_path,
        protocol_sha=protocol_sha,
        predictions=predictions,
        summary=summary,
        private_dir=private_dir,
        cases=reviewed.dataset.cases,
        request=protocol["request_policy"],
    )
    if result["journal_sha256"] != journal_sha:
        raise ValueError("journal digest differs")
    return {
        "protocol_sha256": protocol_sha,
        "journal_sha256": journal_sha,
        "result_sha256": _sha(raw),
        "case_count": len(predictions),
        "summary": summary,
        "claim_scope": SCOPE,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.protocol, args.result, args.journal, args.private_dir, args.model_path),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
