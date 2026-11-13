"""Source-only candidate generation and separate coverage accounting."""

import inspect
import json

import pytest

from experiments.as_safety_v2.candidate_ids import (
    _trim_edges,
    generate_candidates,
    measure_candidate_coverage,
    stage1_id_messages,
    stage1_id_schema,
    validate_stage1_ids,
)
from experiments.as_safety_v2.json_contract import ValidationError

MESSAGE = "접수할 노트북이 켜지지 않습니다. 친구 태블릿의 충전기에서 연기가 났습니다."
TARGET = {"product_index": 1, "target_mention": "노트북"}


def test_unicode_whitespace_and_punctuation_edges_preserve_inner_nbsp():
    clause = "\u00a0“태블릿\u00a0충전기”\u00a0"
    start, end = _trim_edges(clause, 0, len(clause))
    assert clause[start:end] == "태블릿\u00a0충전기"


def test_generated_candidates_have_no_unicode_whitespace_edges():
    message = "접수할\u00a0노트북에서\u00a0연기가 났습니다."
    generated = generate_candidates(message).generated
    assert any("\u00a0" in candidate.quote for candidate in generated)
    assert all(
        not candidate.quote[0].isspace() and not candidate.quote[-1].isspace()
        for candidate in generated
    )


def _id_for(candidate_set, quote, clause_index):
    matches = [
        item.id
        for item in candidate_set.candidates
        if item.quote == quote and item.clause_index == clause_index
    ]
    assert len(matches) == 1
    return matches[0]


def _selection(candidate_set, **changes):
    selected = {
        "event_id": _id_for(candidate_set, "연기가 났습니다", 2),
        "subject_id": _id_for(candidate_set, "친구 태블릿의 충전기에서", 2),
        "owner_id": _id_for(candidate_set, "친구 태블릿의", 2),
        "owner_kind": "explicit",
    }
    selected.update(changes)
    return json.dumps(selected, ensure_ascii=False)


def test_generator_is_deterministic_bounded_and_never_accepts_gold():
    assert "gold" not in inspect.signature(generate_candidates).parameters
    first = generate_candidates(MESSAGE)
    second = generate_candidates(MESSAGE)
    assert first == second
    assert first.source_sha256
    assert len(first.candidates) <= 192
    assert [item.id for item in first.generated] == [
        f"P{number:03}" for number in range(1, len(first.generated) + 1)
    ]
    for item in first.candidates:
        clause = MESSAGE.split(". ")[item.clause_index - 1]
        assert clause[item.start : item.end] == item.quote


def test_candidate_prompt_and_schema_use_only_source_derived_ids_and_target_a():
    candidates = generate_candidates(MESSAGE)
    messages = stage1_id_messages(MESSAGE, candidates, **TARGET)
    prompt = "\n".join(message["content"] for message in messages)
    assert MESSAGE in prompt
    assert "검수된 접수 대상 A: 1. 노트북" in prompt
    assert "원문에서 자동 생성한 후보 목록:" in prompt
    assert "expected_relation" not in prompt and "gold_relation" not in prompt
    assert '"quote":"원문"' not in prompt
    schema = stage1_id_schema(candidates)
    assert schema["additionalProperties"] is False
    assert (
        set(schema["required"])
        == set(schema["properties"])
        == {"event_id", "subject_id", "owner_id", "owner_kind"}
    )
    assert schema["properties"]["event_id"]["enum"] == [
        None,
        *(item.id for item in candidates.candidates),
    ]


def test_selection_resolves_to_exact_spans_and_keeps_raw_ids():
    candidates = generate_candidates(MESSAGE)
    result = validate_stage1_ids(_selection(candidates), MESSAGE, candidates, **TARGET)
    assert result["selected_ids"]["event_id"].startswith("P")
    assert result["extraction"]["event_span"]["quote"] == "연기가 났습니다"
    assert result["extraction"]["owner_span"]["quote"] == "친구 태블릿의"
    assert result["extraction"]["owner_kind"] == "explicit"


def test_coverage_reports_selection_truncation_and_generation_misses_separately():
    message = "접수할 TV가 고장입니다. 멀티탭 연기가 났습니다."
    candidates = generate_candidates(message, max_candidates=1)
    assert candidates.truncated
    assert candidates.candidates[0].quote == "접수할"
    reviewed = {
        "event_span": [{"clause_index": 1, "quote": "접수할"}],
        "subject_span": [{"clause_index": 1, "quote": "TV가"}],
        "owner_span": [{"clause_index": 2, "quote": "원문에 없는 값"}],
    }
    original = candidates.candidates
    report = measure_candidate_coverage(candidates, reviewed)
    assert candidates.candidates == original  # labels do not alter prompt candidates
    assert report["denominator"] == 3
    assert report["selected_hits"] == 1
    assert report["generated_hits"] == 2
    assert report["truncated_hits"] == 1
    assert report["by_field"] == {
        "event_span": "selected",
        "subject_span": "truncated",
        "owner_span": "not_generated",
    }
    assert report["candidate_count"] == 1
    assert report["generated_count"] > 1
    assert [report["by_span"][field][0]["status"] for field in reviewed] == [
        "selected",
        "truncated",
        "not_generated",
    ]
    assert "quote" not in report["by_span"]["owner_span"][0]


def test_korean_particle_variants_are_exact_source_candidates():
    candidates = generate_candidates(MESSAGE)
    report = measure_candidate_coverage(
        candidates,
        {
            "event_span": [{"clause_index": 2, "quote": "연기가 났습니다"}],
            "subject_span": [{"clause_index": 2, "quote": "친구 태블릿의 충전기"}],
            "owner_span": [{"clause_index": 2, "quote": "친구 태블릿"}],
        },
    )
    assert report["by_field"]["event_span"] == "selected"
    assert report["by_field"]["subject_span"] == "selected"
    assert report["by_field"]["owner_span"] == "selected"


def test_window_limit_is_reported_as_generation_recall_loss():
    candidates = generate_candidates(MESSAGE, max_window_tokens=1)
    report = measure_candidate_coverage(
        candidates,
        {
            "event_span": [{"clause_index": 2, "quote": "연기가"}],
            "subject_span": [{"clause_index": 2, "quote": "태블릿의 충전기"}],
            "owner_span": [{"clause_index": 2, "quote": "친구"}],
        },
    )
    assert report["by_field"]["subject_span"] == "not_generated"
    assert report["denominator"] == 3


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        ({"event_id": "P999"}, "candidate_id_invalid", "event_id"),
        ({"event_id": True}, "candidate_id_invalid", "event_id"),
        ({"owner_id": None}, "owner_consistency_invalid", "owner_id"),
        ({"owner_kind": "unresolved"}, "owner_consistency_invalid", "owner_id"),
        ({"owner_kind": "other"}, "owner_kind_invalid", "owner_kind"),
        ({"cue_id": "P001"}, "fields_invalid", "stage1_ids"),
    ],
)
def test_invalid_selection_reports_finite_field_error(changes, code, field):
    candidates = generate_candidates(MESSAGE)
    with pytest.raises(ValidationError) as caught:
        validate_stage1_ids(_selection(candidates, **changes), MESSAGE, candidates, **TARGET)
    assert (caught.value.code, caught.value.field) == (code, field)


def test_id_not_in_bounded_subset_cannot_be_selected():
    candidates = generate_candidates(MESSAGE, max_candidates=1)
    assert len(candidates.generated) > 1
    raw = json.dumps(
        {
            "event_id": candidates.generated[1].id,
            "subject_id": None,
            "owner_id": None,
            "owner_kind": "unresolved",
        }
    )
    with pytest.raises(ValidationError) as caught:
        validate_stage1_ids(raw, MESSAGE, candidates, **TARGET)
    assert (caught.value.code, caught.value.field) == ("candidate_id_invalid", "event_id")


def test_source_mismatch_and_bad_generation_bounds_are_rejected():
    candidates = generate_candidates(MESSAGE)
    with pytest.raises(ValidationError, match="candidate_source_invalid"):
        stage1_id_messages(MESSAGE + " 추가", candidates, **TARGET)
    for kwargs in ({"max_candidates": 0}, {"max_candidates": 257}, {"max_window_tokens": 0}):
        with pytest.raises(ValueError):
            generate_candidates(MESSAGE, **kwargs)
