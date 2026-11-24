"""Exercise surface form and contextual links separately from the review set."""

import pytest

from experiments.as_safety_atomic_edges_v12.pair_contract import FixedPair
from experiments.as_safety_atomic_edges_v12.run import _kiwi
from experiments.as_safety_contextual_part import contextual_source
from experiments.as_safety_v2.quotes import anchor_span, split_clauses
from experiments.as_safety_v2.source_lattice import SourceCandidate


@pytest.mark.parametrize(
    ("prefix", "candidate", "following", "expected"),
    [
        ("", "건조기 송풍구", "", True),
        ("", "건조기 송풍구 주변", "", False),
        ("평탄판은 전원 장치에 장착된 부품입니다. ", "평탄판", "", True),
        ("평탄판을 전원 장치 옆에 놓았습니다. ", "평탄판", "", False),
        ("평탄판은 전원 장치에 장착되지 않은 부품입니다. ", "평탄판", "", False),
        ("평탄판은 전원 장치에 장착된 부품입니다. 평탄판을 분리했습니다. ", "평탄판", "", False),
        (
            "평탄판은 전원 장치에 장착된 부품입니다. 평탄판은 제어 모터에 장착된 부품입니다. ",
            "평탄판",
            "",
            False,
        ),
        (
            "평탄판은 전원 장치에 장착된 부품입니다. ",
            "평탄판",
            " 연기의 출처는 모르겠습니다.",
            False,
        ),
    ],
)
def test_contextual_source(prefix, candidate, following, expected):
    hazard = "연기가 났습니다"
    utterance = f"{prefix}{candidate}에서 {hazard}.{following}"
    clauses = split_clauses(utterance)
    index = len(split_clauses(prefix)) + 1 if prefix else 1
    event = anchor_span({"quote": hazard, "clause_index": index}, clauses, field="event")
    span = anchor_span({"quote": candidate, "clause_index": index}, clauses, field="candidate")
    pair = FixedPair(utterance, clauses, event, SourceCandidate("test", **span))
    assert (contextual_source(pair, "observed", _kiwi()) is not None) == expected
