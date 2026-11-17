"""Audit frozen dual-query requests and saved responses without model calls.

Only aggregate counts leave this process. Reconstructed requests are not proof
of the exact HTTP bytes received by the server, which were not captured.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.as_safety_dual_query_v1.contract import decision_messages, decision_schema
from experiments.as_safety_dual_query_v1.verify import verify
from experiments.as_safety_v2.transport import MODEL_ID
from experiments.as_safety_v4.cases import load_cases
from experiments.as_safety_v4.run import INPUTS


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request_bytes(case: dict, gold: dict, arm: str, policy: dict) -> bytes:
    """Mirror the frozen transport's JSON payload construction, in memory."""
    payload = {
        "model": MODEL_ID,
        "messages": decision_messages(case, gold, arm),
        "max_tokens": policy["max_tokens"],
        "temperature": policy["temperature"],
        "repeat_penalty": policy["repeat_penalty"],
        "stop": policy["stop"],
        "seed": policy["seed"],
        "response_format": {"type": "json_object", "schema": decision_schema()},
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")


def audit(protocol_path: Path, journal_path: Path, private_dir: Path, model_path: Path) -> dict:
    """Verify saved evidence first, then count request and response contrasts."""
    checked = verify(protocol_path, journal_path, private_dir, model_path=model_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cases = load_cases(INPUTS["dataset"])
    by_case = {case["id"]: case for case in cases}
    ends = {
        (row["event_id"], row["arm"]): row["stage"]
        for row in (
            json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()
        )
        if row["event"] == "end"
    }
    request_hashes: set[str] = set()
    request_same = 0
    system_different = 0
    user_same = 0
    response_same = 0
    missing_response_pairs = 0
    by_gold_and_answers: Counter[tuple[str, str | None, str | None]] = Counter()
    for event_id in protocol["event_order"]:
        case_id, index = event_id.rsplit("-", 1)
        case = by_case[case_id]
        gold = case["events"][int(index) - 1]
        current = _request_bytes(case, gold, "current", protocol["request_policy"])
        distinct = _request_bytes(case, gold, "distinct", protocol["request_policy"])
        request_hashes.update((_sha(current), _sha(distinct)))
        request_same += current == distinct
        current_messages = json.loads(current)["messages"]
        distinct_messages = json.loads(distinct)["messages"]
        system_different += current_messages[0] != distinct_messages[0]
        user_same += current_messages[1] == distinct_messages[1]
        current_stage = ends[(event_id, "current")]
        distinct_stage = ends[(event_id, "distinct")]
        current_raw = current_stage["raw_sha256"]
        distinct_raw = distinct_stage["raw_sha256"]
        if current_raw is None or distinct_raw is None:
            missing_response_pairs += 1
        else:
            response_same += current_raw == distinct_raw
        category = f"{gold['occurrence']}_{gold['owner_to_target']}"
        by_gold_and_answers[(category, current_stage["decision"], distinct_stage["decision"])] += 1
    return {
        "scope": "exposed_owner_oracle_offline_diagnostic_not_accuracy",
        "protocol_sha256": checked["protocol_sha256"],
        "journal_sha256": checked["journal_sha256"],
        "saved_raw_count": checked["private_raw_count"],
        "eligible_events": len(protocol["event_order"]),
        "reconstructed_request_count": 2 * len(protocol["event_order"]),
        "unique_reconstructed_requests": len(request_hashes),
        "same_request_pairs": request_same,
        "different_system_question_pairs": system_different,
        "same_user_input_pairs": user_same,
        "same_raw_response_pairs": response_same,
        "pairs_with_missing_raw_response": missing_response_pairs,
        "gold_category_and_decisions": [
            {
                "category": category,
                "current_question": current_answer,
                "distinct_question": distinct_answer,
                "count": count,
            }
            for (category, current_answer, distinct_answer), count in sorted(
                by_gold_and_answers.items(),
                key=lambda item: (
                    item[0][0],
                    item[0][1] if item[0][1] is not None else "",
                    item[0][2] if item[0][2] is not None else "",
                ),
            )
        ],
        "wire_request_captured": False,
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
            audit(args.protocol, args.journal, args.private_dir, args.model_path),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
