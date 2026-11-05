"""Run a committed AI-authored heldout pair against loopback GGUF servers.

Run only after human adjudication and a committed exposure preflight. Output
contains normalized fields and bounded telemetry, never prompts/completions.
Docker runtime claims are checked against supplied metadata, not attested by
this script; independently verify the running container before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from evals.structured_nlu.ai_heldout import (
    AIHeldoutCase,
    AIHeldoutPredictionArtifact,
    AIHeldoutRequestPolicy,
    verify_ai_heldout_exposure_preflight,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt, NormalizedPrediction
from llm.errors import AIResponseValidationError
from llm.structured_output import complete_validated_json
from scripts.probe_gguf_structured_nlu import DIRECT_ANALYZERS

ROOT = Path(__file__).resolve().parents[1]
PROMPT_SOURCES = (
    "evals/structured_nlu/ai_heldout.py",
    "evals/structured_nlu/contracts.py",
    "evals/structured_nlu/metrics.py",
    "evals/structured_nlu/schema.py",
    "evals/structured_nlu/semantics.py",
    "llm/structured_output.py",
    "services/flow/common/state_contract.py",
    "services/flow/service_workflow/structured.py",
    "services/flow/service_workflow/contracts.py",
    "services/flow/service_workflow/structured_contract.py",
    "services/flow/reservation/common/structured_contract.py",
    "services/flow/support/contracts.py",
    "services/flow/delivery/contracts.py",
    "services/flow/cityhall/contracts.py",
    "scripts/probe_gguf_structured_nlu.py",
    *(f"{module.replace('.', '/')}.py" for module, _name, _alt in DIRECT_ANALYZERS.values()),
)


def prompt_revision_sha256() -> str:
    """Hash the live analyzer and contract sources that shape request prompts."""
    digest = hashlib.sha256()
    for relative in sorted(set(PROMPT_SOURCES)):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update((ROOT / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _loopback_endpoint(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is None
        or parsed.path != "/v1/chat/completions"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("AI heldout endpoint must be a loopback OpenAI-compatible URL")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise ValueError("model endpoint redirects are not allowed")


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _post_completion(
    endpoint: str, model_id: str, messages: list[dict[str, str]], policy: AIHeldoutRequestPolicy
) -> str:
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": policy.max_tokens,
        "temperature": policy.temperature,
        "repeat_penalty": policy.repeat_penalty,
        "stop": list(policy.stop),
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _OPENER.open(request, timeout=policy.timeout_seconds) as response:
        body = json.load(response)
    raw = body["choices"][0]["message"]["content"]
    if not isinstance(raw, str):
        raise ValueError("model completion must be text")
    return raw


def _normalize_output(case: AIHeldoutCase, normalized: dict) -> NormalizedPrediction:
    contract = EVALUATION_CONTRACTS[case.scenario_key]
    fields = normalized.get("fields")
    if fields is None:
        fields = {name: normalized.get(name) for name in contract.field_names}
    output = NormalizedPrediction(
        intent=normalized.get("intent"),
        fields=fields,
        user_action=normalized["user_action"],
        change_field=normalized.get("change_field"),
    )
    contract.validate_prediction(
        intent=output.intent,
        fields=output.fields,
        user_action=output.user_action,
        change_field=output.change_field,
        conversation_state=case.conversation_state,
        current_fields=case.current_fields,
        offered_alternative_times=case.offered_alternative_times,
    )
    return output


def _run_case(
    case: AIHeldoutCase,
    *,
    endpoint: str,
    model_id: str,
    policy: AIHeldoutRequestPolicy,
    completion_post: Callable[
        [str, str, list[dict[str, str]], AIHeldoutRequestPolicy], str
    ] = _post_completion,
) -> CasePrediction:
    """Use the live analyzer, preserving every validation attempt's outcome."""
    if EVALUATION_CONTRACTS[case.scenario_key].workflow_spec is not None:
        module = importlib.import_module("services.flow.service_workflow.structured")

        def analyze():
            return module.analyze_service_workflow_message(
                EVALUATION_CONTRACTS[case.scenario_key].workflow_spec,
                conversation_state=case.conversation_state,
                current_fields=case.current_fields,
                user_message=case.user_message,
            )

    else:
        module_name, function_name, uses_alternatives = DIRECT_ANALYZERS[case.scenario_key]
        module = importlib.import_module(module_name)

        def analyze():
            args = [case.conversation_state, case.user_message]
            if uses_alternatives:
                args.append(list(case.offered_alternative_times))
            return getattr(module, function_name)(*args)

    attempts: list[dict] = []
    original_complete = complete_validated_json

    def complete_wrapper(messages, *, completion, validator, operation, max_attempts=2):
        if max_attempts != 2:
            raise ValueError("live analyzer retry policy differs from frozen request policy")

        def completion_wrapper(current_messages):
            started = time.perf_counter()
            outcome = {"latency_ms": 0.0, "raw": "", "output": None, "error_type": None}
            try:
                outcome["raw"] = completion_post(endpoint, model_id, current_messages, policy)
            except (
                urllib.error.URLError,
                TimeoutError,
                OSError,
                ValueError,
                KeyError,
                IndexError,
            ) as error:
                # Treat transport and response-shape failures as invalid attempts,
                # allowing the live validator's single retry policy to apply.
                outcome["error_type"] = type(error).__name__
            finally:
                outcome["latency_ms"] = max(0.0, (time.perf_counter() - started) * 1000)
                attempts.append(outcome)
            return outcome["raw"]

        def validator_wrapper(parsed):
            outcome = attempts[-1]
            try:
                normalized = validator(parsed)
                outcome["output"] = _normalize_output(case, normalized)
                return normalized
            except (TypeError, ValueError) as error:
                outcome["error_type"] = type(error).__name__
                raise

        return original_complete(
            messages,
            completion=completion_wrapper,
            validator=validator_wrapper,
            operation=operation,
            max_attempts=max_attempts,
        )

    try:
        with patch.object(module, "complete_validated_json", complete_wrapper):
            analyze()
    except AIResponseValidationError:
        pass
    if not attempts:
        raise RuntimeError("live analyzer made no model request")
    normalized_attempts = []
    for attempt in attempts:
        output = attempt["output"]
        error_type = attempt["error_type"]
        if output is None and error_type is None:
            raw = attempt["raw"]
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                error_type = "JSONDecodeError"
            else:
                error_type = "InvalidJSONShape"
        normalized_attempts.append(
            EvaluationAttempt(
                contract_valid=output is not None,
                latency_ms=round(attempt["latency_ms"], 3),
                output=output,
                error_type=error_type,
            )
        )
    return CasePrediction(case_id=case.id, attempts=tuple(normalized_attempts))


def run_pair(
    *,
    repo_root: Path,
    freeze_record_path: str,
    baseline_endpoint: str,
    candidate_endpoint: str,
    baseline_model_id: str,
    baseline_model_path: Path,
    candidate_model_id: str,
    candidate_model_path: Path,
    observed_server_image_digest: str,
    observed_cpu_count: int,
    observed_thread_count: int,
    observed_context_size: int,
    observed_cache_policy: str,
) -> tuple[Path, Path]:
    """Gate before HTTP, run a paired pass, and save no raw model text."""
    preflight = verify_ai_heldout_exposure_preflight(
        repo_root=repo_root, freeze_record_path=freeze_record_path
    )
    exposure = preflight.exposure
    root = repo_root.resolve()
    policy = preflight.frozen.request_policy
    if (
        _file_sha256(Path(__file__)) != policy.runner_sha256
        or prompt_revision_sha256() != policy.prompt_revision_sha256
    ):
        raise ValueError("runner or live prompt revision differs from frozen request policy")
    if (
        observed_server_image_digest != policy.server_image_digest
        or observed_cpu_count != policy.cpu_count
        or observed_thread_count != policy.thread_count
        or observed_context_size != policy.context_size
        or observed_cache_policy != policy.cache_policy
    ):
        raise ValueError("observed runtime settings differ from frozen request policy")
    if (
        _file_sha256(baseline_model_path) != exposure.baseline_model_sha256
        or _file_sha256(candidate_model_path) != exposure.candidate_model_sha256
    ):
        raise ValueError("model file hash differs from committed exposure record")
    baseline_endpoint = _loopback_endpoint(baseline_endpoint)
    candidate_endpoint = _loopback_endpoint(candidate_endpoint)
    if not baseline_model_id.strip() or not candidate_model_id.strip():
        raise ValueError("both model identifiers are required")
    exposure_commit = preflight.exposure_commit
    cases = preflight.frozen.reviewed.dataset.cases
    observations: dict[str, AIHeldoutPredictionArtifact] = {}
    model_conditions = (
        (
            "baseline",
            baseline_endpoint,
            baseline_model_id,
            exposure.baseline_model_sha256,
        ),
        (
            "candidate",
            candidate_endpoint,
            candidate_model_id,
            exposure.candidate_model_sha256,
        ),
    )
    predictions_by_role: dict[str, list[CasePrediction]] = {"baseline": [], "candidate": []}
    for index, case in enumerate(cases):
        ordered_conditions = (
            model_conditions if index % 2 == 0 else tuple(reversed(model_conditions))
        )
        for role, condition_endpoint, model_id, _model_sha in ordered_conditions:
            predictions_by_role[role].append(
                _run_case(case, endpoint=condition_endpoint, model_id=model_id, policy=policy)
            )
    for role, _endpoint, _model_id, model_sha in model_conditions:
        observations[role] = AIHeldoutPredictionArtifact(
            kind="ai_authored_heldout_predictions_v1",
            role=role,
            exposure_commit=exposure_commit,
            model_sha256=model_sha,
            request_policy_sha256=exposure.request_policy_sha256,
            attempt_policy=exposure.attempt_policy,
            predictions=tuple(predictions_by_role[role]),
        )
    outputs = (
        root / exposure.baseline_prediction_path,
        root / exposure.candidate_prediction_path,
    )
    _write_pair_artifacts(outputs, observations)
    return outputs


def _write_pair_artifacts(
    outputs: tuple[Path, Path], observations: dict[str, AIHeldoutPredictionArtifact]
) -> None:
    """Publish both artifacts exclusively and roll back a failed second link."""
    for output in outputs:
        if output.exists():
            raise ValueError("prediction output already exists")
        output.parent.mkdir(parents=True, exist_ok=True)
    temporary_paths: list[Path] = []
    linked_outputs: list[Path] = []
    try:
        for role, output in zip(("baseline", "candidate"), outputs, strict=True):
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output.parent,
                prefix=f".{output.name}.",
                suffix=".writing",
                delete=False,
            ) as file:
                temporary_paths.append(Path(file.name))
                file.write(observations[role].model_dump_json(indent=2) + "\n")
                file.flush()
                os.fsync(file.fileno())
        for temporary, output in zip(temporary_paths, outputs, strict=True):
            os.link(temporary, output)
            linked_outputs.append(output)
    except BaseException:
        for output in linked_outputs:
            output.unlink()
        raise
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fingerprints", help="Print current runner and prompt source hashes")
    run_parser = subparsers.add_parser("run", help="Run the committed paired evaluation")
    run_parser.add_argument("--repo-root", type=Path, required=True)
    run_parser.add_argument("--freeze-record", required=True)
    run_parser.add_argument("--baseline-endpoint", required=True)
    run_parser.add_argument("--candidate-endpoint", required=True)
    run_parser.add_argument("--baseline-model-id", required=True)
    run_parser.add_argument("--baseline-model-path", type=Path, required=True)
    run_parser.add_argument("--candidate-model-id", required=True)
    run_parser.add_argument("--candidate-model-path", type=Path, required=True)
    run_parser.add_argument("--server-image-digest", required=True)
    run_parser.add_argument("--cpu-count", type=int, required=True)
    run_parser.add_argument("--thread-count", type=int, required=True)
    run_parser.add_argument("--context-size", type=int, required=True)
    run_parser.add_argument("--cache-policy", choices=("cold", "warm", "mixed"), required=True)
    args = parser.parse_args(argv)
    if args.command == "fingerprints":
        print(
            json.dumps(
                {
                    "runner_sha256": _file_sha256(Path(__file__)),
                    "prompt_revision_sha256": prompt_revision_sha256(),
                },
                sort_keys=True,
            )
        )
        return 0
    outputs = run_pair(
        repo_root=args.repo_root,
        freeze_record_path=args.freeze_record,
        baseline_endpoint=args.baseline_endpoint,
        candidate_endpoint=args.candidate_endpoint,
        baseline_model_id=args.baseline_model_id,
        baseline_model_path=args.baseline_model_path,
        candidate_model_id=args.candidate_model_id,
        candidate_model_path=args.candidate_model_path,
        observed_server_image_digest=args.server_image_digest,
        observed_cpu_count=args.cpu_count,
        observed_thread_count=args.thread_count,
        observed_context_size=args.context_size,
        observed_cache_policy=args.cache_policy,
    )
    print("AI-heldout prediction artifacts:", *(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
