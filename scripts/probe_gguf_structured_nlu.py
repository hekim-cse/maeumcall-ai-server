"""Explore the 16 detailed NLU development drafts with a local GGUF server.

This is not the adjudicated benchmark. The saved report contains no prompt or
completion text. The live analyzers still validate every model response.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from llm.errors import AIResponseValidationError
from scripts.probe_chat_latency import CORPUS, select_cases

DIRECT_ANALYZERS = {
    "예약:병원 예약": (
        "services.flow.reservation.hospital.llm_structured",
        "analyze_hospital_reservation_user_message",
        True,
    ),
    "예약:식당 예약": (
        "services.flow.reservation.restaurant.llm_structured",
        "analyze_restaurant_reservation_user_message",
        True,
    ),
    "예약:미용실 예약": (
        "services.flow.reservation.hair_salon.llm_structured",
        "analyze_hair_salon_reservation_user_message",
        True,
    ),
    "예약:스터디룸 예약": (
        "services.flow.reservation.study_room.llm_structured",
        "analyze_study_room_reservation_user_message",
        True,
    ),
    "교수님:면담 예약": (
        "services.flow.professor.appointment.llm_structured",
        "analyze_professor_appointment_user_message",
        False,
    ),
    "교수님:과제 문의": (
        "services.flow.professor.assignment.llm_structured",
        "analyze_professor_assignment_user_message",
        False,
    ),
    "교수님:결석 사유 전달": (
        "services.flow.professor.absence.llm_structured",
        "analyze_professor_absence_user_message",
        False,
    ),
}


def draft_mismatches(case: dict, normalized: dict) -> list[str]:
    labels = case["labels"]
    mismatched = [
        name
        for name in ("intent", "user_action", "change_field")
        if normalized.get(name) != labels[name]
    ]
    fields = normalized.get("fields")
    if fields is None:
        fields = {name: normalized.get(name) for name in labels["fields"]}
    for name, expected in labels["fields"].items():
        value = fields[name]
        if expected is None:
            if value is not None:
                mismatched.append(name)
        elif value not in expected["accepted_values"]:
            mismatched.append(name)
    return sorted(mismatched)


def run_case(case: dict, *, endpoint: str, model: str, timeout: int) -> dict:
    attempts: list[dict] = []

    def completion(messages: list[dict[str, str]]) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 180,
            "temperature": 0,
            "repeat_penalty": 1.05,
            "stop": ["<|eot_id|>"],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
        usage = body.get("usage", {})
        attempts.append(
            {
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "prompt_tokens": usage.get("prompt_tokens"),
                "cached_prompt_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "finish_reason": body["choices"][0].get("finish_reason"),
            }
        )
        return body["choices"][0]["message"]["content"]

    contract = EVALUATION_CONTRACTS[case["scenario_key"]]
    if contract.workflow_spec is not None:
        module = importlib.import_module("services.flow.service_workflow.structured")

        def analyze():
            return module.analyze_service_workflow_message(
                contract.workflow_spec,
                conversation_state=case["conversation_state"],
                current_fields={
                    name: case["current_fields"].get(name) for name in contract.field_names
                },
                user_message=case["user_message"],
            )

    else:
        module_name, function_name, uses_alternatives = DIRECT_ANALYZERS[case["scenario_key"]]
        module = importlib.import_module(module_name)

        def analyze():
            args = [case["conversation_state"], case["user_message"]]
            if uses_alternatives:
                args.append(case["offered_alternative_times"])
            return getattr(module, function_name)(*args)

    started = time.perf_counter()
    with patch.object(module, "complete_hf_json", completion):
        try:
            normalized = analyze()
        except AIResponseValidationError:
            return {
                "case_id": case["id"],
                "scenario_key": case["scenario_key"],
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "contract_valid": False,
                "attempts": attempts,
            }
    return {
        "case_id": case["id"],
        "scenario_key": case["scenario_key"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "contract_valid": True,
        "draft_label_mismatch_fields": draft_mismatches(case, normalized),
        "attempts": attempts,
    }


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

    corpus_bytes = CORPUS.read_bytes()
    cases = select_cases(json.loads(corpus_bytes), [], False)
    observations = []
    for index, case in enumerate(cases, start=1):
        observation = run_case(case, endpoint=args.endpoint, model=args.model, timeout=args.timeout)
        observations.append(observation)
        print(
            f"{index}/{len(cases)} case={case['id']} "
            f"contract_valid={observation['contract_valid']} "
            f"elapsed={observation['elapsed_seconds']:.3f}s",
            flush=True,
        )
    report = {
        "kind": "exploratory_gguf_structured_nlu_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "probe_runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
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
        "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"cases={len(cases)} contract_valid={sum(item['contract_valid'] for item in observations)} "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
