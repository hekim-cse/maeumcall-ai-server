"""Compare a time-fidelity instruction on four development draft cases.

This local-only exploratory probe keeps live validators and saves no model text.
It does not modify service prompts or produce an official benchmark score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from scripts.probe_chat_latency import CORPUS
from scripts.probe_gguf_structured_nlu import run_case

INSTRUCTION = (
    "시간 값은 사용자가 말한 시간 표현만 보존하세요. 사용자가 오전·오후·저녁을 "
    "말하지 않았다면 시간대를 추가하거나 24시간제로 변환하지 마세요. "
    "예를 들어 '5시'라고만 말했다면 '5시'로 반환하세요."
)
CASE_IDS = (
    "professor-appointment-human-information-provision-001.c1",
    "reservation-hair-salon-human-information-provision-001.c1",
    "reservation-hospital-human-information-provision-001.c1",
    "reservation-study-room-human-information-provision-001.c1",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout < 1 or args.output.exists():
        parser.error("repeats/timeout must be positive and output must not exist")

    corpus_bytes = CORPUS.read_bytes()
    cases_by_id = {case["id"]: case for case in json.loads(corpus_bytes)["cases"]}
    cases = [cases_by_id[case_id] for case_id in CASE_IDS]
    original_urlopen = urllib.request.urlopen
    active_mode = "baseline"

    def urlopen_with_optional_instruction(request, *, timeout):
        if active_mode == "variant":
            payload = json.loads(request.data)
            messages = payload["messages"]
            if messages[0]["role"] != "system":
                raise ValueError("time instruction requires a system message")
            messages[0]["content"] += "\n" + INSTRUCTION
            request = urllib.request.Request(
                request.full_url,
                data=json.dumps(payload, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        return original_urlopen(request, timeout=timeout)

    urllib.request.urlopen = urlopen_with_optional_instruction
    observations = []
    try:
        for repeat in range(args.repeats):
            for case in cases:
                for mode in ("baseline", "variant") if repeat % 2 == 0 else ("variant", "baseline"):
                    active_mode = mode
                    result = run_case(
                        case,
                        endpoint=args.endpoint,
                        model=args.model,
                        timeout=args.timeout,
                    )
                    observations.append({"repeat": repeat + 1, "mode": mode, **result})
                    print(
                        f"repeat={repeat + 1} mode={mode} case={case['id']} "
                        f"valid={result['contract_valid']} "
                        f"mismatch={result.get('draft_label_mismatch_fields')}",
                        flush=True,
                    )
    finally:
        urllib.request.urlopen = original_urlopen
        report = {
            "kind": "exploratory_gguf_time_instruction_v1",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases) * args.repeats * 2,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "model_sha256": args.model_sha256,
            "server_image_digest": args.server_image_digest,
            "instruction": INSTRUCTION,
            "case_ids": CASE_IDS,
            "repeats": args.repeats,
            "observations": observations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
