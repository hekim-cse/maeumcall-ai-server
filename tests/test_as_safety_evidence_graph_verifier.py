"""Independent raw replay, public tamper detection, and source boundaries."""

import hashlib
import json
import os

import pytest

from experiments.as_safety_evidence_graph_v1 import verify as verifier
from experiments.as_safety_evidence_graph_v1.verify import (
    ContractError,
    _public,
    _read_raw,
    _source_paths,
    _span,
    audit_end,
    load_labels,
    replay_graph,
    summarize,
)

MESSAGE = "접수할 프린터가 고장입니다. 옆 라디오 충전기에서 불꽃이 튀었어요."
EVENT = {"clause_index": 2, "quote": "불꽃이 튀었어요"}
SUBJECT = {"clause_index": 2, "quote": "옆 라디오 충전기"}
GRAPH = {
    "subject_span": SUBJECT,
    "event_subject_kind": "subject",
    "event_subject_evidence_span": {
        "clause_index": 2,
        "quote": "옆 라디오 충전기에서 불꽃이 튀었어요",
    },
    "target_edge_kind": "distinct",
    "target_edge_evidence_span": SUBJECT,
}
REVIEW_TABLE = (
    "| 사건 | 기존 | 새 E→B | 새 B→A | 비고 |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| ES99 | 기존 | `subject` · 2 `옆 라디오 충전기에서 불꽃이 튀었어요` | "
    "`distinct` · 2 `옆 라디오 충전기` | 검수 |\n"
)


def _case():
    return {
        "id": "ES99",
        "user_message": MESSAGE,
        "target": {"clause_index": 1, "quote": "프린터"},
        "events": [
            {
                "event_span": EVENT,
                "occurrence": "observed",
                "hazard_owner_span": SUBJECT,
                "owner_to_target": "other",
            }
        ],
        "expected_route": "collecting_service_request",
        "overflow": False,
    }


def _row(raw: str, *, private_dir):
    encoded = raw.encode("utf-8")
    path = private_dir / "ES99-graph-1.json.txt"
    path.write_bytes(encoded)
    os.chmod(path, 0o600)
    prediction = replay_graph(raw, MESSAGE, EVENT)
    public_event = _public(
        _span(
            EVENT,
            ("접수할 프린터가 고장입니다.", "옆 라디오 충전기에서 불꽃이 튀었어요."),
            "event_span",
        )
    )
    stage = {
        "event_index": 1,
        "event_span": public_event,
        "occurrence": "observed",
        "called": True,
        "status": "validated",
        "skip_reason": None,
        "error_code": None,
        "error_field": None,
        "finish_reason": "stop",
        "latency_ms": 3.0,
        "request_latency_ms": 2.0,
        "raw_sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_bytes": len(encoded),
        "subject_span": _public(prediction["subject_span"]),
        "event_subject_kind": prediction["event_subject_kind"],
        "event_subject_evidence_span": _public(prediction["event_subject_evidence_span"]),
        "target_edge_kind": prediction["target_edge_kind"],
        "target_edge_evidence_span": _public(prediction["target_edge_evidence_span"]),
        "effective_relation": prediction["effective_relation"],
    }
    return {
        "event": "end",
        "case_id": "ES99",
        "stages": [stage],
        "route": "collecting_service_request",
        "request_count": 1,
        "model_call_latency_sum_ms": 2.0,
        "elapsed_ms": 4.0,
    }


def test_raw_graph_replay_preserves_source_and_typed_edge():
    result = replay_graph(json.dumps(GRAPH, ensure_ascii=False), MESSAGE, EVENT)
    assert result["subject_span"]["quote"] == "옆 라디오 충전기"
    assert result["target_edge_kind"] == "distinct"
    assert result["effective_relation"] == "other"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("subject_span", {"clause_index": 2, "quote": "없는 제품"}, "quote_unanchored"),
        (
            "event_subject_evidence_span",
            {"clause_index": 1, "quote": "프린터"},
            "event_attachment_unlinked",
        ),
        (
            "target_edge_evidence_span",
            {"clause_index": 2, "quote": "충전기"},
            "distinct_subject_unlinked",
        ),
        ("target_edge_kind", "different", "edge_kind_invalid"),
    ],
)
def test_raw_replay_rejects_invalid_source_or_edge(field, value, code):
    with pytest.raises(ContractError) as caught:
        replay_graph(json.dumps({**GRAPH, field: value}, ensure_ascii=False), MESSAGE, EVENT)
    assert caught.value.code == code


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
def test_invalid_private_response_replays_to_one_confirmation(
    tmp_path, changes, error_code, error_field
):
    row = _row(json.dumps(GRAPH, ensure_ascii=False), private_dir=tmp_path)
    raw = json.dumps({**GRAPH, **changes}, ensure_ascii=False)
    path = tmp_path / "ES99-graph-1.json.txt"
    path.write_text(raw, encoding="utf-8")
    encoded = raw.encode("utf-8")
    stage = row["stages"][0]
    stage.update(
        status="contract_error",
        error_code=error_code,
        error_field=error_field,
        raw_sha256=hashlib.sha256(encoded).hexdigest(),
        raw_bytes=len(encoded),
        subject_span=None,
        event_subject_kind=None,
        event_subject_evidence_span=None,
        target_edge_kind=None,
        target_edge_evidence_span=None,
        effective_relation=None,
    )
    row["route"] = "confirming_safety_status"
    audited = audit_end(row, _case(), tmp_path)
    assert audited["route"] == "confirming_safety_status"
    assert audited["request_count"] == 1
    assert audited["raw_files"] == {"ES99-graph-1.json.txt"}
    assert path.read_text(encoding="utf-8") == raw
    assert path.stat().st_mode & 0o777 == 0o600


def test_duplicate_json_key_rejected():
    raw = json.dumps(GRAPH, ensure_ascii=False)[:-1] + ',"target_edge_kind":"part_of"}'
    with pytest.raises(ContractError) as caught:
        replay_graph(raw, MESSAGE, EVENT)
    assert caught.value.code == "duplicate_key"


def test_public_route_and_private_hash_tampering_are_detected(tmp_path):
    raw = json.dumps(GRAPH, ensure_ascii=False)
    row = _row(raw, private_dir=tmp_path)
    result = audit_end(row, _case(), tmp_path)
    assert result["route"] == "collecting_service_request"
    assert result["raw_files"] == {"ES99-graph-1.json.txt"}
    row["route"] = "safety_action_required"
    with pytest.raises(ValueError, match="journal route"):
        audit_end(row, _case(), tmp_path)
    row["route"] = "collecting_service_request"
    (tmp_path / "ES99-graph-1.json.txt").write_text(raw + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="private raw response differs"):
        audit_end(row, _case(), tmp_path)


def test_private_raw_mode_is_required(tmp_path):
    raw = json.dumps(GRAPH, ensure_ascii=False)
    row = _row(raw, private_dir=tmp_path)
    path = tmp_path / "ES99-graph-1.json.txt"
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="private raw metadata differs"):
        _read_raw(row["stages"][0], path)


def test_summary_recalculates_stagewise_diagnostic_without_runner(tmp_path):
    raw = json.dumps(GRAPH, ensure_ascii=False)
    row = _row(raw, private_dir=tmp_path)
    audited = audit_end(row, _case(), tmp_path)
    labels = [
        {
            "id": "ES99",
            "events": [
                {
                    "event_index": 1,
                    "event_subject_kind": "subject",
                    "event_subject_evidence_span": GRAPH["event_subject_evidence_span"],
                    "target_edge_kind": "distinct",
                    "target_edge_evidence_span": SUBJECT,
                }
            ],
        }
    ]
    summary = summarize([audited], [_case()], labels)
    assert summary["relation_correct"] == 1
    assert summary["subject_exact_nonnull"] == 1
    assert summary["attachment_kind_correct"] == 1
    assert summary["edge_kind_correct"] == 1
    assert summary["label_joint_correct"] == 1
    assert summary["all_fields_exact"] == 1


def test_unapproved_graph_labels_are_rejected(tmp_path, monkeypatch):
    review = tmp_path / "review.md"
    review.write_text(REVIEW_TABLE, encoding="utf-8")
    monkeypatch.setitem(verifier.INPUTS, "graph_field_review", review)
    path = tmp_path / "labels.json"
    approved = {
        "kind": "as_safety_evidence_graph_v1_labels",
        "review_status": "owner_approved_for_exploratory_evaluation",
        "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "cases": [
            {
                "id": "ES99",
                "events": [
                    {
                        "event_index": 1,
                        "event_subject_kind": "subject",
                        "event_subject_evidence_span": GRAPH["event_subject_evidence_span"],
                        "target_edge_kind": "distinct",
                        "target_edge_evidence_span": SUBJECT,
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(approved, ensure_ascii=False), encoding="utf-8")
    assert load_labels(path, [_case()])[0]["id"] == "ES99"
    path.write_text(json.dumps({**approved, "review_status": "draft"}, ensure_ascii=False))
    with pytest.raises(ValueError, match="provenance"):
        load_labels(path, [_case()])


def test_approved_label_review_hash_relation_and_locality_are_checked(tmp_path, monkeypatch):
    review = tmp_path / "review.md"
    review.write_text(REVIEW_TABLE, encoding="utf-8")
    monkeypatch.setitem(verifier.INPUTS, "graph_field_review", review)
    label = {
        "event_index": 1,
        "event_subject_kind": "subject",
        "event_subject_evidence_span": GRAPH["event_subject_evidence_span"],
        "target_edge_kind": "distinct",
        "target_edge_evidence_span": SUBJECT,
    }
    payload = {
        "kind": "as_safety_evidence_graph_v1_labels",
        "review_status": "owner_approved_for_exploratory_evaluation",
        "review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
        "cases": [{"id": "ES99", "events": [label]}],
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert load_labels(path, [_case()])[0]["id"] == "ES99"

    payload["cases"][0]["events"][0]["event_subject_evidence_span"] = {
        "clause_index": 2,
        "quote": "라디오 충전기에서 불꽃이 튀었어요",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed table"):
        load_labels(path, [_case()])
    payload["cases"][0]["events"][0]["event_subject_evidence_span"] = GRAPH[
        "event_subject_evidence_span"
    ]

    payload["cases"][0]["events"][0]["target_edge_kind"] = "part_of"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed table"):
        load_labels(path, [_case()])

    payload["cases"][0]["events"][0]["target_edge_kind"] = "distinct"
    payload["cases"][0]["events"][0]["target_edge_evidence_span"] = {
        "clause_index": 2,
        "quote": "충전기",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed table"):
        load_labels(path, [_case()])

    payload["cases"][0]["events"][0]["target_edge_evidence_span"] = SUBJECT
    payload["review_sha256"] = "0" * 64
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        load_labels(path, [_case()])


def test_frozen_source_manifest_requires_label_compiler(monkeypatch):
    names = {
        "experiments/as_safety_v2": b"experiments/as_safety_v2/evidence_graph.py\n",
        "experiments/as_safety_v4": b"experiments/as_safety_v4/cases.py\n",
        "experiments/as_safety_evidence_graph_v1": (
            b"experiments/as_safety_evidence_graph_v1/__init__.py\n"
            b"experiments/as_safety_evidence_graph_v1/run.py\n"
            b"experiments/as_safety_evidence_graph_v1/verify.py\n"
        ),
        "scripts/build_as_safety_evidence_graph_labels.py": (
            b"scripts/build_as_safety_evidence_graph_labels.py\n"
        ),
    }

    def fake_git(*args):
        return names[args[-1]]

    monkeypatch.setattr(verifier, "_git", fake_git)
    paths = _source_paths("0" * 40)
    assert "scripts/build_as_safety_evidence_graph_labels.py" in paths
    names["scripts/build_as_safety_evidence_graph_labels.py"] = b""
    with pytest.raises(ValueError, match="label compiler missing"):
        _source_paths("0" * 40)


def test_unknown_source_has_separate_null_subject_denominator():
    message = "접수할 이어폰이 고장입니다. 어디선가 탄 냄새가 났어요."
    event = {"clause_index": 2, "quote": "탄 냄새가 났어요"}
    unresolved = {
        "subject_span": None,
        "event_subject_kind": "unresolved",
        "event_subject_evidence_span": None,
        "target_edge_kind": "unresolved",
        "target_edge_evidence_span": None,
    }
    decision = replay_graph(json.dumps(unresolved), message, event)
    case = {
        "id": "ES17",
        "user_message": message,
        "target": {"clause_index": 1, "quote": "이어폰"},
        "events": [
            {
                "event_span": event,
                "occurrence": "observed",
                "hazard_owner_span": None,
                "owner_to_target": "unknown",
            }
        ],
        "expected_route": "confirming_safety_status",
        "overflow": False,
    }
    audited = {
        "case_id": "ES17",
        "route": "confirming_safety_status",
        "request_count": 1,
        "relations": ["unknown"],
        "decisions": [decision],
        "statuses": ["validated"],
        "called": [True],
        "request_latencies_ms": [2.0],
        "elapsed_ms": 4.0,
    }
    labels = [
        {
            "id": "ES17",
            "events": [
                {
                    "event_index": 1,
                    **{
                        key: unresolved[key]
                        for key in (
                            "event_subject_kind",
                            "event_subject_evidence_span",
                            "target_edge_kind",
                            "target_edge_evidence_span",
                        )
                    },
                }
            ],
        }
    ]
    summary = summarize([audited], [case], labels)
    assert summary["subject_gold_null_count"] == 1
    assert summary["subject_null_correct"] == 1
    assert summary["subject_gold_nonnull_count"] == 0
    assert summary["label_joint_correct"] == 1
