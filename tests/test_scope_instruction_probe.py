import json
import urllib.request

import pytest

from scripts.probe_gguf_scope_instruction import (
    INSTRUCTION,
    inject_scope_instruction,
    paired_summary,
)


def test_scope_instruction_changes_only_system_message():
    payload = {
        "model": "example",
        "messages": [
            {"role": "system", "content": "base system"},
            {"role": "user", "content": "private user text"},
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        "http://127.0.0.1:18080/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    injected = json.loads(inject_scope_instruction(request).data)
    assert injected["messages"][0]["content"] == "base system\n" + INSTRUCTION
    assert injected["messages"][1] == payload["messages"][1]
    assert injected["temperature"] == payload["temperature"]
    assert json.loads(request.data) == payload


def test_paired_summary_requires_both_modes_for_each_case():
    with pytest.raises(ValueError, match="every case, repetition and mode"):
        paired_summary([], ["B01"], 1)


def test_paired_summary_separates_contract_from_action_and_polarity():
    def observation(case_id, mode, *, valid, action_match):
        return {
            "case_id": case_id,
            "repetition": 1,
            "mode": mode,
            "contract_valid": valid,
            "action_draft_match": action_match if valid else None,
            "field_draft_match": False if valid else None,
            "draft_label_mismatch_fields": ["user_action"] if valid else None,
            "attempts": [{"prompt_tokens": 1, "cached_prompt_tokens": 0, "completion_tokens": 1}],
            "elapsed_seconds": 1.0,
        }

    observations = [
        observation("B01", "baseline", valid=True, action_match=True),
        observation("B01", "scope_instruction", valid=True, action_match=True),
        observation("B02", "baseline", valid=True, action_match=False),
        observation("B02", "scope_instruction", valid=True, action_match=True),
    ]
    summary = paired_summary(observations, ["B01", "B02"], 1)
    assert summary["by_mode"]["baseline"]["contract_passes"] == 2
    assert summary["by_mode"]["baseline"]["action_draft_matches_on_contract_pass"] == 1
    assert summary["by_polarity"]["scope_instruction"]["near_scope_out"]["contract_passes"] == 1
    assert summary["paired_contract_and_action_discordance"] == {
        "baseline_only": [],
        "scope_instruction_only": ["B02.r1"],
    }
