"""Check the grounded candidate's evidence boundary without a model call."""

import json

import pytest

from scripts.probe_as_safety_grounded_attribution import (
    CONFIRM,
    DIRECT,
    NORMAL,
    journal_schema,
    route_grounded,
    validate_grounded,
)

MESSAGE = "수리할 제습기의 센서가 고장 났습니다. 옆 선풍기 본체에서 연기가 났습니다."


def response(owner: str | None, relation: str, event: str = "observed") -> str:
    return json.dumps(
        {
            "product_index": 1,
            "hazard_index": 2,
            "product_anchor": "제습기",
            "hazard_owner_anchor": owner,
            "target_relation": relation,
            "event_status": event,
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("owner", "relation", "event", "expected"),
    [
        ("선풍기", "other", "observed", NORMAL),
        ("선풍기", "current", "observed", CONFIRM),
        (None, "current", "observed", CONFIRM),
        ("선풍기", "other", "uncertain", NORMAL),
        ("선풍기", "current", "nonoccurring", NORMAL),
    ],
)
def test_grounded_route_requires_matching_source_anchor(owner, relation, event, expected):
    decision = validate_grounded(response(owner, relation, event), MESSAGE)
    assert route_grounded(decision) == expected
    assert not any(isinstance(value, str) and "풍기" in value for value in decision.values())
    schema = journal_schema(MESSAGE)
    assert set(decision) == set(schema["required"])
    for field, value in decision.items():
        assert value in schema["properties"][field]["enum"]


def test_same_product_anchor_allows_direct_route():
    message = "수리할 공기청정기의 화면이 꺼집니다. 공기청정기 전원선에서 연기가 났습니다."
    raw = response("공기청정기", "current").replace("제습기", "공기청정기")
    assert route_grounded(validate_grounded(raw, message)) == DIRECT


@pytest.mark.parametrize(
    "raw",
    [
        response("청소기", "other"),
        response("", "other"),
        response("선풍기", "other").replace('"product_index": 1', '"product_index": 3'),
        response("선풍기", "other").replace(
            '"product_anchor": "제습기"', '"product_anchor": "선풍기"'
        ),
    ],
)
def test_non_source_or_invalid_anchor_is_rejected(raw):
    with pytest.raises(ValueError):
        validate_grounded(raw, MESSAGE)
