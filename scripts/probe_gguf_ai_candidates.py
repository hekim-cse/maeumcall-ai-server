"""Probe the 36 unreviewed portfolio suggestions against the live NLU contracts.

The report saves no user utterance or model completion text. Draft-label matches
are diagnostic only and are not an accuracy or portfolio improvement score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from scripts.probe_chat_latency import CORPUS
from scripts.probe_gguf_structured_nlu import run_case

CANDIDATES = Path(__file__).resolve().parents[1] / "docs/portfolio/heldout_nlu_ai_candidates.md"
ROW = re.compile(r"^\| (C\d\d) \|")
CODE_SPAN = re.compile(r"`([^`]+)`")


def load_draft_cases() -> tuple[list[dict], bytes, bytes]:
    candidate_bytes = CANDIDATES.read_bytes()
    corpus_bytes = CORPUS.read_bytes()
    reference_cases = json.loads(corpus_bytes)["cases"]
    drafts = []
    for line in candidate_bytes.decode().splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        candidate_id = cells[1]
        scenario_key, kind = cells[2].split(" · ")
        spans = CODE_SPAN.findall(cells[4])
        action = spans[0]
        template_kind = {
            "정보 제공": "human-information-provision",
            "어려운 발화": "human-hard-negative",
            "후속 정보": "human-followup-information-provision",
        }[kind]
        reference = next(
            case
            for case in reference_cases
            if case["scenario_key"] == scenario_key and template_kind in case["id"]
        )
        contract = EVALUATION_CONTRACTS[scenario_key]
        fields = dict.fromkeys(contract.field_names)
        for span in spans[1:]:
            if "=" not in span:
                continue
            name, value = span.split("=", 1)
            if name not in fields:
                raise ValueError(f"unknown suggested field: {candidate_id} {name}")
            fields[name] = value
        contract.validate_prediction(
            intent=reference["labels"]["intent"],
            fields=fields,
            user_action=action,
            change_field=None,
            conversation_state=reference["conversation_state"],
            current_fields=reference["current_fields"],
            offered_alternative_times=tuple(reference["offered_alternative_times"]),
        )
        drafts.append(
            {
                "id": candidate_id,
                "scenario_key": scenario_key,
                "conversation_state": reference["conversation_state"],
                "current_fields": reference["current_fields"],
                "offered_alternative_times": reference["offered_alternative_times"],
                "user_message": cells[3],
                "labels": {
                    "intent": reference["labels"]["intent"],
                    "user_action": action,
                    "change_field": None,
                    "fields": {
                        name: None if value is None else {"accepted_values": [value]}
                        for name, value in fields.items()
                    },
                },
            }
        )
    if [case["id"] for case in drafts] != [f"C{index:02d}" for index in range(1, 37)]:
        raise ValueError("expected exactly C01-C36 in order")
    return drafts, candidate_bytes, corpus_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--case-ids", nargs="*", default=None)
    args = parser.parse_args()
    if args.timeout < 1 or args.output.exists():
        parser.error("timeout must be positive and output must not already exist")

    cases, candidate_bytes, corpus_bytes = load_draft_cases()
    if args.case_ids is not None:
        selected = set(args.case_ids)
        known = {case["id"] for case in cases}
        if not selected or selected - known:
            parser.error(f"case-ids must be nonempty known IDs: {sorted(selected - known)}")
        cases = [case for case in cases if case["id"] in selected]
    observations = []
    try:
        for index, case in enumerate(cases, start=1):
            observation = run_case(
                case, endpoint=args.endpoint, model=args.model, timeout=args.timeout
            )
            observations.append(observation)
            print(
                f"{index}/{len(cases)} case={case['id']} "
                f"contract_valid={observation['contract_valid']} "
                f"draft_mismatch={observation.get('draft_label_mismatch_fields')}",
                flush=True,
            )
    finally:
        report = {
            "kind": "exploratory_gguf_ai_candidate_probe_v1",
            "candidate_status": "ai_assisted_unreviewed",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "candidate_source_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
            "reference_corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
            "model": args.model,
            "model_sha256": args.model_sha256,
            "server_image_digest": args.server_image_digest,
            "request_settings": {
                "max_tokens": 180,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
            },
            "case_count": len(cases),
            "selected_case_ids": [case["id"] for case in cases],
            "observations": observations,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
