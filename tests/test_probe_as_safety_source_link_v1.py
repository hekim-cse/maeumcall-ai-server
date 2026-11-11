"""Synthetic counterexamples for the conservative source-link candidate."""

from __future__ import annotations

import pytest

from scripts.probe_as_safety_source_link_v1 import EVIDENCE_KINDS, RELATIONS, link_source


@pytest.mark.parametrize(
    ("utterance", "target", "target_clause", "owner", "owner_clause", "relation", "evidence"),
    [
        (
            "수리할 노트북에서 연기가 났습니다.",
            "수리할 노트북",
            1,
            "노트북",
            1,
            "current",
            "same_anchored_entity",
        ),
        (
            "수리할 노트북의 배터리에서 연기가 났습니다.",
            "수리할 노트북",
            1,
            "노트북의 배터리",
            1,
            "current",
            "target_possesses_owner",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 다른 노트북에서 연기가 났습니다.",
            "노트북",
            1,
            "다른 노트북",
            2,
            "other",
            "explicit_other",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 동료가 사용하는 같은 모델에서 연기가 났습니다.",
            "노트북",
            1,
            "동료가 사용하는 같은 모델",
            2,
            "other",
            "explicit_other",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 친구의 노트북에서 연기가 났습니다.",
            "노트북",
            1,
            "친구의 노트북",
            2,
            "other",
            "explicit_other",
        ),
        (
            "친구가 쓰는 노트북을 수리하려고 합니다. 친구가 쓰는 노트북에서 연기가 났습니다.",
            "친구가 쓰는 노트북",
            1,
            "친구가 쓰는 노트북",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 노트북의 배터리가 이상합니다. 다른 쪽 배터리에서 연기가 났습니다.",
            "노트북",
            1,
            "다른 쪽 배터리",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 다른 노트북이 있습니다. 다른 노트북에서 연기가 났습니다.",
            "수리할 다른 노트북",
            1,
            "다른 노트북",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 노트북에서 연기가 났습니다.",
            "노트북",
            1,
            "노트북",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 본체에서 연기가 났습니다.",
            "노트북",
            1,
            "본체",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 노트북은 켜지지 않습니다. 태블릿의 배터리에서 연기가 났습니다.",
            "노트북",
            1,
            "태블릿의 배터리",
            2,
            "unknown",
            "unresolved",
        ),
        (
            "수리할 노트북 옆에서 연기가 났습니다.",
            "노트북",
            1,
            "옆",
            1,
            "unknown",
            "unresolved",
        ),
    ],
)
def test_source_link_only_commits_on_explicit_identity_or_distinctness(
    utterance, target, target_clause, owner, owner_clause, relation, evidence
):
    """Assert decisions on new generic examples, including same-name other items."""
    result = link_source(
        utterance,
        target_mention=target,
        target_clause_index=target_clause,
        owner_mention=owner,
        owner_clause_index=owner_clause,
    )
    assert result == {"source_relation": relation, "evidence_kind": evidence}
    assert result["source_relation"] in RELATIONS
    assert result["evidence_kind"] in EVIDENCE_KINDS


def test_absent_owner_abstains_without_guessing():
    """An unresolved source must not turn into current by default."""
    assert link_source(
        "수리할 노트북 옆에서 연기가 났습니다.",
        target_mention="노트북",
        target_clause_index=1,
        owner_mention=None,
        owner_clause_index=None,
    ) == {"source_relation": "unknown", "evidence_kind": "unresolved"}


@pytest.mark.parametrize(
    ("owner", "owner_clause"),
    [("노트북", None), (None, 1), (" ", 1), ("태블릿", 1), ("노트북", 0)],
)
def test_inconsistent_or_unanchored_owner_is_rejected(owner, owner_clause):
    """Prevent a guessed or malformed source span from becoming evidence."""
    with pytest.raises(ValueError):
        link_source(
            "수리할 노트북에서 연기가 났습니다.",
            target_mention="노트북",
            target_clause_index=1,
            owner_mention=owner,
            owner_clause_index=owner_clause,
        )


def test_duplicate_target_mention_is_rejected():
    """A repeated noun in one clause cannot identify a unique physical item."""
    with pytest.raises(ValueError):
        link_source(
            "노트북 옆의 노트북에서 연기가 났습니다.",
            target_mention="노트북",
            target_clause_index=1,
            owner_mention="노트북",
            owner_clause_index=1,
        )
