"""Guard the oracle boundary, safe routing, frozen preflight and private raw files."""

from __future__ import annotations

import argparse
import json
import stat

import pytest

from experiments.as_safety_oracle_event_v1 import run as runner
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4.cases import load_cases

MESSAGE = (
    "수리할 로봇청소기 바퀴가 헛돕니다. "
    "탁상 조명에서 연기가 났고, 로봇청소기 전원선에서 불꽃이 튀었습니다."
)
CASE = {
    "id": "ES01",
    "user_message": MESSAGE,
    "target": {"clause_index": 1, "quote": "로봇청소기"},
    "events": [
        {
            "event_span": {"clause_index": 2, "quote": "연기가 났고"},
            "occurrence": "observed",
            "hazard_owner_span": {"clause_index": 2, "quote": "NEVER-LEAK-GOLD-OWNER"},
            "owner_to_target": "other",
        },
        {
            "event_span": {"clause_index": 2, "quote": "불꽃이 튀었습니다"},
            "occurrence": "observed",
            "hazard_owner_span": {"clause_index": 2, "quote": "NEVER-LEAK-GOLD-OWNER"},
            "owner_to_target": "current",
        },
    ],
    "expected_route": "safety_action_required",
    "overflow": False,
}


def _completion(owner: str, relation: str, *, finish_reason: str = "stop") -> Completion:
    return Completion(
        json.dumps(
            {
                "hazard_owner_span": {"clause_index": 2, "quote": owner},
                "owner_to_target": relation,
            },
            ensure_ascii=False,
        ),
        finish_reason,
    )


def test_gold_owner_and_route_never_enter_requests_and_raw_is_private(tmp_path) -> None:
    replies = iter(
        [
            _completion("탁상 조명", "other"),
            _completion("로봇청소기 전원선", "current"),
        ]
    )
    requests = []

    def fake(messages, schema, *, policy):
        requests.append((messages, schema, policy))
        return next(replies)

    row = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert len(requests) == row["request_count"] == 2
    assert row["route"] == "safety_action_required"
    assert [stage["owner_to_target"] for stage in row["stage2"]] == ["other", "current"]
    assert "NEVER-LEAK-GOLD-OWNER" not in json.dumps(requests, ensure_ascii=False, default=str)
    assert "safety_action_required" not in json.dumps(requests, ensure_ascii=False, default=str)
    assert "quote" not in row["stage2"][0]["event_span"]
    assert "quote" not in row["stage2"][0]["hazard_owner_span"]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "ES01-stage2-1.json.txt",
        "ES01-stage2-2.json.txt",
    ]
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in tmp_path.iterdir())
    scoring_case = {
        **CASE,
        "events": [
            {**CASE["events"][0], "hazard_owner_span": {"clause_index": 2, "quote": "탁상 조명"}},
            {
                **CASE["events"][1],
                "hazard_owner_span": {"clause_index": 2, "quote": "로봇청소기 전원선"},
            },
        ],
    }
    summary = runner.summarize([row], [scoring_case])
    assert summary["relation_correct"] == 2
    assert summary["owner_exact_correct"] == 2
    assert summary["category_counts"]["observed_current"] == 1
    assert summary["category_relation_correct"]["observed_other"] == 1
    assert summary["model_involved_route_correct"] == 1
    assert summary["multi_event_route_correct"] == 1
    assert summary["request_latency_p50_ms"] is not None


def test_failed_call_does_not_hide_other_confirmed_current_hazard(tmp_path) -> None:
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TransportError("network_error")
        return _completion("로봇청소기 전원선", "current")

    row = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert calls == row["request_count"] == 2
    assert row["route"] == "safety_action_required"
    assert row["stage2"][1]["error_code"] == "network_error"
    assert not (tmp_path / "ES01-stage2-2.json.txt").exists()


def test_contract_error_fails_closed_without_retry(tmp_path) -> None:
    case = {**CASE, "events": CASE["events"][:1], "expected_route": "collecting_service_request"}
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        return _completion("탁상 조명", "same")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake)
    assert calls == row["request_count"] == 1
    assert row["route"] == "confirming_safety_status"
    assert row["stage2"][0]["status"] == "contract_error"
    assert row["stage2"][0]["error_field"] == "owner_to_target"


@pytest.mark.parametrize(
    ("payload", "error_code", "error_field"),
    [
        (
            {
                "hazard_owner_span": {"clause_index": 2, "quote": "탁상 조명"},
                "owner_to_target": "other",
                "extra": "unexpected",
            },
            "fields_invalid",
            "stage2",
        ),
        (
            {
                "hazard_owner_span": {"clause_index": 2, "quote": "   "},
                "owner_to_target": "other",
            },
            "quote_blank",
            "hazard_owner_span",
        ),
    ],
)
def test_malformed_owner_response_confirms_once_without_retry(
    tmp_path, payload: dict, error_code: str, error_field: str
) -> None:
    case = {**CASE, "events": CASE["events"][:1], "expected_route": "collecting_service_request"}
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        return Completion(json.dumps(payload, ensure_ascii=False), "stop")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake)
    assert calls == row["request_count"] == 1
    assert row["route"] == "confirming_safety_status"
    assert len(row["stage2"]) == 1
    stage = row["stage2"][0]
    assert stage["called"] is True
    assert stage["status"] == "contract_error"
    assert stage["error_code"] == error_code
    assert stage["error_field"] == error_field
    assert stage["owner_to_target"] is None
    assert stage["hazard_owner_span"] is None
    assert (tmp_path / "ES01-stage2-1.json.txt").exists()


def test_nonoccurring_event_is_skipped(tmp_path) -> None:
    case = {
        **CASE,
        "events": [
            {
                **CASE["events"][0],
                "occurrence": "nonoccurring",
                "hazard_owner_span": None,
                "owner_to_target": None,
            }
        ],
        "expected_route": "collecting_service_request",
    }

    def forbidden(messages, schema, *, policy):
        raise AssertionError("nonoccurring must not call model")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=forbidden)
    assert row["request_count"] == 0
    assert row["route"] == "collecting_service_request"
    assert row["stage2"][0]["skip_reason"] == "nonoccurring"
    assert not list(tmp_path.iterdir())


def test_preflight_blocks_existing_outputs_and_unfrozen_protocol(tmp_path, monkeypatch) -> None:
    output = tmp_path / "journal.jsonl"
    output.write_text("partial\n", encoding="utf-8")
    args = argparse.Namespace(
        protocol=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        output=output,
        private_dir=tmp_path / "private",
        container_name="unused",
    )
    with pytest.raises(FileExistsError):
        runner.run(args)
    output.unlink()
    monkeypatch.setattr(
        runner, "load_protocol", lambda *_: (_ for _ in ()).throw(ValueError("unfrozen"))
    )
    with pytest.raises(ValueError, match="unfrozen"):
        runner.run(args)
    assert not output.exists()
    assert not args.private_dir.exists()


def test_finish_length_retains_raw_but_confirms(tmp_path) -> None:
    case = {**CASE, "events": CASE["events"][:1], "expected_route": "collecting_service_request"}

    def fake(messages, schema, *, policy):
        return _completion("탁상 조명", "other", finish_reason="length")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake)
    assert row["stage2"][0]["error_code"] == "finish_length"
    assert row["route"] == "confirming_safety_status"
    assert (tmp_path / "ES01-stage2-1.json.txt").exists()


def test_reviewed_dataset_has_exactly_nineteen_stage2_calls(tmp_path) -> None:
    cases = load_cases(runner.INPUTS["dataset"])
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        # Unknown with no owner is contract-valid for every actionable event.
        return Completion('{"hazard_owner_span":null,"owner_to_target":"unknown"}', "stop")

    rows = [
        runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake) for case in cases
    ]
    assert len(rows) == 20
    assert calls == sum(row["request_count"] for row in rows) == 19
    assert sum(not stage["called"] for row in rows for stage in row["stage2"]) == 3
    assert sum(row["request_count"] > 0 for row in rows) == 18
    assert runner.summarize(rows, cases)["actionable_gold_event_count"] == 19


def test_perfect_injected_decisions_calibrate_category_and_pair_denominators(tmp_path) -> None:
    cases = load_cases(runner.INPUTS["dataset"])
    rows = []
    for case in cases:
        actionable = iter(
            event for event in case["events"] if event["occurrence"] != "nonoccurring"
        )

        def fake(messages, schema, *, policy, _actionable=actionable):
            gold = next(_actionable)
            return Completion(
                json.dumps(
                    {
                        "hazard_owner_span": gold["hazard_owner_span"],
                        "owner_to_target": gold["owner_to_target"],
                    },
                    ensure_ascii=False,
                ),
                "stop",
            )

        rows.append(runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake))
    summary = runner.summarize(rows, cases)
    assert summary["relation_correct"] == summary["owner_exact_correct"] == 19
    assert summary["category_counts"] == {
        "observed_current": 8,
        "observed_other": 9,
        "observed_unknown": 1,
        "uncertain_current": 1,
    }
    assert summary["category_relation_correct"] == summary["category_counts"]
    assert summary["contrast_pair_count"] == summary["contrast_pairs_correct"] == 2
    assert summary["model_involved_route_correct"] == 18
    assert summary["request_latency_p50_ms"] is not None
    assert summary["request_latency_p95_ms"] is not None
