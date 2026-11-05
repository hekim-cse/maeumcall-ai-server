"""The AI-heldout review gate cannot promote drafts into an accuracy report."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.structured_nlu.ai_heldout import (
    build_ai_heldout_exposure_record,
    build_ai_heldout_pre_exposure_freeze,
    score_ai_heldout_pair_from_committed_artifacts,
    verify_ai_heldout_exposure_preflight,
    verify_ai_heldout_pre_exposure_freeze,
    verify_ai_heldout_review,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

GOLD_DATASET = (
    Path(__file__).resolve().parents[1] / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
)


def _artifacts() -> tuple[bytes, bytes]:
    """Build fictional fixtures from valid live-contract shapes, not real test data."""
    source = json.loads(GOLD_DATASET.read_text(encoding="utf-8"))
    by_scenario = {}
    for case in source["cases"]:
        by_scenario.setdefault(case["scenario_key"], case)
    assert set(by_scenario) == set(EVALUATION_CONTRACTS)
    cases = []
    for case in by_scenario.values():
        item = dict(case)
        item["split"] = "test"
        item["review_status"] = "adjudicated"
        item["provenance"] = "ai_authored"
        cases.append(item)
    dataset = {
        "kind": "ai_authored_heldout_dataset_v1",
        "dataset_version": 1,
        "state_contract_version": 2,
        "declared_model_exposure": "not_run",
        "cases": cases,
    }
    dataset_bytes = json.dumps(dataset, ensure_ascii=False).encode()
    ledger = {
        "kind": "ai_authored_heldout_review_v1",
        "reviewed_for": "ai_authored_heldout_accuracy",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "accepted_case_ids": sorted(case["id"] for case in cases),
        "adjudicator_id": "test-reviewer",
        "adjudicated_at": "2026-11-06T00:00:00+00:00",
        "rationale": "Synthetic gate test fixture; no human review is claimed.",
    }
    return dataset_bytes, json.dumps(ledger).encode()


def test_review_gate_records_exact_sha_and_all_scenario_counts() -> None:
    dataset_bytes, ledger_bytes = _artifacts()

    reviewed = verify_ai_heldout_review(dataset_bytes, ledger_bytes)

    assert reviewed.dataset_sha256 == hashlib.sha256(dataset_bytes).hexdigest()
    assert len(reviewed.scenario_counts) == 16
    assert set(reviewed.scenario_counts) == set(EVALUATION_CONTRACTS)
    assert sum(reviewed.scenario_counts.values()) == 16


def test_review_gate_rejects_changed_raw_bytes_even_if_meaning_is_same() -> None:
    dataset_bytes, ledger_bytes = _artifacts()

    with pytest.raises(ValueError, match="exact AI heldout dataset bytes"):
        verify_ai_heldout_review(dataset_bytes + b"\n", ledger_bytes)


def test_review_gate_rejects_unreviewed_or_non_test_cases() -> None:
    dataset_bytes, ledger_bytes = _artifacts()
    for field, value, message in (
        ("review_status", "draft", "adjudicated cases only"),
        ("split", "development", "test cases only"),
    ):
        dataset = json.loads(dataset_bytes)
        dataset["cases"][0][field] = value
        changed = json.dumps(dataset, ensure_ascii=False).encode()
        ledger = json.loads(ledger_bytes)
        ledger["dataset_sha256"] = hashlib.sha256(changed).hexdigest()
        with pytest.raises(ValueError, match=message):
            verify_ai_heldout_review(changed, json.dumps(ledger).encode())


def test_review_gate_rejects_missing_scenario_or_case_id() -> None:
    dataset_bytes, ledger_bytes = _artifacts()
    dataset = json.loads(dataset_bytes)
    dataset["cases"].pop()
    changed = json.dumps(dataset, ensure_ascii=False).encode()
    ledger = json.loads(ledger_bytes)
    ledger["dataset_sha256"] = hashlib.sha256(changed).hexdigest()
    with pytest.raises(ValueError, match="case IDs must exactly match"):
        verify_ai_heldout_review(changed, json.dumps(ledger).encode())
    ledger["accepted_case_ids"] = sorted(case["id"] for case in dataset["cases"])
    with pytest.raises(ValueError, match="all 16 detailed scenarios"):
        verify_ai_heldout_review(changed, json.dumps(ledger).encode())


def test_review_gate_refuses_human_provenance_and_duplicate_inputs() -> None:
    dataset_bytes, ledger_bytes = _artifacts()
    dataset = json.loads(dataset_bytes)
    dataset["cases"][0]["provenance"] = "human_authored"
    with pytest.raises(ValidationError, match="ai_authored"):
        verify_ai_heldout_review(json.dumps(dataset, ensure_ascii=False).encode(), ledger_bytes)

    dataset = json.loads(dataset_bytes)
    copied = dict(dataset["cases"][0])
    copied["id"] = "duplicate-input-case"
    copied["conversation_group_id"] = "duplicate-input-group"
    dataset["cases"].append(copied)
    with pytest.raises(ValidationError, match="duplicate AI heldout model inputs"):
        verify_ai_heldout_review(json.dumps(dataset, ensure_ascii=False).encode(), ledger_bytes)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _committed_input_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Gate Test")
    _git(repo, "config", "user.email", "gate-test@example.invalid")
    dataset_bytes, ledger_bytes = _artifacts()
    (repo / "dataset.json").write_bytes(dataset_bytes)
    (repo / "review.json").write_bytes(ledger_bytes)
    (repo / "protocol.json").write_text(
        json.dumps(
            {
                "kind": "ai_authored_heldout_request_policy_v1",
                "server_image_digest": "sha256:" + "c" * 64,
                "runner_sha256": "d" * 64,
                "prompt_revision_sha256": "e" * 64,
                "cpu_count": 2,
                "thread_count": 2,
                "context_size": 4096,
                "max_tokens": 180,
                "temperature": 0,
                "repeat_penalty": 1.05,
                "stop": ["<|eot_id|>"],
                "timeout_seconds": 180,
                "cache_policy": "warm",
                "retry_policy": "one_retry_after_contract_failure",
            }
        )
    )
    _git(repo, "add", "dataset.json", "review.json", "protocol.json")
    _git(repo, "commit", "-qm", "freeze inputs")
    return repo, _git(repo, "rev-parse", "HEAD")


def _write_record(repo: Path, input_commit: str) -> None:
    record = build_ai_heldout_pre_exposure_freeze(
        repo_root=repo,
        input_git_revision=input_commit,
        dataset_path="dataset.json",
        review_ledger_path="review.json",
        protocol_path="protocol.json",
        exposure_record_path="exposure.json",
    )
    (repo / "freeze.json").write_text(record.model_dump_json(indent=2) + "\n")


def test_pre_exposure_freeze_requires_committed_record_and_exact_input(tmp_path: Path) -> None:
    repo, input_commit = _committed_input_repo(tmp_path)
    _write_record(repo, input_commit)
    with pytest.raises(ValueError, match="exactly one artifact"):
        verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")

    _git(repo, "add", "freeze.json")
    _git(repo, "commit", "-qm", "freeze record")
    verified = verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")
    assert verified.record.input_git_revision == input_commit
    assert len(verified.reviewed.scenario_counts) == 16

    (repo / "dataset.json").write_bytes((repo / "dataset.json").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs from input Git commit"):
        verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")


def test_pre_exposure_freeze_rejects_missing_review_and_exposure(tmp_path: Path) -> None:
    repo, input_commit = _committed_input_repo(tmp_path)
    (repo / "review.json").unlink()
    with pytest.raises(ValueError, match="regular file"):
        _write_record(repo, input_commit)
    _git(repo, "restore", "review.json")
    _write_record(repo, input_commit)
    _git(repo, "add", "freeze.json")
    _git(repo, "commit", "-qm", "freeze record")
    (repo / "exposure.json").write_text("{}\n")
    with pytest.raises(ValueError, match="exposure record already exists"):
        verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")


def test_pre_exposure_freeze_rejects_changed_record_or_protocol(tmp_path: Path) -> None:
    repo, input_commit = _committed_input_repo(tmp_path)
    _write_record(repo, input_commit)
    _git(repo, "add", "freeze.json")
    _git(repo, "commit", "-qm", "freeze record")
    (repo / "freeze.json").write_bytes((repo / "freeze.json").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="differs from the Git HEAD blob"):
        verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")
    _git(repo, "restore", "freeze.json")
    (repo / "protocol.json").write_text('{"kind":"changed"}\n')
    with pytest.raises(ValueError, match="differs from input Git commit"):
        verify_ai_heldout_pre_exposure_freeze(repo_root=repo, record_path="freeze.json")


def test_pre_exposure_freeze_rejects_unstructured_request_policy(tmp_path: Path) -> None:
    repo, _input_commit = _committed_input_repo(tmp_path)
    (repo / "protocol.json").write_text("Both models should use the same settings.\n")
    _git(repo, "add", "protocol.json")
    _git(repo, "commit", "-qm", "invalid prose policy")
    with pytest.raises(ValidationError):
        _write_record(repo, _git(repo, "rev-parse", "HEAD"))


def _committed_exposure_repo(tmp_path: Path) -> tuple[Path, str]:
    repo, input_commit = _committed_input_repo(tmp_path)
    _write_record(repo, input_commit)
    _git(repo, "add", "freeze.json")
    _git(repo, "commit", "-qm", "freeze record")
    exposure = build_ai_heldout_exposure_record(
        repo_root=repo,
        freeze_record_path="freeze.json",
        baseline_model_sha256="a" * 64,
        candidate_model_sha256="b" * 64,
        baseline_prediction_path="baseline.json",
        candidate_prediction_path="candidate.json",
    )
    (repo / "exposure.json").write_text(exposure.model_dump_json(indent=2) + "\n")
    _git(repo, "add", "exposure.json")
    _git(repo, "commit", "-qm", "exposure record before model calls")
    return repo, _git(repo, "rev-parse", "HEAD")


def _prediction_artifact(repo: Path, exposure_commit: str, role: str) -> dict:
    dataset = json.loads((repo / "dataset.json").read_text())
    exposure = json.loads((repo / "exposure.json").read_text())
    predictions = []
    baseline_changed = False
    for case in dataset["cases"]:
        labels = case["labels"]
        fields = {
            key: value["accepted_values"][0] if value is not None else None
            for key, value in labels["fields"].items()
        }
        action = labels["user_action"]
        if role == "baseline" and not baseline_changed and action != "unknown":
            fields = dict.fromkeys(fields)
            action = "unknown"
            baseline_changed = True
        predictions.append(
            {
                "case_id": case["id"],
                "attempts": [
                    {
                        "contract_valid": True,
                        "latency_ms": 1.0,
                        "output": {
                            "intent": labels["intent"],
                            "fields": fields,
                            "user_action": action,
                            "change_field": labels["change_field"],
                        },
                    }
                ],
            }
        )
    return {
        "kind": "ai_authored_heldout_predictions_v1",
        "role": role,
        "exposure_commit": exposure_commit,
        "model_sha256": exposure[f"{role}_model_sha256"],
        "request_policy_sha256": exposure["request_policy_sha256"],
        "attempt_policy": exposure["attempt_policy"],
        "predictions": predictions,
    }


def test_paired_score_requires_exposure_commit_before_prediction_commit(tmp_path: Path) -> None:
    repo, exposure_commit = _committed_exposure_repo(tmp_path)
    preflight = verify_ai_heldout_exposure_preflight(
        repo_root=repo, freeze_record_path="freeze.json"
    )
    assert len(preflight.case_ids) == 16
    with pytest.raises(ValueError, match="predictions must be committed after"):
        score_ai_heldout_pair_from_committed_artifacts(
            repo_root=repo,
            freeze_record_path="freeze.json",
            exposure_commit=exposure_commit,
        )
    for role in ("baseline", "candidate"):
        (repo / f"{role}.json").write_text(
            json.dumps(_prediction_artifact(repo, exposure_commit, role), ensure_ascii=False)
        )
    _git(repo, "add", "baseline.json", "candidate.json")
    _git(repo, "commit", "-qm", "paired predictions")

    scores = score_ai_heldout_pair_from_committed_artifacts(
        repo_root=repo,
        freeze_record_path="freeze.json",
        exposure_commit=exposure_commit,
    )
    assert scores.cases == 16
    assert (scores.baseline_correct, scores.candidate_correct) == (15, 16)
    assert scores.difference_percentage_points == 6.25
    assert scores.source == "ai_authored_human_adjudicated_heldout"


def test_paired_score_rejects_missing_case_and_changed_policy(tmp_path: Path) -> None:
    repo, exposure_commit = _committed_exposure_repo(tmp_path)
    baseline = _prediction_artifact(repo, exposure_commit, "baseline")
    baseline["predictions"].pop()
    candidate = _prediction_artifact(repo, exposure_commit, "candidate")
    (repo / "baseline.json").write_text(json.dumps(baseline, ensure_ascii=False))
    (repo / "candidate.json").write_text(json.dumps(candidate, ensure_ascii=False))
    _git(repo, "add", "baseline.json", "candidate.json")
    _git(repo, "commit", "-qm", "incomplete predictions")
    with pytest.raises(ValueError, match="case IDs do not match"):
        score_ai_heldout_pair_from_committed_artifacts(
            repo_root=repo,
            freeze_record_path="freeze.json",
            exposure_commit=exposure_commit,
        )

    baseline = _prediction_artifact(repo, exposure_commit, "baseline")
    baseline["request_policy_sha256"] = "0" * 64
    (repo / "baseline.json").write_text(json.dumps(baseline, ensure_ascii=False))
    _git(repo, "add", "baseline.json")
    _git(repo, "commit", "-qm", "wrong request policy")
    with pytest.raises(ValueError, match="differs from frozen run policy"):
        score_ai_heldout_pair_from_committed_artifacts(
            repo_root=repo,
            freeze_record_path="freeze.json",
            exposure_commit=exposure_commit,
        )
