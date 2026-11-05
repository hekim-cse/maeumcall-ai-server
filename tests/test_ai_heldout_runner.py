"""Offline seam tests for the AI-heldout prediction runner."""

from __future__ import annotations

import json
import os
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import CasePrediction, EvaluationAttempt, NormalizedPrediction
from scripts import run_ai_heldout_pair as runner

GOLD_DATASET = (
    Path(__file__).resolve().parents[1] / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
)


def _case(scenario: str) -> AIHeldoutCase:
    for original in json.loads(GOLD_DATASET.read_text())["cases"]:
        if original["scenario_key"] == scenario and original["labels"]["user_action"] != "unknown":
            return AIHeldoutCase.model_validate(
                original | {"provenance": "ai_authored", "split": "test"}
            )
    raise AssertionError(f"fixture scenario missing: {scenario}")


def _policy() -> AIHeldoutRequestPolicy:
    return AIHeldoutRequestPolicy(
        kind="ai_authored_heldout_request_policy_v1",
        server_image_digest="sha256:" + "a" * 64,
        runner_sha256="b" * 64,
        prompt_revision_sha256="c" * 64,
        cpu_count=2,
        thread_count=2,
        context_size=4096,
        max_tokens=180,
        temperature=0,
        repeat_penalty=1.05,
        stop=("<|eot_id|>",),
        timeout_seconds=180,
        cache_policy="warm",
        pair_order="alternating",
        retry_policy="one_retry_after_contract_failure",
    )


def _gold_raw(case: AIHeldoutCase, *, nested: bool) -> str:
    fields = {
        name: expected.accepted_values[0] if expected is not None else None
        for name, expected in case.labels.fields.items()
    }
    payload = {
        "intent": case.labels.intent,
        "user_action": case.labels.user_action,
    }
    if nested:
        payload["fields"] = fields
        payload["change_field"] = case.labels.change_field
    else:
        payload.update(fields)
    return json.dumps(payload, ensure_ascii=False)


def test_runner_dispatch_covers_all_live_detailed_analyzers() -> None:
    direct = {
        key for key, contract in EVALUATION_CONTRACTS.items() if contract.workflow_spec is None
    }
    workflow = {
        key for key, contract in EVALUATION_CONTRACTS.items() if contract.workflow_spec is not None
    }
    assert set(runner.DIRECT_ANALYZERS) == direct
    assert len(direct) + len(workflow) == 16
    assert "scripts/probe_gguf_structured_nlu.py" in runner.PROMPT_SOURCES


def test_live_direct_analyzer_records_invalid_then_valid_attempt() -> None:
    case = _case("교수님:면담 예약")
    responses = iter(("{}", _gold_raw(case, nested=False)))

    prediction = runner._run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model_id="mock-model",
        policy=_policy(),
        completion_post=lambda *_args: next(responses),
    )

    assert len(prediction.attempts) == 2
    assert prediction.attempts[0].contract_valid is False
    assert prediction.attempts[0].error_type
    assert prediction.final_output is not None
    assert prediction.final_output.user_action == case.labels.user_action
    assert "user_message" not in prediction.model_dump_json()
    assert "messages" not in prediction.model_dump_json()


def test_live_workflow_analyzer_returns_normalized_fields() -> None:
    case = _case("고객센터:a/s 접수")
    prediction = runner._run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model_id="mock-model",
        policy=_policy(),
        completion_post=lambda *_args: _gold_raw(case, nested=True),
    )
    assert len(prediction.attempts) == 1
    assert prediction.final_output is not None
    assert set(prediction.final_output.fields) == set(case.labels.fields)


def test_transport_failure_is_recorded_and_retried_without_raw_text() -> None:
    case = _case("교수님:면담 예약")
    calls = 0

    def completion(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.URLError("test transport failure")
        return _gold_raw(case, nested=False)

    prediction = runner._run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model_id="mock-model",
        policy=_policy(),
        completion_post=completion,
    )
    assert calls == 2
    assert prediction.attempts[0].error_type == "URLError"
    assert prediction.final_output is not None
    assert "test transport failure" not in prediction.model_dump_json()


def test_invalid_freeze_blocks_runner_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(**_kwargs):
        raise ValueError("freeze unavailable")

    monkeypatch.setattr(runner, "verify_ai_heldout_exposure_preflight", reject)
    monkeypatch.setattr(
        runner,
        "_run_case",
        lambda *_args, **_kwargs: pytest.fail("model must not run before freeze gate"),
    )
    with pytest.raises(ValueError, match="freeze unavailable"):
        runner.run_pair(
            repo_root=Path("/unused"),
            freeze_record_path="freeze.json",
            baseline_endpoint="http://127.0.0.1:18080/v1/chat/completions",
            candidate_endpoint="http://127.0.0.1:18081/v1/chat/completions",
            baseline_model_id="q4",
            baseline_model_path=Path("/unused-q4"),
            candidate_model_id="q5",
            candidate_model_path=Path("/unused-q5"),
            observed_server_image_digest="sha256:" + "a" * 64,
            observed_cpu_count=2,
            observed_thread_count=2,
            observed_context_size=4096,
            observed_cache_policy="warm",
        )


def test_runtime_mismatch_blocks_runner_before_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy = _policy().model_copy(
        update={
            "runner_sha256": runner._file_sha256(Path(runner.__file__)),
            "prompt_revision_sha256": runner.prompt_revision_sha256(),
        }
    )
    exposure = SimpleNamespace(baseline_model_sha256="a" * 64, candidate_model_sha256="b" * 64)
    monkeypatch.setattr(
        runner,
        "verify_ai_heldout_exposure_preflight",
        lambda **_kw: SimpleNamespace(
            exposure=exposure,
            frozen=SimpleNamespace(request_policy=policy),
            exposure_commit="0" * 40,
        ),
    )
    monkeypatch.setattr(
        runner,
        "_run_case",
        lambda *_args, **_kwargs: pytest.fail("model must not run on settings mismatch"),
    )
    with pytest.raises(ValueError, match="observed runtime settings differ"):
        runner.run_pair(
            repo_root=tmp_path,
            freeze_record_path="freeze.json",
            baseline_endpoint="http://127.0.0.1:18080/v1/chat/completions",
            candidate_endpoint="http://127.0.0.1:18081/v1/chat/completions",
            baseline_model_id="q4",
            baseline_model_path=tmp_path / "q4.gguf",
            candidate_model_id="q5",
            candidate_model_path=tmp_path / "q5.gguf",
            observed_server_image_digest="sha256:" + "0" * 64,
            observed_cpu_count=2,
            observed_thread_count=2,
            observed_context_size=4096,
            observed_cache_policy="warm",
        )


def test_remote_or_redirectable_endpoint_is_rejected() -> None:
    for endpoint in (
        "https://127.0.0.1:18080/v1/chat/completions",
        "http://example.com:18080/v1/chat/completions",
        "http://127.0.0.1:18080/other",
    ):
        with pytest.raises(ValueError, match="loopback"):
            runner._loopback_endpoint(endpoint)


def test_model_file_hash_mismatch_blocks_runner_before_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy = _policy().model_copy(
        update={
            "runner_sha256": runner._file_sha256(Path(runner.__file__)),
            "prompt_revision_sha256": runner.prompt_revision_sha256(),
        }
    )
    exposure = SimpleNamespace(baseline_model_sha256="a" * 64, candidate_model_sha256="b" * 64)
    monkeypatch.setattr(
        runner,
        "verify_ai_heldout_exposure_preflight",
        lambda **_kw: SimpleNamespace(
            exposure=exposure,
            frozen=SimpleNamespace(request_policy=policy),
            exposure_commit="0" * 40,
        ),
    )
    monkeypatch.setattr(
        runner,
        "_run_case",
        lambda *_args, **_kwargs: pytest.fail("model must not run on hash mismatch"),
    )
    q4 = tmp_path / "q4.gguf"
    q5 = tmp_path / "q5.gguf"
    q4.write_bytes(b"model-q4")
    q5.write_bytes(b"model-q5")
    with pytest.raises(ValueError, match="model file hash differs"):
        runner.run_pair(
            repo_root=tmp_path,
            freeze_record_path="freeze.json",
            baseline_endpoint="http://127.0.0.1:18080/v1/chat/completions",
            candidate_endpoint="http://127.0.0.1:18081/v1/chat/completions",
            baseline_model_id="q4",
            baseline_model_path=q4,
            candidate_model_id="q5",
            candidate_model_path=q5,
            observed_server_image_digest=policy.server_image_digest,
            observed_cpu_count=policy.cpu_count,
            observed_thread_count=policy.thread_count,
            observed_context_size=policy.context_size,
            observed_cache_policy=policy.cache_policy,
        )


def test_pair_runner_writes_only_normalized_predictions_in_alternating_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    q4 = tmp_path / "q4.gguf"
    q5 = tmp_path / "q5.gguf"
    q4.write_bytes(b"model-q4")
    q5.write_bytes(b"model-q5")
    policy = _policy().model_copy(
        update={
            "runner_sha256": runner._file_sha256(Path(runner.__file__)),
            "prompt_revision_sha256": runner.prompt_revision_sha256(),
        }
    )
    cases = (_case("교수님:면담 예약"), _case("고객센터:a/s 접수"))
    exposure = SimpleNamespace(
        baseline_model_sha256=runner._file_sha256(q4),
        candidate_model_sha256=runner._file_sha256(q5),
        baseline_prediction_path="baseline.json",
        candidate_prediction_path="candidate.json",
        request_policy_sha256="f" * 64,
        attempt_policy=policy.retry_policy,
    )
    monkeypatch.setattr(
        runner,
        "verify_ai_heldout_exposure_preflight",
        lambda **_kw: SimpleNamespace(
            exposure=exposure,
            frozen=SimpleNamespace(
                request_policy=policy,
                reviewed=SimpleNamespace(dataset=SimpleNamespace(cases=cases)),
            ),
            exposure_commit="0" * 40,
        ),
    )
    observed_order = []

    def fake_case(case, *, model_id, **_kwargs):
        observed_order.append((case.id, model_id))
        labels = case.labels
        output = NormalizedPrediction(
            intent=labels.intent,
            fields={
                name: value.accepted_values[0] if value is not None else None
                for name, value in labels.fields.items()
            },
            user_action=labels.user_action,
            change_field=labels.change_field,
        )
        return CasePrediction(
            case_id=case.id,
            attempts=(EvaluationAttempt(contract_valid=True, latency_ms=1.0, output=output),),
        )

    monkeypatch.setattr(runner, "_run_case", fake_case)
    outputs = runner.run_pair(
        repo_root=tmp_path,
        freeze_record_path="freeze.json",
        baseline_endpoint="http://127.0.0.1:18080/v1/chat/completions",
        candidate_endpoint="http://127.0.0.1:18081/v1/chat/completions",
        baseline_model_id="q4",
        baseline_model_path=q4,
        candidate_model_id="q5",
        candidate_model_path=q5,
        observed_server_image_digest=policy.server_image_digest,
        observed_cpu_count=policy.cpu_count,
        observed_thread_count=policy.thread_count,
        observed_context_size=policy.context_size,
        observed_cache_policy=policy.cache_policy,
    )
    assert observed_order == [
        (cases[0].id, "q4"),
        (cases[0].id, "q5"),
        (cases[1].id, "q5"),
        (cases[1].id, "q4"),
    ]
    assert outputs == (tmp_path / "baseline.json", tmp_path / "candidate.json")
    for output in outputs:
        content = output.read_text()
        assert "user_message" not in content
        assert "messages" not in content
        assert len(json.loads(content)["predictions"]) == 2


def test_pair_output_rolls_back_if_second_publish_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outputs = (tmp_path / "baseline.json", tmp_path / "candidate.json")
    artifact = SimpleNamespace(model_dump_json=lambda indent: '{"predictions":[]}')
    original_link = os.link
    calls = 0

    def fail_second_link(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated second publish failure")
        return original_link(source, target)

    monkeypatch.setattr(runner.os, "link", fail_second_link)
    with pytest.raises(OSError, match="second publish failure"):
        runner._write_pair_artifacts(outputs, {"baseline": artifact, "candidate": artifact})
    assert all(not output.exists() for output in outputs)
    assert not list(tmp_path.glob("*.writing"))
