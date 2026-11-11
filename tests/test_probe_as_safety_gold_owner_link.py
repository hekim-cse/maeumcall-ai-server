"""Contract tests for the reviewed-owner link-only diagnostic prompt."""

import pytest

from scripts.probe_as_safety_gold_owner_link import (
    gold_owner_link_messages,
    gold_owner_link_schema,
    validate_gold_owner_link,
)
from scripts.probe_as_safety_oracle_relation import relation_messages, relation_schema

UTTERANCE = "수리 맡길 공기청정기 옆에 가습기가 있습니다. 가습기의 전원선에서 연기가 났습니다."
BASE = {
    "product_index": 1,
    "hazard_index": 2,
    "event_status": "observed",
    "target_mention": "공기청정기",
    "hazard_event_mention": "가습기의 전원선에서 연기가 났습니다",
}
OWNER = {"owner_clause_index": 2, "owner_mention": "가습기의 전원선"}


def test_only_two_owner_lines_differ_from_prior_oracle_prompt() -> None:
    before = relation_messages(UTTERANCE, **BASE)
    after = gold_owner_link_messages(UTTERANCE, **BASE, **OWNER)
    added = (
        "검수된 위험 출처 근거 문장: 2. 가습기의 전원선에서 연기가 났습니다.\n"
        "검수된 위험 출처 구절: 가습기의 전원선\n"
    )
    assert after[0] == before[0]
    assert after[1]["content"].replace(added, "") == before[1]["content"]
    assert after[1]["content"].count(added) == 1
    assert "accepted_link_kinds" not in after[1]["content"]
    assert "expected_relation" not in after[1]["content"]


def test_re06_conditional_owner_does_not_rewrite_occurrence() -> None:
    utterance = (
        "제 커피머신 물통을 청소하다가 바닥에 자국을 봤어요. "
        "액체가 새는 건지 세척할 때 흘린 물인지 구분이 안 됩니다."
    )
    messages = gold_owner_link_messages(
        utterance,
        product_index=1,
        hazard_index=2,
        event_status="uncertain",
        target_mention="커피머신 물통",
        hazard_event_mention="액체가 새는 건지 세척할 때 흘린 물인지 구분이 안 됩니다",
        owner_clause_index=1,
        owner_mention="커피머신 물통",
    )
    assert "고정된 위험 발생 상태: uncertain" in messages[1]["content"]
    assert "검수된 위험 출처 구절: 커피머신 물통" in messages[1]["content"]


@pytest.mark.parametrize(
    ("owner_clause_index", "owner_mention"),
    [
        (0, "가습기의 전원선"),
        (True, "가습기의 전원선"),
        (3, "가습기의 전원선"),
        (1, "가습기의 전원선"),
        (2, ""),
        (2, " "),
        (2, "전기레인지"),
    ],
)
def test_invalid_owner_anchor_rejected(owner_clause_index: int, owner_mention: str) -> None:
    with pytest.raises(ValueError, match="reviewed owner quote"):
        gold_owner_link_messages(
            UTTERANCE,
            **BASE,
            owner_clause_index=owner_clause_index,
            owner_mention=owner_mention,
        )


def test_owner_quote_must_occur_once_in_its_clause() -> None:
    utterance = "선풍기가 켜졌고 선풍기에서 연기가 났습니다."
    with pytest.raises(ValueError, match="reviewed owner quote"):
        gold_owner_link_messages(
            utterance,
            product_index=1,
            hazard_index=1,
            event_status="observed",
            target_mention="선풍기",
            hazard_event_mention="연기가 났습니다",
            owner_clause_index=1,
            owner_mention="선풍기",
        )


def test_schema_and_response_validation_match_prior_relation_contract() -> None:
    assert gold_owner_link_schema() == relation_schema()
    assert validate_gold_owner_link('{"source_relation":"other"}') == {"source_relation": "other"}
    assert validate_gold_owner_link('{"source_relation":"unknown"}') == {
        "source_relation": "unknown"
    }
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        validate_gold_owner_link('{"source_relation":"current","source_relation":"other"}')
    with pytest.raises(ValueError, match="fields differ"):
        validate_gold_owner_link('{"source_relation":"other","link_kind":"explicit_other"}')
    with pytest.raises(ValueError, match="finite choices"):
        validate_gold_owner_link('{"source_relation":1}')
