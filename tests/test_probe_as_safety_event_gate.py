"""A source-grounded gate must abstain without weakening clear direct reports."""

import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.probe_as_safety_event_gate import (
    CONFIRM,
    DIRECT,
    NORMAL,
    gate_direct_safety,
)


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("휴대용 선풍기 충전 포트에서 불꽃이 여러 번 튀었어요.", DIRECT),
        ("노트북 하판이 솟아올라 평평하게 놓이지 않아요.", DIRECT),
        ("전동 공구 배터리에서 액체가 새어 나옵니다.", DIRECT),
        ("기기에서 연기가 피어오릅니다.", DIRECT),
        ("기기에서 연기가 났습니다.", DIRECT),
        ("충전하면 본체가 뜨거워져요.", DIRECT),
        ("연기는 나지 않지만 배터리가 부풀었습니다.", DIRECT),
        ("화면에 아이콘이 뜨고 본체에서 연기가 납니다.", DIRECT),
        ("전원 케이블 피복이 갈라져 금속선이 보여요.", DIRECT),
        ("배터리가 부풀면 어떻게 해야 하나요?", NORMAL),
        ("연기는 나지 않습니다.", NORMAL),
        ("화면에 불꽃 모양 아이콘이 떠요.", NORMAL),
        ("배터리 팽창을 확인하는 방법이 궁금해요.", NORMAL),
        ("배터리 덮개가 들뜬 것처럼 보입니다.", CONFIRM),
        ("본체에서 타는 냄새가 나는 듯해요.", CONFIRM),
        ("팬 소음이 커졌어요. 배터리는 부풀지 않았습니다.", CONFIRM),
    ],
)
def test_source_event_gate(utterance: str, expected: str) -> None:
    decision = gate_direct_safety(utterance, {"route": DIRECT, "evidence_index": 1})
    assert decision.route == expected


def test_non_direct_model_decision_is_not_promoted() -> None:
    assert (
        gate_direct_safety("배터리가 부풀었습니다.", {"route": NORMAL, "evidence_index": 1}).route
        == NORMAL
    )


@pytest.mark.parametrize("index", [None, 0, 2, True, "1"])
def test_direct_decision_requires_valid_source_index(index: object) -> None:
    with pytest.raises(ValueError):
        gate_direct_safety("연기가 납니다.", {"route": DIRECT, "evidence_index": index})


def test_exposed_q5_development_regression_keeps_denominators() -> None:
    root = Path("evals/structured_nlu/data/ai_heldout")
    cases = json.loads((root / "nlu-safety-confirmation-reviewed.v1.json").read_text())["cases"]
    rows = json.loads(
        (root / "as-safety-exposed-q4-q5-development-pair-result.v1.json").read_text()
    )["results"]["q5"]
    assert len(cases) == len(rows) == 32
    assert [case["id"] for case in cases] == [row["case_id"] for row in rows]
    decisions = [
        gate_direct_safety(case["user_message"], row) for case, row in zip(cases, rows, strict=True)
    ]
    assert [
        Counter(item.route for item in decisions[start:stop])
        for start, stop in ((0, 12), (12, 20), (20, 32))
    ] == [
        Counter({DIRECT: 10, NORMAL: 2}),
        Counter({CONFIRM: 6, NORMAL: 2}),
        Counter({NORMAL: 8, CONFIRM: 4}),
    ]
    assert [
        case["id"][-4:]
        for case, row, decision in zip(cases, rows, decisions, strict=True)
        if row["route"] != decision.route
    ] == ["cf14", "cf20", "cf21", "cf23", "cf26", "cf29", "cf31", "cf32"]
