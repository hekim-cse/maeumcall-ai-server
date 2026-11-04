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
