"""The validation pair must fail before model calls when inputs are unqualified."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unicodedata

import pytest

from experiments.internal_validation_pair_v1 import qualification as gate
from experiments.internal_validation_pair_v1 import worker


@pytest.fixture
def reviewed_inputs():
    return {key: (gate.ROOT / path).read_bytes() for key, path in gate.INPUT_PATHS.items()}


def test_reviewed_validation_qualifies_only_as_balanced_candidate_selection(reviewed_inputs):
    case_ids, digests = gate.qualify_validation(gate.ROOT, reviewed_inputs)
    schedule = gate.pair_order(case_ids)
    assert len(case_ids) == len(schedule) == 32
    assert len(digests) == 4
    assert schedule[0] == {"case_id": case_ids[0], "arms": ["baseline", "candidate"]}
    assert schedule[1] == {"case_id": case_ids[1], "arms": ["candidate", "baseline"]}
    assert sum(row["arms"][0] == "baseline" for row in schedule) == 16
    assert sum(row["arms"][0] == "candidate" for row in schedule) == 16
    assert sum(row["arms"][0] == "baseline" for row in schedule[::2]) == 8
    assert sum(row["arms"][0] == "baseline" for row in schedule[1::2]) == 8


def test_known_corpus_exact_match_blocks_validation_case(reviewed_inputs, tmp_path):
    dataset = json.loads(reviewed_inputs["validation_dataset"])
    text = unicodedata.normalize("NFC", dataset["cases"][0]["user_message"]).strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = tmp_path / "evals/structured_nlu/data/exposed.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"user_message": text}, ensure_ascii=False))
    inventory = {
        "kind": "known_nlu_corpus_inventory_v1",
        "scope": "repository_corpus_exact_match_only",
        "normalization": "NFC+strip",
        "source_files": {
            source.relative_to(tmp_path).as_posix(): hashlib.sha256(source.read_bytes()).hexdigest()
        },
        "normalized_message_sha256": [digest],
    }
    changed = dict(reviewed_inputs)
    changed["known_corpus_inventory"] = json.dumps(inventory).encode()
    with pytest.raises(ValueError, match="known-corpus exact exposure"):
        gate.qualify_validation(tmp_path, changed)


def test_stale_known_corpus_source_is_rejected(reviewed_inputs):
    inventory = json.loads(reviewed_inputs["known_corpus_inventory"])
    first = next(iter(inventory["source_files"]))
    inventory["source_files"][first] = "0" * 64
    changed = dict(reviewed_inputs)
    changed["known_corpus_inventory"] = json.dumps(inventory).encode()
    with pytest.raises(ValueError, match="known-corpus inventory differs"):
        gate.qualify_validation(gate.ROOT, changed)


def test_omitted_known_corpus_message_is_rejected(reviewed_inputs):
    inventory = json.loads(reviewed_inputs["known_corpus_inventory"])
    inventory["normalized_message_sha256"].pop()
    changed = dict(reviewed_inputs)
    changed["known_corpus_inventory"] = json.dumps(inventory).encode()
    with pytest.raises(ValueError, match="known-corpus inventory differs"):
        gate.qualify_validation(gate.ROOT, changed)


def test_changed_case_decision_content_is_rejected(reviewed_inputs):
    ledger = json.loads(reviewed_inputs["validation_case_decisions"])
    ledger = copy.deepcopy(ledger)
    ledger["decisions"][0]["case_sha256"] = "0" * 64
    changed = dict(reviewed_inputs)
    changed["validation_case_decisions"] = json.dumps(ledger).encode()
    with pytest.raises(ValueError, match="case decision content differs"):
        gate.qualify_validation(gate.ROOT, changed)


def test_duplicate_json_key_is_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        gate._strict_json(b'{"kind":"one","kind":"two"}')


def test_pair_schedule_rejects_duplicate_case_ids():
    with pytest.raises(ValueError, match="32 unique"):
        gate.pair_order(["same-case"] * 32)


def test_frozen_manifest_includes_transitive_script_imports():
    commit = gate._git(gate.ROOT, "rev-parse", "HEAD").decode().strip()
    manifest = gate._manifest(gate.ROOT, commit)
    assert {
        "scripts/run_ai_heldout_pair.py",
        "scripts/probe_gguf_structured_nlu.py",
        "scripts/gguf_action_field_split.py",
        "scripts/gguf_service_workflow_schema.py",
        "scripts/probe_chat_latency.py",
    } <= set(manifest)
    assert set(manifest) >= gate._current_source_names(gate.ROOT) - {
        name
        for name in gate._current_source_names(gate.ROOT)
        if name.startswith("experiments/internal_validation_pair_v1/")
    }


def test_worker_rejects_changed_frozen_source(tmp_path):
    repo = tmp_path / "arm"
    source = repo / "scripts/probe_chat_latency.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n")
    subprocess.run(("git", "init", "-q", str(repo)), check=True)
    subprocess.run(("git", "-C", str(repo), "add", "."), check=True)
    subprocess.run(
        (
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "test",
        ),
        check=True,
    )
    head = gate._git(repo, "rev-parse", "HEAD").decode().strip()
    manifest = {"scripts/probe_chat_latency.py": gate._file_sha(source)}
    worker._check_arm(repo, head, manifest, arm="baseline", expected_head=head)
    source.write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="frozen and clean"):
        worker._check_arm(repo, head, manifest, arm="baseline", expected_head=head)


def test_protocol_survives_separate_harness_and_protocol_commits(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    subprocess.run(("git", "init", "-q", str(baseline)), check=True)

    def commit(root, message):
        subprocess.run(("git", "-C", str(root), "add", "."), check=True)
        subprocess.run(
            (
                "git",
                "-C",
                str(root),
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
        return gate._git(root, "rev-parse", "HEAD").decode().strip()

    for relative in (
        "core/value.py",
        "evals/structured_nlu/metrics.py",
        "evals/structured_nlu/schema.py",
        "evals/structured_nlu/ai_heldout.py",
        *(
            path.as_posix()
            for key, path in gate.INPUT_PATHS.items()
            if key != "known_corpus_inventory"
        ),
    ):
        path = baseline / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test\n")
    baseline_commit = commit(baseline, "baseline")
    subprocess.run(
        ("git", "-C", str(baseline), "worktree", "add", "-qb", "candidate", str(candidate)),
        check=True,
    )
    for relative in (gate.SELECTION_RULE, gate.INPUT_PATHS["known_corpus_inventory"].as_posix()):
        path = candidate / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test\n")
    candidate_commit = commit(candidate, "candidate code")
    harness = candidate / gate.HARNESS_ROOT / "qualification.py"
    harness.parent.mkdir(parents=True)
    harness.write_text("test harness\n")
    commit(candidate, "harness")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fake model")
    monkeypatch.setattr(gate, "MODEL_SHA256", gate._file_sha(model))
    monkeypatch.setattr(
        gate,
        "qualify_validation",
        lambda root, inputs: (
            [f"case-{number:02}" for number in range(32)],
            {key: gate._sha(raw) for key, raw in inputs.items()},
        ),
    )
    paths = {name: tmp_path / name for name in ("result", "journal", "private", "receipt")}
    protocol = gate.build_protocol(
        baseline_root=baseline,
        baseline_commit=baseline_commit,
        candidate_root=candidate,
        candidate_commit=candidate_commit,
        model_path=model,
        output=paths["result"],
        journal=paths["journal"],
        private_dir=paths["private"],
        receipt=paths["receipt"],
    )
    protocol_path = candidate / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    commit(candidate, "protocol")
    assert (
        gate.preflight(
            protocol_path=protocol_path,
            baseline_root=baseline,
            candidate_root=candidate,
            model_path=model,
            output=paths["result"],
            journal=paths["journal"],
            private_dir=paths["private"],
            receipt=paths["receipt"],
        )[0]
        == protocol
    )
    source = candidate / "core/value.py"
    source.write_text("changed\n")
    with pytest.raises(ValueError, match="clean"):
        gate.preflight(
            protocol_path=protocol_path,
            baseline_root=baseline,
            candidate_root=candidate,
            model_path=model,
            output=paths["result"],
            journal=paths["journal"],
            private_dir=paths["private"],
            receipt=paths["receipt"],
        )
