"""Reverse only the enumerated status definitions in the v12 user message."""

from __future__ import annotations

from experiments.as_safety_atomic_edges_v12 import pair_contract

ORIGINAL = (
    "relation_status는 supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함), "
    "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
    "insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음) 중 하나입니다."
)
REVERSED = (
    "relation_status는 insufficient(가능성은 있으나 원문만으로 출처를 확정할 수 없음), "
    "unsupported(이 후보는 현상 자체이거나 원문과 모순되어 출처가 될 수 없음), "
    "supported(원문이 이 후보를 사건의 물리적 출처로 뒷받침함) 중 하나입니다."
)


def messages(pair: pair_contract.FixedPair) -> list[dict[str, str]]:
    baseline = pair_contract.messages(pair)
    original = baseline[1]["content"]
    if original.count(ORIGINAL) != 1 or REVERSED in original:
        raise ValueError("baseline status options differ")
    return [baseline[0], {"role": "user", "content": original.replace(ORIGINAL, REVERSED)}]
