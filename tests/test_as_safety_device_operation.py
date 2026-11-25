"""Verify that a source candidate has affirmative operation evidence for the same device."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_device_context import device_context_source
from experiments.as_safety_device_operation import device_operation_source
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("before", "source", "event", "after", "expected"),
    [
        ("분진추출기의 전원 버튼을 눌렀습니다.", "분진추출기 절연막", "연기가 났습니다", "", True),
        (
            "분진추출기의 전원 스위치를 켰습니다.",
            "분진추출기 차폐판",
            "불꽃이 튀었습니다",
            "",
            True,
        ),
        (
            "가루수거기의 전원 스위치를 켰습니다.",
            "분진추출기 차폐판",
            "불꽃이 튀었습니다",
            "",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 누를 예정입니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "",
            False,
        ),
        (
            "설명서에 분진추출기의 전원 버튼을 눌렀다고 적혀 있습니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "",
            False,
        ),
        ("작업실의 전원 버튼을 눌렀습니다.", "작업실 절연막", "연기가 났습니다", "", False),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막 옆 선반",
            "연기가 났습니다",
            "",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막",
            "연기가 보였습니다",
            "",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "분진추출기는 보관 구역 이름입니다.",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "분진추출기라는 이름의 장비가 두 대 있습니다.",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "연기 출처는 모르겠습니다.",
            False,
        ),
        (
            "분진추출기의 전원 버튼을 눌렀습니다.",
            "분진추출기 절연막",
            "연기가 났습니다",
            "소리 출처는 모르겠습니다.",
            True,
        ),
    ],
)
def test_affirmative_operation_names_exact_device(before, source, event, after, expected):
    utterance = f"{before} {source}에서 {event}. {after}".strip()
    clauses = split_clauses(utterance)
    event_span = anchor_span({"clause_index": 2, "quote": event}, clauses, field="event")
    source_span = anchor_span({"clause_index": 2, "quote": source}, clauses, field="source")
    pair = FixedPair(utterance, clauses, event_span, SourceCandidate("unit", **source_span))

    kiwi = _kiwi()
    assert device_context_source(pair, "observed", kiwi) is None
    result = device_operation_source(pair, "observed", kiwi)
    assert (result is not None) is expected
    if result:
        assert clauses[1][result.source_start : result.source_end] == source
    assert device_operation_source(pair, "uncertain", kiwi) is None
