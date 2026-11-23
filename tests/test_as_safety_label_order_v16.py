"""Keep the label-order intervention to one exact user-message span."""

import json

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10 import probe
from experiments.as_safety_atomic_edges_v12 import pair_contract
from experiments.as_safety_atomic_edges_v12 import run as v12
from experiments.as_safety_atomic_edges_v16 import run as v16
from experiments.as_safety_atomic_edges_v16 import variant
from experiments.as_safety_atomic_edges_v16 import verify as v16_verify


def test_all_reviewed_pairs_change_only_status_definition_order():
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    for case_id, candidate_id in v12.ORDER:
        pair = pair_contract.fixed_pair(cases[case_id], candidate_id, v12._kiwi())
        baseline = pair_contract.messages(pair)
        changed = variant.messages(pair)
        assert changed[0] == baseline[0]
        assert (
            changed[1]["content"].replace(variant.REVERSED, variant.ORIGINAL)
            == baseline[1]["content"]
        )
        assert changed[1]["content"].count(variant.REVERSED) == 1
        original_request = json.loads(
            v4.request_bytes(baseline, pair_contract.schema(pair), policy, "variant")
        )
        changed_request = json.loads(
            v4.request_bytes(changed, pair_contract.schema(pair), policy, "variant")
        )
        changed_request["messages"] = original_request["messages"]
        assert changed_request == original_request


@pytest.mark.parametrize("field", ["model", "response_format", "seed"])
def test_request_guard_rejects_any_second_variable(field):
    cases = probe.cases()
    policy = v5._policy({"request_policy": v1.REQUEST_POLICY})
    original = v12._requests(cases, policy)
    changed = v16._requests(cases, policy)
    name = "PC01-P014"
    payload = json.loads(changed[name])
    payload[field] = "different"
    changed[name] = json.dumps(payload, ensure_ascii=False).encode()
    with pytest.raises(ValueError, match="more than label order changed"):
        v16._single_change(changed, original)


def _valid_rows():
    protocol = {
        "request_policy": {"max_tokens": 320},
        "max_context_tokens": 4096,
        "request_sha256": {name: "a" * 64 for name in v16_verify.ORDER},
    }
    header = {
        "event": "header",
        "protocol_sha256": "p" * 64,
        "input_tokens": {name: 400 for name in v16_verify.ORDER},
    }
    row = {
        "event": "result",
        "call": v16_verify.ORDER[0],
        "request_sha256": "a" * 64,
        "finish_reason": "stop",
        "error_code": None,
        "http_status": None,
        "raw_sha256": "b" * 64,
        "raw_bytes": 42,
        "request_latency_ms": 12.0,
    }
    return protocol, [header, row]


def test_journal_guard_accepts_complete_first_result():
    protocol, rows = _valid_rows()
    assert v16_verify._rows(rows, "p" * 64, protocol) == rows[0]["input_tokens"]


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda rows: rows[0]["input_tokens"].update({"PC01-P014": 4096}), "input token"),
        (lambda rows: rows[1].update({"finish_reason": "length"}), "length finish"),
        (lambda rows: rows[1].update({"raw_sha256": "wrong"}), "raw response metadata"),
        (lambda rows: rows[1].update({"raw_bytes": 0}), "raw response metadata"),
        (lambda rows: rows[1].update({"unexpected": True}), "journal result shape"),
    ],
)
def test_journal_guard_rejects_invalid_or_partial_result(change, error):
    protocol, rows = _valid_rows()
    change(rows)
    with pytest.raises(ValueError, match=error):
        v16_verify._rows(rows, "p" * 64, protocol)


def test_journal_guard_stops_after_first_error():
    protocol, rows = _valid_rows()
    rows[1]["error_code"] = "fields_invalid"
    rows.append({**rows[1], "call": v16_verify.ORDER[1]})
    with pytest.raises(ValueError, match="continued after error"):
        v16_verify._rows(rows, "p" * 64, protocol)


def test_existing_journal_blocks_rerun_before_loading_protocol(tmp_path, monkeypatch):
    journal = tmp_path / "partial.jsonl"
    journal.write_text("")
    monkeypatch.setattr(v16, "JOURNAL", journal)
    monkeypatch.setattr(v16, "PRIVATE_DIR", tmp_path / "absent")

    def forbidden():
        pytest.fail("partial run must not reach protocol or model")

    monkeypatch.setattr(v16, "_load_protocol", forbidden)
    with pytest.raises(FileExistsError, match="partial run"):
        v16.run(tmp_path / "model.gguf")
