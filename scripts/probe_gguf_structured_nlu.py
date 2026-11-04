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
from llm.structured_output import StructuredKeyError, complete_validated_json
from scripts.gguf_action_field_split import action_messages, validate_action_choice
from scripts.gguf_service_workflow_schema import (
    workflow_action_schema,
    workflow_response_schema,
    workflow_schema_for_selected_action,
)
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


def safe_failure_code(cause: BaseException | None) -> str | None:
    """Classify known validator failures without saving model text or values."""
    if cause is None:
        return None
    if isinstance(cause, StructuredKeyError):
        return "schema_keys_mismatch"
    message = str(cause)
    if "user_action must be one of" in message:
        return "action_not_allowed_for_state"
    if "intent must be" in message:
        return "intent_not_allowed"
    if "must not include current-turn fields" in message:
        return "action_has_forbidden_fields"
    if "requires at least one current-turn field" in message:
        return "action_missing_required_field"
    if "requires current-turn fields" in message:
        return "action_missing_required_field"
    if "change_field must be null" in message:
        return "unexpected_change_field"
    if "must be one of" in message:
        return "field_value_not_allowed"
    return "other_validation_failure"


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


def safe_output_shape(raw: str, *, field_names: tuple[str, ...], actions: frozenset[str]) -> dict:
    """Retain only whitelisted action and field names, never generated values."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"json_object": False}
    if not isinstance(parsed, dict):
        return {"json_object": False}
    action = parsed.get("user_action")
    fields = parsed.get("fields")
    if not isinstance(fields, dict):
        fields = parsed
    return {
        "json_object": True,
        "user_action": action if isinstance(action, str) and action in actions else "__other__",
        "present_field_names": sorted(name for name in field_names if fields.get(name) is not None),
        "change_field": (
            parsed.get("change_field")
            if parsed.get("change_field") in field_names
            else None
            if parsed.get("change_field") is None
            else "__other__"
        ),
    }


def run_case(
    case: dict,
    *,
    endpoint: str,
    model: str,
    timeout: int,
    capture_shape: bool = False,
    constrain_workflow: bool = False,
    schema_format: str = "json_schema",
    split_workflow: bool = False,
) -> dict:
    attempts: list[dict] = []
    contract = EVALUATION_CONTRACTS[case["scenario_key"]]
    if split_workflow and (not constrain_workflow or contract.workflow_spec is None):
        raise ValueError("split workflow requires a constrained service-workflow case")
    if split_workflow and schema_format != "json_object":
        raise ValueError("split workflow requires the observed json_object schema format")
    if constrain_workflow:
        if schema_format not in {"json_schema", "json_object"}:
            raise ValueError("unsupported schema format")
        if contract.workflow_spec is None:
            raise ValueError("workflow schema is available only for service-workflow cases")
        response_schema = workflow_response_schema(
            contract.workflow_spec,
            conversation_state=case["conversation_state"],
            current_fields=case["current_fields"],
        )
    else:
        response_schema = None
    stage = "action" if split_workflow else "single"

    def completion(messages: list[dict[str, str]]) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 180,
            "temperature": 0,
            "repeat_penalty": 1.05,
            "stop": ["<|eot_id|>"],
        }
        if response_schema is not None:
            payload["response_format"] = {"type": schema_format, "schema": response_schema}
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
        attempt = {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "prompt_tokens": usage.get("prompt_tokens"),
            "cached_prompt_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "finish_reason": body["choices"][0].get("finish_reason"),
        }
        if split_workflow:
            attempt["stage"] = stage
        raw = body["choices"][0]["message"]["content"]
        if capture_shape:
            attempt["output_shape"] = safe_output_shape(
                raw, field_names=contract.field_names, actions=contract.user_actions
            )
        attempts.append(attempt)
        return raw

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
    selected_action: dict[str, str | None] | None = None
    try:
        if split_workflow:
            spec = contract.workflow_spec
            workflow_fields = {
                name: case["current_fields"].get(name) for name in contract.field_names
            }
            response_schema = workflow_action_schema(
                spec,
                conversation_state=case["conversation_state"],
                current_fields=workflow_fields,
            )
            selected_action = complete_validated_json(
                action_messages(
                    spec,
                    conversation_state=case["conversation_state"],
                    current_fields=workflow_fields,
                    user_message=case["user_message"],
                ),
                completion=completion,
                validator=lambda parsed: validate_action_choice(
                    parsed,
                    spec=spec,
                    conversation_state=case["conversation_state"],
                    current_fields=workflow_fields,
                ),
                operation=f"{spec.graph_name}_action_probe",
            )
            response_schema = workflow_schema_for_selected_action(
                spec,
                conversation_state=case["conversation_state"],
                current_fields=workflow_fields,
                user_action=selected_action["user_action"],
                change_field=selected_action["change_field"],
            )
            stage = "fields"
        with patch.object(module, "complete_hf_json", completion):
            normalized = analyze()
    except AIResponseValidationError as exc:
        cause = exc.__cause__
        failure = {
            "last_error_type": type(cause).__name__ if cause else None,
            "last_error_code": safe_failure_code(cause),
        }
        if isinstance(cause, StructuredKeyError):
            failure["missing_output_keys"] = sorted(cause.missing)
            failure["unexpected_output_key_count"] = len(cause.unexpected)
        return {
            "case_id": case["id"],
            "scenario_key": case["scenario_key"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "contract_valid": False,
            "failure": failure,
            "selected_action": selected_action,
            "first_stage_action_draft_match": (
                selected_action["user_action"] == case["labels"]["user_action"]
                and selected_action["change_field"] == case["labels"]["change_field"]
                if selected_action is not None
                else None
            ),
            "attempts": attempts,
        }
    if selected_action is not None and (
        normalized["user_action"] != selected_action["user_action"]
        or normalized["change_field"] != selected_action["change_field"]
    ):
        return {
            "case_id": case["id"],
            "scenario_key": case["scenario_key"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "contract_valid": False,
            "failure": {
                "last_error_type": "ValueError",
                "last_error_code": "stage_action_mismatch",
            },
            "selected_action": selected_action,
            "first_stage_action_draft_match": (
                selected_action["user_action"] == case["labels"]["user_action"]
                and selected_action["change_field"] == case["labels"]["change_field"]
            ),
            "attempts": attempts,
        }
    mismatch_fields = draft_mismatches(case, normalized)
    return {
        "case_id": case["id"],
        "scenario_key": case["scenario_key"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "contract_valid": True,
        "draft_label_mismatch_fields": mismatch_fields,
        "action_draft_match": not {"user_action", "change_field"} & set(mismatch_fields),
        "field_draft_match": not (set(mismatch_fields) - {"intent", "user_action", "change_field"}),
        "selected_action": selected_action,
        "first_stage_action_draft_match": (
            selected_action["user_action"] == case["labels"]["user_action"]
            and selected_action["change_field"] == case["labels"]["change_field"]
            if selected_action is not None
            else None
        ),
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
    try:
        for index, case in enumerate(cases, start=1):
            observation = run_case(
                case, endpoint=args.endpoint, model=args.model, timeout=args.timeout
            )
            observations.append(observation)
            print(
                f"{index}/{len(cases)} case={case['id']} "
                f"contract_valid={observation['contract_valid']} "
                f"elapsed={observation['elapsed_seconds']:.3f}s",
                flush=True,
            )
    finally:
        report = {
            "kind": "exploratory_gguf_structured_nlu_v1",
            "not_official_quality_score": True,
            "complete": len(observations) == len(cases),
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
