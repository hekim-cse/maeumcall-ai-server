"""Exercise compact registered aliases and scoped device descriptions."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_device_context import device_context_source, unique_contextual_split
from experiments.as_safety_device_part import attached_device_source
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("prefix", "candidate", "following", "expected"),
    [
        ("", "전원장치발열체", "", True),
        ("", "전원장치발열체", " 전원 장치는 장비가 아니라 보관함 이름입니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 두 대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 네 대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 2대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 열한 대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 두세 대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 2~3대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 백 대 있습니다.", False),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 한 대 있습니다.", True),
        ("", "전원장치발열체", " 전원장치라는 이름의 기기가 1대 있습니다.", True),
        ("공기순환기는 지금 사용 중인 기기입니다. ", "공기순환기 여과격자", "", True),
        ("", "공기순환기 여과격자", "", False),
        ("공기순환기는 지금 사용 중인 기기입니다. ", "공기순환기여과격자", "", False),
        ("공기순환기는 지금 사용 중인 기기입니다. ", "공기순환기 여과격자 보관함", "", False),
        (
            "공기순환기는 지금 사용 중인 기기입니다. ",
            "공기순환기 여과격자",
            " 공기순환기는 기기가 아닙니다.",
            False,
        ),
        (
            "공기순환기는 지금 사용 중인 기기입니다. ",
            "공기순환기 여과격자",
            " 공기순환기라는 이름의 기기가 두 대 있습니다.",
            False,
        ),
        (
            "공기순환기는 지금 사용 중인 기기입니다. ",
            "공기순환기 여과격자",
            " 연기 출처는 모르겠습니다.",
            False,
        ),
    ],
)
def test_compact_and_contextual_nominal_evidence(prefix, candidate, following, expected):
    hazard = "연기가 났습니다"
    utterance = f"{prefix}{candidate}에서 {hazard}.{following}"
    clauses = split_clauses(utterance)
    index = 2 if prefix else 1
    event = anchor_span({"clause_index": index, "quote": hazard}, clauses, field="event")
    source = anchor_span({"clause_index": index, "quote": candidate}, clauses, field="candidate")
    pair = FixedPair(utterance, clauses, event, SourceCandidate("unit", **source))
    assert attached_device_source(pair, "observed", _kiwi()) is None
    result = device_context_source(pair, "observed", _kiwi())
    assert (result is not None) is expected
    if result:
        assert clauses[index - 1][result.source_start : result.source_end] == candidate


def test_alias_collision_remains_ambiguous():
    assert not unique_contextual_split(
        "전원장치발열체",
        frozenset({"전원장치", "전원 장치"}),
        frozenset(),
    )
