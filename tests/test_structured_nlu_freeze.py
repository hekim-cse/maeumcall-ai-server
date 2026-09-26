from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import evals.structured_nlu.authoring as authoring_module
import evals.structured_nlu.freeze as freeze_module
from evals.structured_nlu.authoring import VerifiedAuthoringBundle, serialize_gold_dataset
from evals.structured_nlu.benchmark import (
    OFFICIAL_BENCHMARK_PROFILE,
    OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
    BenchmarkCoverageReport,
    QualifiedTestSlice,
)
from evals.structured_nlu.coverage_v3 import OFFICIAL_COVERAGE_CONTRACT_V3
from evals.structured_nlu.freeze import (
    FREEZE_RECORD_FINGERPRINT_ALGORITHM_V1,
    FreezeArtifactPathsV1,
    build_freeze_record,
    create_freeze_record_file,
    load_freeze_record,
    prepare_qualified_test_slice_from_freeze,
    score_qualified_test_slice_from_freeze,
    serialize_freeze_record,
    serialize_freeze_record_schema,
    verify_freeze_record,
    write_new_freeze_record,
)
from evals.structured_nlu.schema import EvaluationCase, GoldDataset


def _case(case_id: str, split: str, message: str, value: str) -> EvaluationCase:
    return EvaluationCase.model_validate(
        {
            "id": case_id,
            "conversation_group_id": case_id.rsplit(".", 1)[0],
            "split": split,
            "scenario_key": "교수님:면담 예약",
            "conversation_state": "collecting_appointment_info",
            "current_fields": {},
            "offered_alternative_times": [],
            "user_message": message,
            "labels": {
                "intent": "appointment_booking",
                "fields": {
                    "appointment_purpose": None,
                    "date": {"accepted_values": [value]},
                    "time": None,
                    "user_name": None,
                },
                "user_action": "provide_appointment_info",
                "change_field": None,
            },
            "tags": ["single_field"],
            "provenance": "human_authored",
            "review_status": "draft" if split == "development" else "adjudicated",
        }
    )


def _dataset() -> GoldDataset:
    return GoldDataset(
        dataset_version=2,
        state_contract_version=2,
        cases=(
            _case("freeze.dev.base", "development", "내일 면담하고 싶습니다.", "내일"),
            _case("freeze.validation.base", "validation", "모레 면담하고 싶습니다.", "모레"),
            _case("freeze.test.base", "test", "금요일에 면담하고 싶습니다.", "금요일"),
        ),
    )


def _fake_verified_inputs(dataset: GoldDataset):
    validation_cases = tuple(case for case in dataset.cases if case.split.value == "validation")
    test_cases = tuple(case for case in dataset.cases if case.split.value == "test")
    validation_coverage = BenchmarkCoverageReport(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        split=validation_cases[0].split,
        case_count=len(validation_cases),
        issues=(),
    )
    test_coverage = BenchmarkCoverageReport(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        split=test_cases[0].split,
        case_count=len(test_cases),
        issues=(),
    )
    bundle = VerifiedAuthoringBundle(
        dataset=dataset,
        group_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        review=SimpleNamespace(
            guideline_fingerprint="c" * 64,
            ledger_fingerprint="d" * 64,
        ),
        contrast=SimpleNamespace(fingerprint="e" * 64),
    )
    benchmark = QualifiedTestSlice(
        profile_id=OFFICIAL_BENCHMARK_PROFILE.profile_id,
        profile_fingerprint=OFFICIAL_BENCHMARK_PROFILE_FINGERPRINT,
        dataset_version=2,
        state_contract_version=2,
        dataset_fingerprint="1" * 64,
        split=test_cases[0].split,
        cases=test_cases,
        coverage=test_coverage,
        validation_coverage=validation_coverage,
        coverage_contract_fingerprint=OFFICIAL_COVERAGE_CONTRACT_V3.fingerprint,
        contrast_manifest_fingerprint="e" * 64,
        authoring_source_fingerprint="a" * 64,
        split_assignment_fingerprint="b" * 64,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_fingerprint="2" * 64,
        corpus_cases=dataset.cases,
    )
    return bundle, benchmark, "f" * 64


def _init_repo(tmp_path: Path, dataset: GoldDataset) -> tuple[Path, FreezeArtifactPathsV1, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    files = {
        "data/source/group.json": "{}\n",
        "data/split-assignments.v1.json": "{}\n",
        "data/compiled/gold-dataset.v2.json": serialize_gold_dataset(dataset),
        "guidelines/annotation-guideline.v1.md": "# guideline\n",
        "data/review-ledger.v1.json": "{}\n",
        "data/contrast-groups.v1.json": "{}\n",
        "manifests/coverage-obligations.v3.json": "{}\n",
    }
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "freeze@example.com")
    _git(repo, "config", "user.name", "Freeze Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "test: freeze inputs")
    commit = _git(repo, "rev-parse", "HEAD").strip()
    paths = FreezeArtifactPathsV1(
        group_source_root="data/source",
        split_assignment_path="data/split-assignments.v1.json",
        compiled_corpus_path="data/compiled/gold-dataset.v2.json",
        annotation_guideline_path="guidelines/annotation-guideline.v1.md",
        review_ledger_path="data/review-ledger.v1.json",
        contrast_manifest_path="data/contrast-groups.v1.json",
        obligation_manifest_path="manifests/coverage-obligations.v3.json",
    )
    return repo, paths, commit


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _build_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dataset = _dataset()
    repo, paths, commit = _init_repo(tmp_path, dataset)
    verified_inputs = _fake_verified_inputs(dataset)
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: verified_inputs,
    )
    record = build_freeze_record(
        repo_root=repo,
        freeze_id="structured-nlu-corpus-r0001",
        freeze_revision=1,
        previous_record_path=None,
        input_git_revision=commit,
        paths=paths,
    )
    return repo, paths, record, verified_inputs


def test_freeze_record_binds_the_committed_benchmark_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, paths, record, verified_inputs = _build_record(tmp_path, monkeypatch)

    assert record.input_git_revision.commit == _git(repo, "rev-parse", "HEAD").strip()
    assert record.paths == paths
    assert record.inventory.case_count == 3
    assert record.inventory.group_count == 3
    assert record.benchmark.obligation_count == 1562
    assert record.record_fingerprint_algorithm == FREEZE_RECORD_FINGERPRINT_ALGORITHM_V1

    record_path = repo / "freezes" / "structured-nlu-corpus-r0001.json"
    write_new_freeze_record(record_path, record)
    _git(repo, "add", "freezes/structured-nlu-corpus-r0001.json")
    _git(repo, "commit", "-m", "test: add freeze record")
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: verified_inputs,
    )
    verified = verify_freeze_record(repo_root=repo, record_path=record_path)

    assert verified.record == record
    assert verified.benchmark == verified_inputs[1]
    assert (
        prepare_qualified_test_slice_from_freeze(
            repo_root=repo,
            record_path=record_path,
        )
        == verified_inputs[1]
    )
    forged = replace(verified_inputs[1], dataset_fingerprint="9" * 64)
    with pytest.raises(ValueError, match="does not match the explicit freeze record"):
        score_qualified_test_slice_from_freeze(
            repo_root=repo,
            record_path=record_path,
            benchmark=forged,
            predictions=(),
        )


def test_freeze_record_rejects_self_hash_and_lineage_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _, _, record, _ = _build_record(tmp_path, monkeypatch)
    payload = record.model_dump(mode="json")
    payload["freeze_id"] = "structured-nlu-corpus-forged"
    with pytest.raises(ValidationError, match="record fingerprint does not match"):
        freeze_module.CorpusFreezeRecordV1.model_validate(payload)

    payload = record.model_dump(mode="json")
    payload["freeze_revision"] = 2
    with pytest.raises(ValidationError, match="require a previous record fingerprint"):
        freeze_module.CorpusFreezeRecordV1.model_validate(payload)


def test_later_freeze_revision_requires_the_exact_previous_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, paths, first, _ = _build_record(tmp_path, monkeypatch)
    first_path = repo / "freezes" / "revision-1.json"
    write_new_freeze_record(first_path, first)
    _git(repo, "add", "freezes/revision-1.json")
    _git(repo, "commit", "-m", "test: commit first freeze revision")

    second = build_freeze_record(
        repo_root=repo,
        freeze_id=first.freeze_id,
        freeze_revision=2,
        previous_record_path=first_path,
        input_git_revision="HEAD",
        paths=paths,
    )
    assert second.previous_freeze_record_fingerprint == first.record_fingerprint

    with pytest.raises(ValueError, match="explicit previous record"):
        build_freeze_record(
            repo_root=repo,
            freeze_id=first.freeze_id,
            freeze_revision=2,
            previous_record_path=None,
            input_git_revision="HEAD",
            paths=paths,
        )
    with pytest.raises(ValueError, match="different freeze lineage"):
        build_freeze_record(
            repo_root=repo,
            freeze_id="different-lineage",
            freeze_revision=2,
            previous_record_path=first_path,
            input_git_revision="HEAD",
            paths=paths,
        )


def test_freeze_record_parser_rejects_duplicate_json_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, _, record, _ = _build_record(tmp_path, monkeypatch)
    record_path = repo / "freezes" / "duplicate.json"
    record_path.parent.mkdir()
    serialized = serialize_freeze_record(record)
    record_path.write_text(
        serialized.replace(
            "{\n",
            '{\n  "freeze_record_schema_version": 999,\n',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid freeze record"):
        load_freeze_record(record_path)


def test_freeze_record_creation_is_create_only_and_preserves_existing_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, _, record, _ = _build_record(tmp_path, monkeypatch)
    record_path = repo / "freezes" / "record.json"
    write_new_freeze_record(record_path, record)
    original = record_path.read_bytes()

    with pytest.raises(FileExistsError, match="already exists"):
        write_new_freeze_record(record_path, record)

    assert record_path.read_bytes() == original


def test_official_verification_rejects_an_uncommitted_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, _, record, verified_inputs = _build_record(tmp_path, monkeypatch)
    record_path = repo / "freezes" / "uncommitted.json"
    write_new_freeze_record(record_path, record)
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: verified_inputs,
    )

    with pytest.raises(ValueError, match="exactly one artifact"):
        verify_freeze_record(repo_root=repo, record_path=record_path)


def test_official_verification_rejects_record_bytes_changed_after_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo, _, record, verified_inputs = _build_record(tmp_path, monkeypatch)
    record_path = repo / "freezes" / "committed.json"
    write_new_freeze_record(record_path, record)
    _git(repo, "add", "freezes/committed.json")
    _git(repo, "commit", "-m", "test: commit freeze record")
    record_path.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: verified_inputs,
    )

    with pytest.raises(ValueError, match="exact Git HEAD blob"):
        verify_freeze_record(repo_root=repo, record_path=record_path)


def test_freeze_creation_rejects_changed_inputs_after_the_git_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset = _dataset()
    repo, paths, commit = _init_repo(tmp_path, dataset)
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: _fake_verified_inputs(dataset),
    )
    (repo / paths.annotation_guideline_path).write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="differs from the input Git revision"):
        build_freeze_record(
            repo_root=repo,
            freeze_id="structured-nlu-corpus-r0001",
            freeze_revision=1,
            previous_record_path=None,
            input_git_revision=commit,
            paths=paths,
        )


def test_freeze_creation_requires_current_head_and_a_clean_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset = _dataset()
    repo, paths, first_commit = _init_repo(tmp_path, dataset)
    monkeypatch.setattr(
        freeze_module,
        "_verify_freeze_input_snapshot",
        lambda _snapshot: _fake_verified_inputs(dataset),
    )
    (repo / "history.md").write_text("next commit\n", encoding="utf-8")
    _git(repo, "add", "history.md")
    _git(repo, "commit", "-m", "test: advance head")

    with pytest.raises(ValueError, match="current HEAD"):
        build_freeze_record(
            repo_root=repo,
            freeze_id="structured-nlu-corpus-r0001",
            freeze_revision=1,
            previous_record_path=None,
            input_git_revision=first_commit,
            paths=paths,
        )

    (repo / "untracked.txt").write_text("not committed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clean Git worktree"):
        build_freeze_record(
            repo_root=repo,
            freeze_id="structured-nlu-corpus-r0001",
            freeze_revision=1,
            previous_record_path=None,
            input_git_revision="HEAD",
            paths=paths,
        )


def test_freeze_paths_reject_aliases_parent_traversal_and_source_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    with pytest.raises(ValidationError, match="repository-relative"):
        FreezeArtifactPathsV1(
            group_source_root="data/source",
            split_assignment_path="../split.json",
            compiled_corpus_path="data/compiled.json",
            annotation_guideline_path="guideline.md",
            review_ledger_path="review.json",
            contrast_manifest_path="contrast.json",
            obligation_manifest_path="obligations.json",
        )

    repo, paths, record, _ = _build_record(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="must not replace"):
        create_freeze_record_file(
            repo_root=repo,
            output_path=Path(paths.group_source_root) / "record.json",
            freeze_id="structured-nlu-corpus-r0001",
            freeze_revision=1,
            previous_record_path=None,
            input_git_revision="HEAD",
            paths=paths,
        )

    alias = repo.parent / "repo-alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="Git worktree root"):
        verify_freeze_record(
            repo_root=alias,
            record_path=Path("freezes/missing.json"),
        )

    real_output_dir = repo / "real-freezes"
    real_output_dir.mkdir()
    output_alias = repo / "freeze-alias"
    output_alias.symlink_to(real_output_dir, target_is_directory=True)
    with pytest.raises(ValueError, match="must not contain symbolic links"):
        write_new_freeze_record(output_alias / "record.json", record)


def test_official_prepare_requires_an_explicit_existing_record(tmp_path: Path):
    with pytest.raises(ValueError, match="Git verification failed"):
        prepare_qualified_test_slice_from_freeze(
            repo_root=tmp_path,
            record_path=Path("freezes/latest.json"),
        )
    assert not hasattr(authoring_module, "prepare_qualified_test_slice_from_authoring")
    assert not hasattr(authoring_module, "score_qualified_test_slice_from_authoring")


def test_committed_freeze_schema_matches_the_code_contract():
    path = Path("evals/structured_nlu/freeze_record.schema.json")
    serialized = serialize_freeze_record_schema()

    assert path.read_text(encoding="utf-8") == serialized
    schema = json.loads(serialized)
    assert schema["$id"] == "urn:maeumcall:structured-nlu:freeze-record:v1"
    assert schema["properties"]["freeze_record_schema_version"]["const"] == 1
    assert schema["properties"]["qualified_splits"]["prefixItems"] == [
        {"const": "validation", "type": "string"},
        {"const": "test", "type": "string"},
    ]
