"""Verify and rescore the v19 journal from private model responses."""

import json
import stat

from experiments import as_safety_atomic_edges_v19 as run
from experiments.as_safety_v2.json_contract import ValidationError


def replay():
    _, calls = run.baseline.calls()
    protocol_bytes = run.PROTOCOL.read_bytes()
    frozen = json.loads(protocol_bytes)
    if frozen != run.manifest(frozen["frozen_code_commit"], calls):
        raise ValueError("comparison protocol differs")
    header, *rows = map(json.loads, run.JOURNAL.read_text(encoding="utf-8").splitlines())
    if header["protocol_sha256"] != run.v12._sha(protocol_bytes):
        raise ValueError("journal protocol differs")
    if [row["call"] for row in rows] != list(calls)[: len(rows)]:
        raise ValueError("journal call order differs")
    if not rows or any(row["error"] for row in rows[:-1]):
        raise ValueError("invalid journal after execution failure")
    if len(rows) < len(calls) and rows[-1]["error"] is None:
        raise ValueError("journal ended without a recorded error")
    if run.PRIVATE_DIR.is_symlink() or stat.S_IMODE(run.PRIVATE_DIR.stat().st_mode) != 0o700:
        raise ValueError("private response directory differs")
    gold = {row["call"]: row for row in json.loads(run.baseline.LABELS.read_bytes())["cases"]}
    for row in rows:
        name = row["call"]
        pair, _, _, body = calls[name]
        if row["request_sha256"] != run.v12._sha(body):
            raise ValueError(f"request differs: {name}")
        result = None
        if "raw_sha256" in row:
            path = run.PRIVATE_DIR / f"{name}.json.txt"
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise ValueError(f"raw response mode differs: {name}")
            raw = path.read_bytes()
            if (run.v12._sha(raw), len(raw)) != (row["raw_sha256"], row["raw_bytes"]):
                raise ValueError(f"raw response differs: {name}")
            error = "finish_length" if row["finish_reason"] != "stop" else None
            if error is None:
                try:
                    result = run.baseline.selection.validate_response(raw.decode(), pair)
                except ValidationError as exc:
                    error = exc.code
            if row["error"] != error:
                raise ValueError(f"contract error differs: {name}")
        elif row["error"] is None or "http_status" not in row:
            raise ValueError(f"missing completion or transport error: {name}")
        score = run.baseline.selection.score(pair, gold[name.rsplit("-", 1)[0]], result)
        blank = (
            None if result is None else all(item is None for item in result["evidence"].values())
        )
        if (
            any(row[key] != value for key, value in score.items())
            or row["all_evidence_blank"] != blank
        ):
            raise ValueError(f"score differs: {name}")
    return rows


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
