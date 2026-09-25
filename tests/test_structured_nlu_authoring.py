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
    compile_authoring_directory,
    ensure_output_outside_source,
    prepare_qualified_test_slice_from_authoring,
    score_qualified_test_slice_from_authoring,
    serialize_authoring_group_schema,
    serialize_gold_dataset,
    verify_compiled_authoring_corpus,
)
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.obligations import (
    build_official_authoring_obligations,
    serialize_official_authoring_obligations,
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
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "authoring_schema_version": 1,
                "conversation_group_id": group_id,
                "split": split,
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
                        "review_status": "draft",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_compiler_owns_split_and_scenario_at_the_semantic_group_level(tmp_path: Path):
    source_dir = tmp_path / "source"
    _write_group(
        source_dir / "appointment" / "date-request.json",
        group_id="appointment.date-request",
        case_id="appointment.date-request.base",
    )

    dataset = compile_authoring_directory(source_dir)
    case = dataset.cases[0]

    assert case.conversation_group_id == "appointment.date-request"
    assert case.split.value == "development"
    assert case.scenario_key == "교수님:면담 예약"
    assert case.provenance == "human_authored"


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
    )
    source_dir.mkdir()
    (source_dir / "linked.json").symlink_to(external_path)

    with pytest.raises(ValueError, match="must not be symbolic links"):
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
        ["compile_structured_nlu_corpus", "compile", str(source_dir), str(source_path)],
    )

    with pytest.raises(ValueError, match="must be outside"):
        compile_corpus_main()

    assert source_path.read_text(encoding="utf-8") == original


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
        verify_compiled_authoring_corpus(source_dir, compiled_path)


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

    verify_compiled_authoring_corpus(source_dir, compiled_path)

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
    _, source_fingerprint = verify_compiled_authoring_corpus(source_dir, compiled_path)
    benchmark = SimpleNamespace(
        authoring_source_fingerprint=source_fingerprint,
        corpus_cases=dataset.cases,
    )
    monkeypatch.setattr(
        "evals.structured_nlu.benchmark._score_qualified_test_slice",
        lambda _benchmark, _predictions: "scored",
    )

    assert (
        score_qualified_test_slice_from_authoring(
            source_dir,
            compiled_path,
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
            compiled_path,
            benchmark,
            (),
        )


def test_official_qualification_requires_verified_authoring_sources(tmp_path: Path):
    source_dir = tmp_path / "source"
    compiled_path = tmp_path / "compiled" / "gold-dataset.v2.json"
    _write_group(
        source_dir / "group.json",
        group_id="appointment.qualification-family",
        case_id="appointment.qualification-family.base",
    )
    compiled_path.parent.mkdir()
    compiled_path.write_text(
        serialize_gold_dataset(compile_authoring_directory(source_dir)),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a complete corpus"):
        prepare_qualified_test_slice_from_authoring(source_dir, compiled_path)


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


def test_committed_official_obligation_manifest_matches_live_contracts():
    manifest_path = Path("evals/structured_nlu/manifests/coverage-obligations.v2.json")

    assert manifest_path.read_text(encoding="utf-8") == (serialize_official_authoring_obligations())


def test_committed_authoring_schema_matches_the_code_contract():
    schema_path = Path("evals/structured_nlu/authoring_group.schema.json")

    assert schema_path.read_text(encoding="utf-8") == serialize_authoring_group_schema()


def test_authoring_schema_exposes_runtime_string_and_scenario_constraints():
    schema = json.loads(serialize_authoring_group_schema())

    assert schema["$id"] == "urn:maeumcall:structured-nlu:authoring-group:v1"
    assert schema["properties"]["scenario_key"]["enum"] == sorted(EVALUATION_CONTRACTS)
    assert schema["$defs"]["AuthoringCase"]["properties"]["user_message"]["pattern"] == (r"\S")
