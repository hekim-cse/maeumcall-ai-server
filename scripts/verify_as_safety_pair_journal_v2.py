"""Audit paired-call exposure order and completion independently of the runner."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROUTES = {"safety_action_required", "confirming_safety_status", "collecting_service_request"}
STAGES = {"response", "contract", "route"}


def verify_journal(path: Path, case_ids: list[str], protocol_sha256: str) -> dict:
    """Reject a partial or malformed log before anyone computes performance."""
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if not events or events[0] != {"event": "header", "protocol_sha256": protocol_sha256}:
        raise ValueError("journal protocol header differs")
    if len(set(case_ids)) != len(case_ids) or len(events) != 1 + 4 * len(case_ids):
        raise ValueError("journal has incomplete or duplicate calls")
    errors = {stage: 0 for stage in STAGES}
    for index, case_id in enumerate(case_ids):
        order = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        for position, arm in enumerate(order):
            begin = events[1 + index * 4 + position * 2]
            end = events[2 + index * 4 + position * 2]
            if begin != {"event": "begin", "case_id": case_id, "arm": arm}:
                raise ValueError("journal call order differs")
            if (
                not isinstance(end, dict)
                or set(end)
                != {
                    "event",
                    "case_id",
                    "arm",
                    "decision",
                    "route",
                    "error_stage",
                    "error_type",
                    "finish_reason",
                    "latency_ms",
                }
                or (end["event"], end["case_id"], end["arm"]) != ("end", case_id, arm)
            ):
                raise ValueError("journal end fields differ")
            latency = end["latency_ms"]
            if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
                raise ValueError("journal latency differs")
            stage = end["error_stage"]
            if stage is None:
                if end["error_type"] is not None or end["finish_reason"] != "stop":
                    raise ValueError("successful call metadata differs")
                if not isinstance(end["decision"], dict) or end["route"] not in ROUTES:
                    raise ValueError("successful call decision differs")
            else:
                if stage not in STAGES or not isinstance(end["error_type"], str):
                    raise ValueError("error category differs")
                if len(end["error_type"]) > 80 or end["route"] is not None:
                    raise ValueError("error detail or route differs")
                if stage != "route" and end["decision"] is not None:
                    raise ValueError("failed call has decision")
                if end["finish_reason"] not in (None, "stop", "length"):
                    raise ValueError("invalid finish reason")
                errors[stage] += 1
    return {"cases": len(case_ids), "arm_calls": 2 * len(case_ids), "errors_by_stage": errors}
