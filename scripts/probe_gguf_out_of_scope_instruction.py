"""Compare an out-of-scope instruction on unreviewed development suggestions.

This local probe saves no utterance or completion text. Draft-label agreement
is diagnostic only; the selected cases have already been exposed to the model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from scripts.probe_gguf_ai_candidates import load_draft_cases
from scripts.probe_gguf_structured_nlu import run_case

INSTRUCTION = (
    "사용자 발화가 현재 전화 시뮬레이션의 업무 범위 밖이라면, 다른 업무의 정보가 "
    "구체적으로 언급돼도 현재 업무의 필드로 옮기지 마세요. 이 경우 현재 허용된 "
    "user_action에 unknown이 있다면 unknown을 선택하고 이번 턴 필드는 모두 null로 "
    "두세요. 현재 업무에 관한 새 정보가 실제로 있을 때만 정보 제공 행동을 선택하세요."
)
CASE_IDS = ("C05", "C06", "C07", "C08", "C11", "C12", "C15", "C16", "C19", "C20")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.timeout < 1 or args.output.exists():
        parser.error("timeout must be positive and output must not already exist")

    all_cases, candidate_bytes, corpus_bytes = load_draft_cases()
    cases_by_id = {case["id"]: case for case in all_cases}
    cases = [cases_by_id[case_id] for case_id in CASE_IDS]
    original_urlopen = urllib.request.urlopen
    active_mode = "baseline"

    def urlopen_with_optional_instruction(request, *, timeout):
        if active_mode == "variant":
            payload = json.loads(request.data)
            messages = payload["messages"]
            if messages[0]["role"] != "system":
                raise ValueError("out-of-scope instruction requires a system message")
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
        for index, case in enumerate(cases):
            modes = ("baseline", "variant") if index % 2 == 0 else ("variant", "baseline")
            for mode in modes:
                active_mode = mode
                result = run_case(
                    case, endpoint=args.endpoint, model=args.model, timeout=args.timeout
                )
                observations.append({"mode": mode, **result})
                print(
                    f"mode={mode} case={case['id']} valid={result['contract_valid']} "
                    f"mismatch={result.get('draft_label_mismatch_fields')}",
                    flush=True,
                )
    finally:
        urllib.request.urlopen = original_urlopen
        report = {
            "kind": "exploratory_gguf_out_of_scope_instruction_v1",
            "candidate_status": "ai_assisted_unreviewed",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases) * 2,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "candidate_source_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
            "reference_corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "model": args.model,
            "model_sha256": args.model_sha256,
            "server_image_digest": args.server_image_digest,
            "instruction": INSTRUCTION,
            "case_ids": CASE_IDS,
            "observations": observations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
