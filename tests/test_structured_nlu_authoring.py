from __future__ import annotations

import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import (
    SplitAssignmentManifest,
    ensure_output_outside_source,
    prepare_qualified_test_slice_from_authoring,
    score_qualified_test_slice_from_authoring,
    serialize_authoring_group_schema,
    serialize_gold_dataset,
    serialize_split_assignment_schema,
    verify_compiled_authoring_corpus,
)
from evals.structured_nlu.authoring import (
    compile_authoring_directory as compile_authoring_directory_with_manifest,
)
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.obligations import (
    build_official_authoring_obligations,
    serialize_official_authoring_obligations,
)
from evals.structured_nlu.review import (
    ANNOTATION_GUIDELINE_V1_FINGERPRINT,
    ANNOTATION_GUIDELINE_V1_ID,
    EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
    REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1,
    ReviewLedgerV1,
    evaluation_case_fingerprint,
    serialize_review_ledger_schema,
    verify_review_ledger,
)
from scripts.compile_structured_nlu_corpus import main as compile_corpus_main


def _write_group(
    path: Path,
    *,
    group_id: str,
    case_id: str,
    split: str = "development",
    message: str = "내일 면담하고 싶습니다.",
    accepted_date: str = "내일",
    review_status: str = "draft",
    register_split: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "authoring_schema_version": 2,
                "conversation_group_id": group_id,
                "scenario_key": "교수님:면담 예약",
                "provenance": "human_authored",
                "cases": [
                    {
                        "id": case_id,
                        "conversation_state": "collecting_appointment_info",
                        "current_fields": {},
                        "offered_alternative_times": [],
                        "user_message": message,
                        "labels": {
                            "intent": "appointment_booking",
                            "fields": {
                                "appointment_purpose": None,
                                "date": {"accepted_values": [accepted_date]},
                                "time": None,
                                "user_name": None,
                            },
                            "user_action": "provide_appointment_info",
                            "change_field": None,
                        },
                        "tags": ["single_field"],
                        "review_status": review_status,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if register_split:
        assignments_path = _split_assignments_path(path.parent)
        if assignments_path.is_file():
            manifest = json.loads(assignments_path.read_text(encoding="utf-8"))
        else:
            manifest = {
                "split_assignment_schema_version": 1,
                "dataset_version": 2,
                "assignments": [],
            }
        manifest["assignments"] = [
            assignment
            for assignment in manifest["assignments"]
            if assignment["conversation_group_id"] != group_id
        ]
        manifest["assignments"].append({"conversation_group_id": group_id, "split": split})
        manifest["assignments"].sort(key=lambda item: item["conversation_group_id"])
        _write_split_assignment_manifest(assignments_path, manifest["assignments"])


def _split_assignments_path(source_dir: Path) -> Path:
    return source_dir.parent / f"{source_dir.name}-split-assignments.v1.json"


def _write_split_assignment_manifest(path: Path, assignments: list[dict[str, str]]) -> None:
    path.write_text(
        json.dumps(
            {
                "split_assignment_schema_version": 1,
                "dataset_version": 2,
                "assignments": assignments,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_review_ledger(
    path: Path,
    dataset,
    *,
    case_ids: tuple[str, ...] | None = None,
    guideline_fingerprint: str = ANNOTATION_GUIDELINE_V1_FINGERPRINT,
) -> None:
    cases_by_id = {case.id: case for case in dataset.cases}
    selected_ids = case_ids or tuple(
        sorted(case.id for case in dataset.cases if case.split.value in {"validation", "test"})
    )
    path.write_text(
        json.dumps(
            {
                "review_ledger_schema_version": 1,
                "dataset_version": 2,
                "state_contract_version": 2,
                "annotation_guideline_id": ANNOTATION_GUIDELINE_V1_ID,
                "annotation_guideline_fingerprint": guideline_fingerprint,
                "case_fingerprint_algorithm": EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
                "ledger_fingerprint_algorithm": REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1,
                "governed_splits": ["validation", "test"],
                "entries": [
                    {
                        "case_id": case_id,
                        "case_fingerprint": evaluation_case_fingerprint(cases_by_id[case_id]),
                        "adjudicator_id": "project-owner",
                        "adjudicated_at": "2026-09-26T00:00:00+09:00",
                        "rationale": "작성 지침과 라이브 계약을 대조해 최종 정답을 확정했다.",
                        "decision": "approved",
                    }
                    for case_id in selected_ids
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def compile_authoring_directory(source_dir: Path):
    return compile_authoring_directory_with_manifest(
        source_dir,
        _split_assignments_path(source_dir),
    )


def _build_review_dataset(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "development.json",
        group_id="appointment.review-development",
        case_id="appointment.review-development.base",
        split="development",
    )
    _write_group(
        source_dir / "validation.json",
        group_id="appointment.review-validation",
        case_id="appointment.review-validation.base",
        split="validation",
        message="모레 면담하고 싶습니다.",
        accepted_date="모레",
        review_status="adjudicated",
    )
    _write_group(
        source_dir / "test.json",
        group_id="appointment.review-test",
        case_id="appointment.review-test.base",
        split="test",
        message="다음 주에 면담하고 싶습니다.",
        accepted_date="다음 주",
        review_status="adjudicated",
    )
    return compile_authoring_directory(source_dir)


def test_compiler_owns_split_and_scenario_at_the_semantic_group_level(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "date-request.json",
        group_id="appointment.date-request",
        case_id="appointment.date-request.base",
    )

    dataset = compile_authoring_directory(source_dir)
    case = dataset.cases[0]

    assert case.conversation_group_id == "appointment.date-request"
    assert case.split.value == "development"
    assert case.scenario_key == "교수님:면담 예약"
    assert case.provenance == "human_authored"


def test_authoring_group_cannot_override_the_frozen_split(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    _write_group(
        source_path,
        group_id="appointment.frozen-family",
        case_id="appointment.frozen-family.base",
        split="test",
    )
    decoded = json.loads(source_path.read_text(encoding="utf-8"))
    decoded["split"] = "development"
    source_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid authoring group"):
        compile_authoring_directory(source_dir)


def test_compiler_requires_every_group_to_have_exactly_one_split_assignment(
    tmp_path: Path,
):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "first.json",
        group_id="appointment.first-family",
        case_id="appointment.first-family.base",
    )
    _write_group(
        source_dir / "second.json",
        group_id="appointment.second-family",
        case_id="appointment.second-family.base",
        message="모레 면담하고 싶습니다.",
        accepted_date="모레",
    )
    _write_split_assignment_manifest(
        _split_assignments_path(source_dir),
        [
            {
                "conversation_group_id": "appointment.first-family",
                "split": "development",
            }
        ],
    )

    with pytest.raises(ValueError, match="missing=.*appointment.second-family"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_split_assignments_without_an_authoring_group(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.used-family",
        case_id="appointment.used-family.base",
    )
    _write_split_assignment_manifest(
        _split_assignments_path(source_dir),
        [
            {
                "conversation_group_id": "appointment.used-family",
                "split": "development",
            },
            {
                "conversation_group_id": "appointment.unused-family",
                "split": "validation",
            },
        ],
    )

    with pytest.raises(ValueError, match="unused=.*appointment.unused-family"):
        compile_authoring_directory(source_dir)


def test_split_assignment_change_changes_the_compiled_case_split(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.assignment-family",
        case_id="appointment.assignment-family.base",
    )
    assignments_path = _split_assignments_path(source_dir)

    development = compile_authoring_directory(source_dir)
    development_manifest = SplitAssignmentManifest.model_validate_json(
        assignments_path.read_text(encoding="utf-8")
    )
    _write_split_assignment_manifest(
        assignments_path,
        [
            {
                "conversation_group_id": "appointment.assignment-family",
                "split": "validation",
            }
        ],
    )
    validation = compile_authoring_directory(source_dir)
    validation_manifest = SplitAssignmentManifest.model_validate_json(
        assignments_path.read_text(encoding="utf-8")
    )

    assert development.cases[0].split.value == "development"
    assert validation.cases[0].split.value == "validation"
    assert serialize_gold_dataset(development) != serialize_gold_dataset(validation)
    assert development_manifest.fingerprint != validation_manifest.fingerprint


def test_split_assignment_fingerprint_ignores_json_order_and_whitespace():
    compact = SplitAssignmentManifest.model_validate_json(
        '{"split_assignment_schema_version":1,"dataset_version":2,'
        '"assignments":[{"conversation_group_id":"group.alpha","split":"development"},'
        '{"conversation_group_id":"group.beta","split":"test"}]}'
    )
    reordered = SplitAssignmentManifest.model_validate_json(
        """
        {
          "assignments": [
            {"split": "test", "conversation_group_id": "group.beta"},
            {"split": "development", "conversation_group_id": "group.alpha"}
          ],
          "dataset_version": 2,
          "split_assignment_schema_version": 1
        }
        """
    )

    assert compact.fingerprint == reordered.fingerprint


def test_compiler_sorts_output_independently_of_source_file_order(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "z.json",
        group_id="appointment.z-family",
        case_id="appointment.z-family.base",
        message="모레 면담하고 싶습니다.",
        accepted_date="모레",
    )
    _write_group(
        source_dir / "a.json",
        group_id="appointment.a-family",
        case_id="appointment.a-family.base",
    )

    dataset = compile_authoring_directory(source_dir)

    assert [case.id for case in dataset.cases] == [
        "appointment.a-family.base",
        "appointment.z-family.base",
    ]
    assert serialize_gold_dataset(dataset) == serialize_gold_dataset(dataset)


def test_compiler_canonicalizes_unordered_label_values_and_tags(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    _write_group(
        source_path,
        group_id="appointment.canonical-family",
        case_id="appointment.canonical-family.base",
    )
    decoded = json.loads(source_path.read_text(encoding="utf-8"))
    case = decoded["cases"][0]
    case["labels"]["fields"]["date"]["accepted_values"] = ["낼", "내일"]
    case["tags"] = ["single_field", "colloquial"]
    source_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    first = serialize_gold_dataset(compile_authoring_directory(source_dir))

    case["labels"]["fields"]["date"]["accepted_values"].reverse()
    case["tags"].reverse()
    source_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    second = serialize_gold_dataset(compile_authoring_directory(source_dir))

    assert first == second


def test_compiler_normalizes_equivalent_unicode_to_the_same_corpus(tmp_path: Path):
    nfc_source = tmp_path / "nfc"
    nfd_source = tmp_path / "nfd"
    for source_dir in (nfc_source, nfd_source):
        _write_group(
            source_dir / "group.json",
            group_id="appointment.unicode-family",
            case_id="appointment.unicode-family.base",
            message="내일 김하늘 교수님과 면담하고 싶습니다.",
        )
    nfd_path = nfd_source / "group.json"
    nfd_path.write_text(
        unicodedata.normalize("NFD", nfd_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    nfc_compiled = serialize_gold_dataset(compile_authoring_directory(nfc_source))
    nfd_compiled = serialize_gold_dataset(compile_authoring_directory(nfd_source))

    assert nfc_compiled == nfd_compiled
    assert unicodedata.is_normalized("NFC", nfd_compiled)


def test_compiler_rejects_values_that_duplicate_after_unicode_normalization(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    _write_group(
        source_path,
        group_id="appointment.unicode-duplicate-family",
        case_id="appointment.unicode-duplicate-family.base",
    )
    decoded = json.loads(source_path.read_text(encoding="utf-8"))
    decoded["cases"][0]["labels"]["fields"]["date"]["accepted_values"] = [
        "김하늘",
        unicodedata.normalize("NFD", "김하늘"),
    ]
    source_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid authoring group"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_one_group_owned_by_multiple_source_files(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "first.json",
        group_id="appointment.shared-family",
        case_id="appointment.shared-family.first",
    )
    _write_group(
        source_dir / "second.json",
        group_id="appointment.shared-family",
        case_id="appointment.shared-family.second",
        message="모레 면담하고 싶습니다.",
        accepted_date="모레",
    )

    with pytest.raises(ValueError, match="owned by one source file"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_exact_input_leakage_across_split_groups(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "development.json",
        group_id="appointment.development-family",
        case_id="appointment.development-family.base",
    )
    _write_group(
        source_dir / "test.json",
        group_id="appointment.test-family",
        case_id="appointment.test-family.base",
        split="test",
    )

    with pytest.raises(ValidationError, match="duplicate evaluation inputs are not allowed"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_symbolic_linked_source_file(tmp_path: Path):
    source_dir = tmp_path / "source"
    external_path = tmp_path / "external.json"
    _write_group(
        external_path,
        group_id="appointment.external-family",
        case_id="appointment.external-family.base",
        register_split=False,
    )
    source_dir.mkdir()
    (source_dir / "linked.json").symlink_to(external_path)
    _write_split_assignment_manifest(
        _split_assignments_path(source_dir),
        [{"conversation_group_id": "appointment.external-family", "split": "development"}],
    )

    with pytest.raises(ValueError, match="must not be symbolic links"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_symbolic_linked_split_assignment_manifest(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    _write_group(
        source_path,
        group_id="appointment.assignment-link-family",
        case_id="appointment.assignment-link-family.base",
    )
    assignments_path = _split_assignments_path(source_dir)
    external_path = tmp_path / "external-split-assignments.v1.json"
    assignments_path.replace(external_path)
    assignments_path.symlink_to(external_path)

    with pytest.raises(ValueError, match="manifest must not be a symbolic link"):
        compile_authoring_directory(source_dir)


def test_compiler_rejects_duplicate_split_assignments(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.duplicate-assignment-family",
        case_id="appointment.duplicate-assignment-family.base",
    )
    duplicate = {
        "conversation_group_id": "appointment.duplicate-assignment-family",
        "split": "development",
    }
    _write_split_assignment_manifest(
        _split_assignments_path(source_dir),
        [duplicate, duplicate],
    )

    with pytest.raises(ValueError, match="invalid split assignment manifest"):
        compile_authoring_directory(source_dir)


def test_compile_command_rejects_output_inside_source_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    _write_group(
        source_path,
        group_id="appointment.safe-family",
        case_id="appointment.safe-family.base",
    )
    original = source_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile_structured_nlu_corpus",
            "compile",
            str(source_dir),
            str(_split_assignments_path(source_dir)),
            str(source_path),
        ],
    )

    with pytest.raises(ValueError, match="must be outside"):
        compile_corpus_main()

    assert source_path.read_text(encoding="utf-8") == original


def test_compile_command_does_not_overwrite_the_split_assignment_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.protected-assignment-family",
        case_id="appointment.protected-assignment-family.base",
    )
    assignments_path = _split_assignments_path(source_dir)
    original = assignments_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile_structured_nlu_corpus",
            "compile",
            str(source_dir),
            str(assignments_path),
            str(assignments_path),
        ],
    )

    with pytest.raises(ValueError, match="must not replace"):
        compile_corpus_main()

    assert assignments_path.read_text(encoding="utf-8") == original


def test_verified_corpus_rejects_manual_compiled_edits(tmp_path: Path):
    source_dir = tmp_path / "source"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.verified-family",
        case_id="appointment.verified-family.base",
    )
    compiled_path.parent.mkdir()
    compiled_path.write_text(
        serialize_gold_dataset(compile_authoring_directory(source_dir)),
        encoding="utf-8",
    )
    decoded = json.loads(compiled_path.read_text(encoding="utf-8"))
    decoded["cases"][0]["user_message"] = "수동으로 바꾼 문장"
    compiled_path.write_text(
        json.dumps(decoded, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differs from the authoring sources"):
        verify_compiled_authoring_corpus(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
        )


def test_verification_compiles_and_hashes_one_source_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    _write_group(
        source_path,
        group_id="appointment.snapshot-family",
        case_id="appointment.snapshot-family.base",
    )
    compiled_path.parent.mkdir()
    compiled_path.write_text(
        serialize_gold_dataset(compile_authoring_directory(source_dir)),
        encoding="utf-8",
    )
    original_read_bytes = Path.read_bytes
    source_reads = 0

    def tracked_read_bytes(path: Path) -> bytes:
        nonlocal source_reads
        if path.resolve() == source_path.resolve():
            source_reads += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)

    verify_compiled_authoring_corpus(
        source_dir,
        _split_assignments_path(source_dir),
        compiled_path,
    )

    assert source_reads == 1


def test_qualified_scoring_revalidates_sources_immediately_before_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source_dir = tmp_path / "source"
    source_path = source_dir / "group.json"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    _write_group(
        source_path,
        group_id="appointment.score-family",
        case_id="appointment.score-family.base",
    )
    compiled_path.parent.mkdir()
    dataset = compile_authoring_directory(source_dir)
    compiled_path.write_text(serialize_gold_dataset(dataset), encoding="utf-8")
    _, source_fingerprint, split_assignment_fingerprint = verify_compiled_authoring_corpus(
        source_dir,
        _split_assignments_path(source_dir),
        compiled_path,
    )
    benchmark = SimpleNamespace(
        authoring_source_fingerprint=source_fingerprint,
        split_assignment_fingerprint=split_assignment_fingerprint,
        annotation_guideline_fingerprint="c" * 64,
        review_ledger_fingerprint="d" * 64,
        corpus_cases=dataset.cases,
    )
    monkeypatch.setattr(
        "evals.structured_nlu.review.verify_review_ledger",
        lambda *_args: SimpleNamespace(
            guideline_fingerprint="c" * 64,
            ledger_fingerprint="d" * 64,
        ),
    )
    monkeypatch.setattr(
        "evals.structured_nlu.benchmark._score_qualified_test_slice",
        lambda _benchmark, _predictions: "scored",
    )

    assert (
        score_qualified_test_slice_from_authoring(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
            tmp_path / "guideline.md",
            tmp_path / "review-ledger.json",
            benchmark,
            (),
        )
        == "scored"
    )

    decoded = json.loads(source_path.read_text(encoding="utf-8"))
    source_path.write_text(
        json.dumps(decoded, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source fingerprint does not match"):
        score_qualified_test_slice_from_authoring(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
            tmp_path / "guideline.md",
            tmp_path / "review-ledger.json",
            benchmark,
            (),
        )


def test_qualified_scoring_rejects_a_changed_split_assignment(tmp_path: Path):
    source_dir = tmp_path / "source"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.changed-assignment-family",
        case_id="appointment.changed-assignment-family.base",
    )
    assignments_path = _split_assignments_path(source_dir)
    compiled_path.parent.mkdir()
    dataset = compile_authoring_directory(source_dir)
    compiled_path.write_text(serialize_gold_dataset(dataset), encoding="utf-8")
    _, source_fingerprint, split_assignment_fingerprint = verify_compiled_authoring_corpus(
        source_dir, assignments_path, compiled_path
    )
    benchmark = SimpleNamespace(
        authoring_source_fingerprint=source_fingerprint,
        split_assignment_fingerprint=split_assignment_fingerprint,
        corpus_cases=dataset.cases,
    )

    _write_split_assignment_manifest(
        assignments_path,
        [
            {
                "conversation_group_id": "appointment.changed-assignment-family",
                "split": "validation",
            }
        ],
    )
    changed_dataset = compile_authoring_directory(source_dir)
    compiled_path.write_text(serialize_gold_dataset(changed_dataset), encoding="utf-8")

    with pytest.raises(ValueError, match="split assignment fingerprint does not match"):
        score_qualified_test_slice_from_authoring(
            source_dir,
            assignments_path,
            compiled_path,
            tmp_path / "guideline.md",
            tmp_path / "review-ledger.json",
            benchmark,
            (),
        )


def test_official_qualification_requires_verified_authoring_sources(tmp_path: Path):
    source_dir = tmp_path / "source"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    guideline_path = Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md")
    _write_review_ledger(ledger_path, dataset)
    compiled_path.parent.mkdir()
    compiled_path.write_text(
        serialize_gold_dataset(dataset),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="benchmark coverage is incomplete"):
        prepare_qualified_test_slice_from_authoring(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
            guideline_path,
            ledger_path,
        )


def test_output_boundary_resolves_symbolic_aliases(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    alias = tmp_path / "source-alias"
    alias.symlink_to(source_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="must be outside"):
        ensure_output_outside_source(source_dir, alias / "compiled.json")


def test_official_obligations_are_derived_from_the_v2_contract():
    obligations = build_official_authoring_obligations()
    counts = Counter(obligation.dimension for obligation in obligations)

    assert counts == {
        CoverageDimension.STATE_ACTION: 352,
        CoverageDimension.INTENT: 17,
        CoverageDimension.FIELD_PRESENT: 76,
        CoverageDimension.FIELD_ABSENT: 76,
        CoverageDimension.FIELD_OPTION: 76,
        CoverageDimension.CHANGE_FIELD: 42,
        CoverageDimension.ACTION_FIELD_PRESENT: 146,
        CoverageDimension.ACTION_FIELD_ABSENT: 68,
        CoverageDimension.DIFFICULTY_TAG: 12,
    }


def test_official_obligation_manifest_records_all_scenario_counts():
    manifest = json.loads(serialize_official_authoring_obligations())

    assert manifest["dimension_counts"] == {
        "action_field_absent": 68,
        "action_field_present": 146,
        "change_field": 42,
        "difficulty_tag": 12,
        "field_absent": 76,
        "field_option": 76,
        "field_present": 76,
        "intent": 17,
        "state_action": 352,
    }
    assert manifest["scenario_counts"] == {
        "고객센터:a/s 접수": 75,
        "고객센터:요금/약정 상담": 54,
        "고객센터:인터넷/통화 문제 문의": 72,
        "교수님:결석 사유 전달": 35,
        "교수님:과제 문의": 24,
        "교수님:면담 예약": 35,
        "배달:배달 지연 문의": 54,
        "배달:주문 변경": 55,
        "배달:환불/재배달 문의": 63,
        "시청:대형폐기물 배출": 52,
        "시청:여권 발급 문의": 62,
        "시청:주민등록 등본 문의": 60,
        "예약:미용실 예약": 53,
        "예약:병원 예약": 60,
        "예약:스터디룸 예약": 53,
        "예약:식당 예약": 46,
    }
    assert sum(manifest["scenario_counts"].values()) + 12 == manifest["obligation_count"]


def test_committed_official_obligation_manifest_matches_live_contracts():
    manifest_path = Path("evals/structured_nlu/manifests/coverage-obligations.v2.json")

    assert manifest_path.read_text(encoding="utf-8") == (serialize_official_authoring_obligations())


def test_committed_authoring_schema_matches_the_code_contract():
    schema_path = Path("evals/structured_nlu/authoring_group.schema.json")

    assert schema_path.read_text(encoding="utf-8") == serialize_authoring_group_schema()


def test_committed_split_assignment_schema_matches_the_code_contract():
    schema_path = Path("evals/structured_nlu/split_assignment.schema.json")

    assert schema_path.read_text(encoding="utf-8") == serialize_split_assignment_schema()


def test_split_assignment_schema_exposes_the_frozen_manifest_contract():
    schema = json.loads(serialize_split_assignment_schema())

    assert schema["$id"] == "urn:maeumcall:structured-nlu:split-assignments:v1"
    assert schema["properties"]["split_assignment_schema_version"]["const"] == 1
    assert schema["properties"]["dataset_version"]["const"] == 2
    assert schema["$defs"]["DatasetSplit"]["enum"] == [
        "development",
        "validation",
        "test",
    ]


def test_authoring_schema_exposes_runtime_string_and_scenario_constraints():
    schema = json.loads(serialize_authoring_group_schema())

    assert schema["$id"] == "urn:maeumcall:structured-nlu:authoring-group:v2"
    assert schema["properties"]["scenario_key"]["enum"] == sorted(EVALUATION_CONTRACTS)
    assert schema["$defs"]["AuthoringCase"]["properties"]["user_message"]["pattern"] == (r"\S")


def test_committed_review_ledger_schema_matches_the_code_contract():
    schema_path = Path("evals/structured_nlu/review_ledger.schema.json")

    assert schema_path.read_text(encoding="utf-8") == serialize_review_ledger_schema()


def test_review_ledger_schema_exposes_versioned_adjudication_contract():
    schema = json.loads(serialize_review_ledger_schema())

    assert schema["$id"] == "urn:maeumcall:structured-nlu:review-ledger:v1"
    properties = schema["properties"]
    assert properties["review_ledger_schema_version"]["const"] == 1
    assert properties["dataset_version"]["const"] == 2
    assert properties["state_contract_version"]["const"] == 2
    assert properties["annotation_guideline_id"]["const"] == ANNOTATION_GUIDELINE_V1_ID
    assert properties["annotation_guideline_fingerprint"]["const"] == (
        ANNOTATION_GUIDELINE_V1_FINGERPRINT
    )
    assert properties["case_fingerprint_algorithm"]["const"] == (
        EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1
    )
    assert properties["ledger_fingerprint_algorithm"]["const"] == (
        REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1
    )
    assert properties["governed_splits"]["prefixItems"] == [
        {"const": "validation", "type": "string"},
        {"const": "test", "type": "string"},
    ]
    assert properties["governed_splits"]["minItems"] == 2
    assert properties["governed_splits"]["maxItems"] == 2


def test_review_ledger_verifies_exact_validation_and_test_approvals(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    guideline_path = Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md")
    _write_review_ledger(ledger_path, dataset)

    verified = verify_review_ledger(dataset, guideline_path, ledger_path)

    assert verified.guideline_fingerprint == ANNOTATION_GUIDELINE_V1_FINGERPRINT
    assert verified.ledger_fingerprint == verified.ledger.fingerprint
    assert [entry.case_id for entry in verified.ledger.entries] == [
        "appointment.review-test.base",
        "appointment.review-validation.base",
    ]


def test_review_ledger_rejects_missing_and_unused_case_approvals(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    guideline_path = Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md")
    _write_review_ledger(
        ledger_path,
        dataset,
        case_ids=("appointment.review-validation.base",),
    )

    with pytest.raises(ValueError, match="must match validation and test cases exactly"):
        verify_review_ledger(dataset, guideline_path, ledger_path)

    decoded = json.loads(ledger_path.read_text(encoding="utf-8"))
    decoded["entries"].append(
        {
            "case_id": "appointment.review-unused.base",
            "case_fingerprint": "a" * 64,
            "adjudicator_id": "project-owner",
            "adjudicated_at": "2026-09-26T00:00:00+09:00",
            "rationale": "현재 corpus에 존재하지 않는 오래된 검수 항목이다.",
            "decision": "approved",
        }
    )
    decoded["entries"].sort(key=lambda item: item["case_id"])
    ledger_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="must match validation and test cases exactly"):
        verify_review_ledger(dataset, guideline_path, ledger_path)


def test_review_ledger_rejects_non_adjudicated_cases(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "validation.json",
        group_id="appointment.review-validation",
        case_id="appointment.review-validation.base",
        split="validation",
        review_status="reviewed",
    )
    _write_group(
        source_dir / "test.json",
        group_id="appointment.review-test",
        case_id="appointment.review-test.base",
        split="test",
        message="모레 면담하고 싶습니다.",
        accepted_date="모레",
        review_status="adjudicated",
    )
    dataset = compile_authoring_directory(source_dir)
    ledger_path = tmp_path / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)

    with pytest.raises(ValueError, match="requires adjudicated"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            ledger_path,
        )


def test_review_ledger_requires_both_governed_splits(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "validation.json",
        group_id="appointment.review-validation",
        case_id="appointment.review-validation.base",
        split="validation",
        review_status="adjudicated",
    )
    dataset = compile_authoring_directory(source_dir)
    ledger_path = tmp_path / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)

    with pytest.raises(ValueError, match=r"missing splits=\['test'\]"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            ledger_path,
        )


def test_review_ledger_rejects_an_approval_for_changed_case_content(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)
    decoded = json.loads(ledger_path.read_text(encoding="utf-8"))
    decoded["entries"][0]["case_fingerprint"] = "a" * 64
    ledger_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="different case content"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            ledger_path,
        )


def test_review_ledger_rejects_a_different_annotation_guideline(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    guideline_path = tmp_path / "annotation-guideline.v1.md"
    guideline_path.write_text("변경된 지침\n", encoding="utf-8")
    _write_review_ledger(ledger_path, dataset)

    with pytest.raises(ValueError, match="versioned guideline fingerprint"):
        verify_review_ledger(dataset, guideline_path, ledger_path)


def test_review_ledger_rejects_unsupported_schema_version(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v2.json"
    _write_review_ledger(ledger_path, dataset)
    decoded = json.loads(ledger_path.read_text(encoding="utf-8"))
    decoded["review_ledger_schema_version"] = 2
    ledger_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid review ledger"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            ledger_path,
        )


@pytest.mark.parametrize(
    "mutate_json",
    (
        lambda text: text.replace(
            '"review_ledger_schema_version": 1,',
            '"review_ledger_schema_version": 1, "review_ledger_schema_version": 1,',
            1,
        ),
        lambda text: text.replace(
            '"decision": "approved",',
            '"decision": "rejected", "decision": "approved",',
            1,
        ),
        lambda text: text.replace("{", '{"가": 1, "가": 2,', 1),
    ),
)
def test_review_ledger_rejects_duplicate_json_keys(tmp_path: Path, mutate_json):
    dataset = _build_review_dataset(tmp_path)
    ledger_path = tmp_path / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)
    ledger_path.write_text(
        mutate_json(ledger_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid review ledger"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            ledger_path,
        )


def test_review_ledger_rejects_a_symlinked_parent_directory(tmp_path: Path):
    dataset = _build_review_dataset(tmp_path)
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    ledger_path = real_dir / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)
    alias_dir = tmp_path / "alias"
    alias_dir.symlink_to(real_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="path must not contain symbolic links"):
        verify_review_ledger(
            dataset,
            Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md"),
            alias_dir / ledger_path.name,
        )


def test_official_scoring_revalidates_the_review_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset = _build_review_dataset(tmp_path)
    source_dir = tmp_path / "source"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    compiled_path.parent.mkdir()
    compiled_path.write_text(serialize_gold_dataset(dataset), encoding="utf-8")
    guideline_path = Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md")
    ledger_path = tmp_path / "review-ledger.v1.json"
    _write_review_ledger(ledger_path, dataset)
    _, source_fingerprint, split_fingerprint = verify_compiled_authoring_corpus(
        source_dir,
        _split_assignments_path(source_dir),
        compiled_path,
    )
    verified_review = verify_review_ledger(dataset, guideline_path, ledger_path)
    benchmark = SimpleNamespace(
        authoring_source_fingerprint=source_fingerprint,
        split_assignment_fingerprint=split_fingerprint,
        annotation_guideline_fingerprint=verified_review.guideline_fingerprint,
        review_ledger_fingerprint=verified_review.ledger_fingerprint,
        corpus_cases=dataset.cases,
    )
    monkeypatch.setattr(
        "evals.structured_nlu.benchmark._score_qualified_test_slice",
        lambda _benchmark, _predictions: "scored",
    )

    assert (
        score_qualified_test_slice_from_authoring(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
            guideline_path,
            ledger_path,
            benchmark,
            (),
        )
        == "scored"
    )

    decoded = json.loads(ledger_path.read_text(encoding="utf-8"))
    decoded["entries"][0]["rationale"] = "같은 사례를 다른 근거로 다시 승인했다."
    ledger_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="review ledger fingerprint does not match"):
        score_qualified_test_slice_from_authoring(
            source_dir,
            _split_assignments_path(source_dir),
            compiled_path,
            guideline_path,
            ledger_path,
            benchmark,
            (),
        )


def test_review_ledger_rejects_duplicate_or_unsorted_entries():
    base_entry = {
        "case_id": "appointment.review-validation.base",
        "case_fingerprint": "a" * 64,
        "adjudicator_id": "project-owner",
        "adjudicated_at": "2026-09-26T00:00:00+09:00",
        "rationale": "작성 지침과 라이브 계약을 대조했다.",
        "decision": "approved",
    }
    payload = {
        "review_ledger_schema_version": 1,
        "dataset_version": 2,
        "state_contract_version": 2,
        "annotation_guideline_id": ANNOTATION_GUIDELINE_V1_ID,
        "annotation_guideline_fingerprint": ANNOTATION_GUIDELINE_V1_FINGERPRINT,
        "case_fingerprint_algorithm": EVALUATION_CASE_FINGERPRINT_ALGORITHM_V1,
        "ledger_fingerprint_algorithm": REVIEW_LEDGER_FINGERPRINT_ALGORITHM_V1,
        "governed_splits": ["validation", "test"],
        "entries": [base_entry, base_entry],
    }
    with pytest.raises(ValidationError, match="must be unique"):
        ReviewLedgerV1.model_validate(payload)

    payload["entries"] = [
        {**base_entry, "case_id": "appointment.review-validation.second"},
        base_entry,
    ]
    with pytest.raises(ValidationError, match="sorted by case_id"):
        ReviewLedgerV1.model_validate(payload)


def test_review_ledger_cli_checks_schema_and_case_approvals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    dataset = _build_review_dataset(tmp_path)
    compiled_path = tmp_path / "gold-dataset.v2.json"
    ledger_path = tmp_path / "review-ledger.v1.json"
    schema_path = Path("evals/structured_nlu/review_ledger.schema.json")
    guideline_path = Path("evals/structured_nlu/guidelines/annotation-guideline.v1.md")
    compiled_path.write_text(serialize_gold_dataset(dataset), encoding="utf-8")
    _write_review_ledger(ledger_path, dataset)

    monkeypatch.setattr(
        sys,
        "argv",
        ["compile-structured-nlu-corpus", "check-review-schema", str(schema_path)],
    )
    assert compile_corpus_main() == 0

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile-structured-nlu-corpus",
            "check-review",
            str(tmp_path / "source"),
            str(_split_assignments_path(tmp_path / "source")),
            str(compiled_path),
            str(guideline_path),
            str(ledger_path),
        ],
    )
    assert compile_corpus_main() == 0
