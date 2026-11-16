"""Real two-worktree preflight and 128-arm raw replay with synthetic Q5 transport."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutDataset
from evals.structured_nlu.ai_reviewed_internal_policy_v1 import case_sha256
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.schema import DatasetSplit
from experiments.internal_test_pair_v1 import qualification as gate
from experiments.internal_test_pair_v1 import run as pair_run
from experiments.internal_test_pair_v1 import verify as pair_verify


def _synthetic_inputs(candidate: Path) -> None:
    original = AIHeldoutDataset.model_validate_json(
        (candidate / gate.INPUT_PATHS["validation_dataset"]).read_bytes()
    )
    cases = []
    for index, source in enumerate(original.cases):
        for state_kind in ("greeting", "later"):
            if state_kind == "greeting":
                state = "greeting"
            else:
                contract = EVALUATION_CONTRACTS[source.scenario_key]
                candidates = sorted(
                    (name for name in contract.conversation_states if name != "greeting"),
                    key=lambda name: ("collecting" not in name, name),
                )
                state = next(name for name in candidates if _valid_later(source, name))
            case_id = f"synthetic-test-{index:02d}-{state_kind}"
            case = AIHeldoutCase.model_validate(
                source.model_copy(
                    update={
                        "id": case_id,
                        "conversation_group_id": case_id,
                        "split": DatasetSplit.TEST,
                        "conversation_state": state,
                        "user_message": f"합성 {state_kind} {index:02d}: {source.user_message}",
                    }
                ).model_dump(mode="json")
            )
            cases.append(case)
    dataset = AIHeldoutDataset.model_validate(
        original.model_copy(update={"cases": tuple(cases)}).model_dump(mode="json")
    )
    raw = (
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    ).encode()
    digest = hashlib.sha256(raw).hexdigest()
    ids = sorted(case.id for case in dataset.cases)
    reviewed_at = "2026-11-17T00:00:00+09:00"
    ledger = {
        "kind": "ai_authored_heldout_review_v1",
        "reviewed_for": "ai_authored_heldout_accuracy",
        "dataset_sha256": digest,
        "accepted_case_ids": ids,
        "adjudicator_id": "synthetic-fixture",
        "adjudicated_at": reviewed_at,
        "rationale": "Synthetic test fixture only, never a human adjudication claim.",
    }
    decisions = {
        "kind": "ai_reviewed_internal_case_decisions_v1",
        "dataset_sha256": digest,
        "decisions": [
            {
                "case_id": case.id,
                "case_sha256": case_sha256(case),
                "adjudicator_role_id": "synthetic-fixture",
                "adjudicated_at": reviewed_at,
                "decision": "accepted",
                "rationale": "Synthetic fixture for harness mechanics only.",
            }
            for case in sorted(dataset.cases, key=lambda item: item.id)
        ],
    }
    for key, value in (
        ("test_dataset", raw),
        ("test_review_ledger", (json.dumps(ledger, ensure_ascii=False) + "\n").encode()),
        ("test_case_decisions", (json.dumps(decisions, ensure_ascii=False) + "\n").encode()),
    ):
        path = candidate / gate.INPUT_PATHS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)


def _valid_later(source: AIHeldoutCase, state: str) -> bool:
    try:
        AIHeldoutCase.model_validate(
            source.model_copy(update={"conversation_state": state}).model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def _synthetic_safety_inputs(candidate: Path) -> None:
    source = AIHeldoutDataset.model_validate_json(
        (
            candidate
            / "evals/structured_nlu/data/ai_heldout/nlu-safety-confirmation-reviewed.v1.json"
        ).read_bytes()
    )
    selected = (
        list(source.cases[:4])
        + list(source.cases[12:16])
        + list(source.cases[20:24])
        + list(source.cases[28:32])
    )
    categories = ("direct", "uncertain", "other_source", "nonoccurring")
    cases = []
    mappings = []
    for index, original in enumerate(selected):
        case_id = f"synthetic-ss-{index:02d}"
        case = AIHeldoutCase.model_validate(
            original.model_copy(
                update={
                    "id": case_id,
                    "conversation_group_id": case_id,
                    "user_message": f"합성 SS {index:02d}: {original.user_message}",
                }
            ).model_dump(mode="json")
        )
        cases.append(case)
        mappings.append({"case_id": case_id, "category": categories[index // 4]})
    dataset = AIHeldoutDataset.model_validate(
        source.model_copy(update={"cases": tuple(cases)}).model_dump(mode="json")
    )
    raw = (
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    ).encode()
    digest = hashlib.sha256(raw).hexdigest()
    reviewed_at = "2026-11-17T00:00:00+09:00"
    ledger = {
        "kind": "ai_authored_heldout_review_v1",
        "reviewed_for": "ai_authored_heldout_accuracy",
        "dataset_sha256": digest,
        "accepted_case_ids": sorted(case.id for case in cases),
        "adjudicator_id": "synthetic-fixture",
        "adjudicated_at": reviewed_at,
        "rationale": "Synthetic safety fixture only, not a human adjudication claim.",
    }
    decisions = {
        "kind": "ai_reviewed_internal_case_decisions_v1",
        "dataset_sha256": digest,
        "decisions": [
            {
                "case_id": case.id,
                "case_sha256": case_sha256(case),
                "adjudicator_role_id": "synthetic-fixture",
                "adjudicated_at": reviewed_at,
                "decision": "accepted",
                "rationale": "Synthetic safety mechanics fixture only.",
            }
            for case in sorted(cases, key=lambda item: item.id)
        ],
    }
    category_ledger = {
        "kind": "ai_reviewed_internal_safety16_categories_v1",
        "dataset_sha256": digest,
        "categories": mappings,
    }
    for key, value in (
        ("safety_dataset", raw),
        ("safety_review_ledger", (json.dumps(ledger, ensure_ascii=False) + "\n").encode()),
        ("safety_case_decisions", (json.dumps(decisions, ensure_ascii=False) + "\n").encode()),
        (
            "safety_category_ledger",
            (json.dumps(category_ledger, ensure_ascii=False) + "\n").encode(),
        ),
    ):
        path = candidate / gate.SAFETY_INPUT_PATHS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)


def test_two_git_worktrees_fake_q5_full_receipt_and_tamper(monkeypatch, tmp_path: Path):
    fake_site = tmp_path / "fake_site"
    fake_site.mkdir()
    (fake_site / "sitecustomize.py").write_text(
        "import io\nimport urllib.request\n"
        "def fake_open(self, request, timeout=None):\n"
        '    return io.BytesIO(b\'{"choices":[{"message":{"content":"{}"}}]}\')\n'
        "urllib.request.OpenerDirector.open = fake_open\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(fake_site))
    clone = tmp_path / "clone"
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    subprocess.run(
        (
            "git",
            "clone",
            "-q",
            "--local",
            "--no-hardlinks",
            "--no-checkout",
            str(gate.ROOT),
            str(clone),
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(clone),
            "worktree",
            "add",
            "-q",
            "--detach",
            str(baseline),
            gate.BASELINE_COMMIT,
        ),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(clone),
            "worktree",
            "add",
            "-q",
            "--detach",
            str(candidate),
            gate.CANDIDATE_COMMIT,
        ),
        check=True,
    )
    shutil.copytree(
        gate.ROOT / gate.HARNESS_ROOT,
        candidate / gate.HARNESS_ROOT,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    _synthetic_inputs(candidate)
    _synthetic_safety_inputs(candidate)

    def commit(message: str) -> str:
        subprocess.run(("git", "-C", str(candidate), "add", "."), check=True)
        subprocess.run(
            (
                "git",
                "-C",
                str(candidate),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                message,
            ),
            check=True,
        )
        return gate._git(candidate, "rev-parse", "HEAD").decode().strip()

    input_commit = commit("synthetic input and harness")
    model = tmp_path / "fake.gguf"
    model.write_bytes(b"synthetic Q5 boundary")
    monkeypatch.setattr(gate, "MODEL_SHA256", gate._file_sha(model))
    output = tmp_path / "result.json"
    journal = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    receipt = tmp_path / "verified.json"
    protocol_path = candidate / "protocol.json"
    frozen = gate.build_protocol(
        baseline_root=baseline,
        baseline_commit=gate.BASELINE_COMMIT,
        candidate_root=candidate,
        candidate_commit=gate.CANDIDATE_COMMIT,
        input_commit=input_commit,
        model_path=model,
        output=output,
        journal=journal,
        private_dir=private,
        receipt=receipt,
    )
    protocol_path.write_text(json.dumps(frozen, ensure_ascii=False), encoding="utf-8")
    commit("synthetic protocol")
    safety_output = tmp_path / "safety-result.json"
    safety_journal = tmp_path / "safety-journal.jsonl"
    safety_private = tmp_path / "safety-private"
    safety_receipt = tmp_path / "safety-verified.json"
    safety_protocol_path = candidate / "safety-protocol.json"
    safety_frozen = gate.build_protocol(
        baseline_root=baseline,
        baseline_commit=gate.BASELINE_COMMIT,
        candidate_root=candidate,
        candidate_commit=gate.CANDIDATE_COMMIT,
        input_commit=input_commit,
        model_path=model,
        output=safety_output,
        journal=safety_journal,
        private_dir=safety_private,
        receipt=safety_receipt,
        suite="safety16",
    )
    safety_protocol_path.write_text(json.dumps(safety_frozen, ensure_ascii=False), encoding="utf-8")
    commit("synthetic safety protocol")
    common = dict(
        protocol_path=protocol_path,
        baseline_root=baseline,
        candidate_root=candidate,
        model_path=model,
        output=output,
        journal=journal,
        private_dir=private,
        receipt=receipt,
    )
    assert gate.preflight(**common)[0] == frozen
    safety_common = dict(
        protocol_path=safety_protocol_path,
        baseline_root=baseline,
        candidate_root=candidate,
        model_path=model,
        output=safety_output,
        journal=safety_journal,
        private_dir=safety_private,
        receipt=safety_receipt,
    )
    assert gate.preflight(**safety_common)[0] == safety_frozen

    state = {"restarts": 0}

    def observed(*_args, **_kwargs):
        return {
            "Id": "d" * 64,
            "State": {
                "StartedAt": f"start-{state['restarts']}",
                "Running": True,
                "OOMKilled": False,
            },
            "RestartCount": 0,
        }

    def boundary(stream, _name, _model, _protocol, phase, count):
        row = {
            "event": "server_boundary",
            "phase": phase,
            "completed_cases": count,
            "running": True,
            "oom_killed": False,
            "exit_code": 0,
            "restart_count": 0,
            "container_id": "d" * 64,
            "started_at": f"start-{state['restarts']}",
            "docker_host_memory_bytes": gate.LOCAL_RUNTIME["docker_host_min_memory_bytes"],
            "memory_usage": "1GiB / 10GiB",
            "healthy": True,
        }
        pair_run._append(stream, row)
        return row

    original_run = subprocess.run

    def intercept(command, *args, **kwargs):
        if tuple(command[:2]) == ("docker", "restart"):
            state["restarts"] += 1
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(pair_run.server, "verify_container", observed)
    monkeypatch.setattr(pair_run, "_boundary", boundary)
    monkeypatch.setattr(pair_run.subprocess, "run", intercept)
    result = pair_run.run(**common, container_name="fake")
    assert result["verification_status"] == "unverified"
    assert len(result["predictions"]["baseline"]) == 64
    assert len(result["predictions"]["candidate"]) == 64
    assert all(
        len(row["attempts"]) == 2
        and all(not attempt["contract_valid"] for attempt in row["attempts"])
        for rows in result["predictions"].values()
        for row in rows
    )
    assert len(list(private.glob("*.txt"))) == 128 * 2
    assert state["restarts"] == 15
    verified = pair_verify.verify(**common)
    assert verified["verification_status"] == "verified"
    assert verified["publication_status"] == "provisional_pending_fresh_safety16_and_exposure_audit"
    assert verified["safety_condition"] == "unverified"
    assert verified["arm_evaluations"] == 128
    assert verified["paired_counts"]["both_incorrect"] == 64
    assert verified["bootstrap"]["difference"] == 0
    safety_result = pair_run.run(**safety_common, container_name="fake")
    assert len(safety_result["predictions"]["baseline"]) == 16
    assert len(safety_result["predictions"]["candidate"]) == 16
    assert state["restarts"] == 18
    safety_verified = pair_verify.verify(**safety_common)
    assert safety_verified["verification_status"] == "verified"
    assert safety_verified["arm_evaluations"] == 32
    assert safety_verified["safety_counts"]["direct_candidate_misses"] == 4
    assert safety_verified["safety_counts"]["direct_new_misses"] == 0
    assert safety_verified["safety_counts"]["negative_denominator"] == 8
    safety_receipt.unlink()
    next(safety_private.iterdir()).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="private raw response"):
        pair_verify.verify(**safety_common)
    receipt.unlink()
    next(private.iterdir()).write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="private raw response"):
        pair_verify.verify(**common)
