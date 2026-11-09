"""Protect the candidate's unanimity and abstention boundary."""

import pytest

from scripts.as_safety_consensus_v1 import CONFIRM, DIRECT, NORMAL, consensus_route


@pytest.mark.parametrize(
    ("baseline", "relation", "expected"),
    [
        (DIRECT, DIRECT, DIRECT),
        (NORMAL, NORMAL, NORMAL),
        (CONFIRM, CONFIRM, CONFIRM),
        (DIRECT, NORMAL, CONFIRM),
        (NORMAL, DIRECT, CONFIRM),
        (DIRECT, None, CONFIRM),
        (NORMAL, None, CONFIRM),
        (None, None, CONFIRM),
    ],
)
def test_unanimity_or_abstention(baseline, relation, expected):
    assert consensus_route(baseline, relation) == expected


def test_unknown_route_is_rejected():
    with pytest.raises(ValueError, match="unrecognized"):
        consensus_route("unknown", DIRECT)
