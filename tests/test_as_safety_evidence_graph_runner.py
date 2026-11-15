"""Graph event-oracle runner preserves prompt, safety and freeze boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat

import pytest

from experiments.as_safety_evidence_graph_v1 import run as runner
from experiments.as_safety_v2.transport import Completion, RequestPolicy, TransportError
from experiments.as_safety_v4.cases import load_cases

MESSAGE = (
    "접수할 프린터가 고장 났습니다. 옆 라디오 충전기에서 불꽃이 튀었어요. 프린터 전원선이 녹았어요."
)
CASE = {
    "id": "ES01",
    "user_message": MESSAGE,
    "target": {"clause_index": 1, "quote": "프린터"},
    "events": [
        {
            "event_span": {"clause_index": 2, "quote": "불꽃이 튀었어요"},
            "occurrence": "observed",
            "hazard_owner_span": {"clause_index": 2, "quote": "옆 라디오 충전기"},
            "owner_to_target": "other",
        },
        {
            "event_span": {"clause_index": 3, "quote": "녹았어요"},
            "occurrence": "observed",
            "hazard_owner_span": {"clause_index": 3, "quote": "프린터 전원선"},
            "owner_to_target": "current",
        },
    ],
    "expected_route": "safety_action_required",
    "overflow": False,
}
LABELS = [
    {
        "id": "ES01",
        "events": [
            {
                "event_index": 1,
                "event_subject_kind": "subject",
                "event_subject_evidence_span": {
                    "clause_index": 2,
                    "quote": "옆 라디오 충전기에서 불꽃이 튀었어요",
                },
                "target_edge_kind": "distinct",
                "target_edge_evidence_span": {"clause_index": 2, "quote": "옆 라디오 충전기"},
            },
            {
                "event_index": 2,
                "event_subject_kind": "subject",
                "event_subject_evidence_span": {
                    "clause_index": 3,
                    "quote": "프린터 전원선이 녹았어요",
                },
                "target_edge_kind": "part_of",
                "target_edge_evidence_span": {"clause_index": 3, "quote": "프린터 전원선"},
            },
        ],
    }
]


def test_label_compiler_is_a_required_frozen_source(monkeypatch):
    compiler = "scripts/build_as_safety_evidence_graph_labels.py"
    assert compiler in runner.REQUIRED_SOURCES
    requested = []

    def fake_git(*args):
        requested.append(args)
        return f"{compiler}\n".encode() if args[-1] == compiler else b""

    monkeypatch.setattr(runner.v4, "_git", fake_git)
    assert compiler in runner._source_paths("a" * 40)
    assert any(args[-1] == compiler for args in requested)


def _reply(subject: str, event_cue: str, edge: str, edge_cue: str, clause: int) -> Completion:
    return Completion(
        json.dumps(
            {
                "subject_span": {"clause_index": clause, "quote": subject},
                "event_subject_kind": "subject",
                "event_subject_evidence_span": {"clause_index": clause, "quote": event_cue},
                "target_edge_kind": edge,
                "target_edge_evidence_span": {"clause_index": clause, "quote": edge_cue},
            },
            ensure_ascii=False,
        ),
        "stop",
    )


def test_two_events_hide_gold_and_keep_private_raw(tmp_path):
    responses = iter(
        [
            _reply(
                "옆 라디오 충전기",
                "옆 라디오 충전기에서 불꽃이 튀었어요",
                "distinct",
                "옆 라디오 충전기",
                2,
            ),
            _reply("프린터 전원선", "프린터 전원선이 녹았어요", "part_of", "프린터 전원선", 3),
        ]
    )
    requests = []

    def fake(messages, schema, *, policy):
        requests.append((messages, schema, policy))
        return next(responses)

    tainted_case = {
        **CASE,
        "events": [
            {**event, "hazard_owner_span": {"clause_index": 2, "quote": "NEVER-LEAK-GOLD"}}
            for event in CASE["events"]
        ],
    }
    row = runner.call_case(tainted_case, RequestPolicy(), tmp_path, completion_call=fake)
    assert row["request_count"] == len(requests) == 2
    assert row["route"] == "safety_action_required"
    assert [stage["effective_relation"] for stage in row["stages"]] == ["other", "current"]
    joined = json.dumps(requests, ensure_ascii=False, default=str)
    assert "NEVER-LEAK-GOLD" not in joined
    assert "owner_to_target" not in joined
    assert "expected_route" not in joined
    assert 'target_edge_kind": "part_of"' not in joined
    assert all("quote" not in stage["subject_span"] for stage in row["stages"])
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "ES01-graph-1.json.txt",
        "ES01-graph-2.json.txt",
    ]
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in tmp_path.iterdir())
    metrics = runner.summarize([row], [CASE], LABELS)
    assert metrics["relation_correct"] == 2
    assert metrics["subject_exact_nonnull"] == 2
    assert metrics["attachment_kind_correct"] == 2
    assert metrics["attachment_evidence_exact"] == 2
    assert metrics["edge_kind_correct"] == 2
    assert metrics["edge_evidence_exact"] == 2
    assert metrics["label_joint_correct"] == 2
    assert metrics["all_fields_exact"] == 2
    assert metrics["multi_event_route_correct"] == 1


def test_transport_error_confirms_without_retry_unless_other_event_is_current(tmp_path):
    count = 0

    def fake(messages, schema, *, policy):
        nonlocal count
        count += 1
        if count == 1:
            raise TransportError("network_error")
        return _reply("프린터 전원선", "프린터 전원선이 녹았어요", "part_of", "프린터 전원선", 3)

    row = runner.call_case(CASE, RequestPolicy(), tmp_path, completion_call=fake)
    assert count == 2
    assert row["route"] == "safety_action_required"
    assert row["stages"][0]["error_code"] == "network_error"
    assert not (tmp_path / "ES01-graph-1.json.txt").exists()


def test_invalid_graph_output_confirms_once_and_keeps_raw(tmp_path):
    case = {**CASE, "events": CASE["events"][:1], "expected_route": "collecting_service_request"}
    count = 0

    def fake(messages, schema, *, policy):
        nonlocal count
        count += 1
        return Completion('{"target_edge_kind":"distinct"}', "stop")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake)
    assert count == 1
    assert row["route"] == "confirming_safety_status"
    assert row["stages"][0]["status"] == "contract_error"
    assert row["stages"][0]["effective_relation"] is None
    assert (tmp_path / "ES01-graph-1.json.txt").exists()


@pytest.mark.parametrize(
    ("changes", "error_code", "error_field"),
    [
        ({"target_edge_kind": "different"}, "edge_kind_invalid", "target_edge_kind"),
        ({"unexpected": "value"}, "fields_invalid", "evidence_graph"),
        (
            {"subject_span": {"clause_index": 2, "quote": ""}},
            "quote_blank",
            "subject_span",
        ),
        (
            {"subject_span": {"clause_index": 2, "quote": " "}},
            "quote_blank",
            "subject_span",
        ),
        (
            {"subject_span": {"clause_index": 2, "quote": "\t"}},
            "quote_blank",
            "subject_span",
        ),
    ],
)
def test_malformed_graph_response_confirms_once_and_preserves_raw(
    tmp_path, changes, error_code, error_field
):
    case = {**CASE, "events": CASE["events"][:1], "expected_route": "collecting_service_request"}
    base = json.loads(
        _reply(
            "옆 라디오 충전기",
            "옆 라디오 충전기에서 불꽃이 튀었어요",
            "distinct",
            "옆 라디오 충전기",
            2,
        ).content
    )
    raw = json.dumps({**base, **changes}, ensure_ascii=False)
    calls = 0

    def fake(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        return Completion(raw, "stop")

    row = runner.call_case(case, RequestPolicy(), tmp_path, completion_call=fake)
    stage = row["stages"][0]
    assert calls == row["request_count"] == 1
    assert row["route"] == "confirming_safety_status"
    assert (stage["status"], stage["error_code"], stage["error_field"]) == (
        "contract_error",
        error_code,
        error_field,
    )
    assert stage["effective_relation"] is None
    path = tmp_path / "ES01-graph-1.json.txt"
    assert path.read_text(encoding="utf-8") == raw
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stage["raw_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_reviewed_es_has_nineteen_calls_and_three_nonoccurring_skips(tmp_path):
    cases = load_cases(runner.INPUTS["dataset"])
    calls = 0

    def unresolved(messages, schema, *, policy):
        nonlocal calls
        calls += 1
        return Completion(
            '{"subject_span":null,"event_subject_kind":"unresolved",'
            '"event_subject_evidence_span":null,"target_edge_kind":"unresolved",'
            '"target_edge_evidence_span":null}',
            "stop",
        )

    rows = [
        runner.call_case(case, RequestPolicy(), tmp_path, completion_call=unresolved)
        for case in cases
    ]
    assert len(rows) == 20
    assert calls == sum(row["request_count"] for row in rows) == 19
    assert sum(not stage["called"] for row in rows for stage in row["stages"]) == 3
    assert sum(row["request_count"] > 0 for row in rows) == 18
    assert (
        next(row for row in rows if row["case_id"] == "ES17")["route"] == "confirming_safety_status"
    )
    assert [row["route"] for row in rows[-2:]] == [
        "collecting_service_request",
        "collecting_service_request",
    ]


def test_unresolved_and_nonoccurring_paths(tmp_path):
    unknown = {
        **CASE,
        "events": [
            {
                **CASE["events"][0],
                "hazard_owner_span": None,
                "owner_to_target": "unknown",
            }
        ],
        "expected_route": "confirming_safety_status",
    }

    def unresolved(messages, schema, *, policy):
        return Completion(
            json.dumps(
                {
                    "subject_span": None,
                    "event_subject_kind": "unresolved",
                    "event_subject_evidence_span": None,
                    "target_edge_kind": "unresolved",
                    "target_edge_evidence_span": None,
                }
            ),
            "stop",
        )

    row = runner.call_case(unknown, RequestPolicy(), tmp_path, completion_call=unresolved)
    assert row["route"] == "confirming_safety_status"
    assert row["stages"][0]["status"] == "validated"
    unknown_labels = [
        {
            "id": "ES01",
            "events": [
                {
                    "event_index": 1,
                    "event_subject_kind": "unresolved",
                    "event_subject_evidence_span": None,
                    "target_edge_kind": "unresolved",
                    "target_edge_evidence_span": None,
                }
            ],
        }
    ]
    metrics = runner.summarize([row], [unknown], unknown_labels)
    assert (metrics["subject_null_correct"], metrics["subject_gold_null_count"]) == (1, 1)
    nonoccurring = {
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
        raise AssertionError("nonoccurring must not reach model")

    row = runner.call_case(nonoccurring, RequestPolicy(), tmp_path, completion_call=forbidden)
    assert row["request_count"] == 0
    assert row["route"] == "collecting_service_request"
    assert row["stages"][0]["skip_reason"] == "nonoccurring"


def test_unapproved_labels_and_existing_partial_output_block_before_model(tmp_path, monkeypatch):
    label_path = tmp_path / "labels.json"
    approved = {
        "kind": "as_safety_evidence_graph_v1_labels",
        "review_status": "owner_approved_for_exploratory_evaluation",
        "review_sha256": "0" * 64,
        "cases": LABELS,
    }
    label_path.write_text(json.dumps(approved, ensure_ascii=False), encoding="utf-8")
    assert runner.load_graph_labels(label_path, [CASE]) == LABELS
    draft = {**approved, "review_status": "draft"}
    label_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        runner.load_graph_labels(label_path, [CASE])
    output = tmp_path / "journal.jsonl"
    output.write_text("partial\n")
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
    assert not output.exists() and not args.private_dir.exists()


def test_approved_labels_bind_review_and_existing_relation(tmp_path, monkeypatch):
    review = tmp_path / "review.md"
    review.write_text("user-reviewed graph labels", encoding="utf-8")
    root = {
        "kind": "as_safety_evidence_graph_v1_labels",
        "review_status": "owner_approved_for_exploratory_evaluation",
        "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "cases": LABELS,
    }
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(runner, "compile_labels", lambda **_kwargs: root)
    assert runner.load_graph_labels(labels_path, [CASE], review_path=review) == LABELS
    review.write_text("changed after approval", encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed table"):
        runner.load_graph_labels(labels_path, [CASE], review_path=review)
    review.write_text("user-reviewed graph labels", encoding="utf-8")
    wrong = json.loads(labels_path.read_text(encoding="utf-8"))
    wrong["cases"][0]["events"][0]["target_edge_kind"] = "part_of"
    labels_path.write_text(json.dumps(wrong, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="relation differs"):
        runner.load_graph_labels(labels_path, [CASE], review_path=review)
    altered = json.loads(json.dumps(root))
    altered["cases"][0]["events"][1]["target_edge_evidence_span"]["quote"] = (
        "프린터 전원선이 녹았어요"
    )
    labels_path.write_text(json.dumps(altered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed table values"):
        runner.load_graph_labels(labels_path, [CASE], review_path=review)


def test_interrupted_run_preserves_partial_for_audit_and_refuses_resume(tmp_path, monkeypatch):
    args = argparse.Namespace(
        protocol=tmp_path / "protocol.json",
        model_path=tmp_path / "model.gguf",
        output=tmp_path / "journal.jsonl",
        private_dir=tmp_path / "private",
        container_name="unused",
    )
    monkeypatch.setattr(
        runner,
        "load_protocol",
        lambda *_: (
            {"request_policy": runner.REQUEST, "input_hashes": {"graph_labels": "x"}},
            "frozen",
        ),
    )
    monkeypatch.setattr(runner, "load_graph_labels", lambda *_args, **_kwargs: LABELS)
    monkeypatch.setattr(runner.v4, "verify_container", lambda *_: None)
    monkeypatch.setattr(
        runner, "call_case", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("interrupted"))
    )
    with pytest.raises(OSError, match="interrupted"):
        runner.run(args)
    assert args.output.exists() and args.private_dir.exists()
    lines = args.output.read_text().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["header", "begin"]
    with pytest.raises(FileExistsError):
        runner.run(args)
