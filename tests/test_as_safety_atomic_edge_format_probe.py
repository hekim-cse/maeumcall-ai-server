"""Offline checks for the paired ES response-format probe."""

import argparse
import json

import pytest

from experiments.as_safety_atomic_edges_v1 import run as v1
from experiments.as_safety_atomic_edges_v1.event_owner import event_owner_schema
from experiments.as_safety_atomic_edges_v3 import run as probe
from experiments.as_safety_atomic_edges_v3 import verify
from experiments.as_safety_v2.transport import Completion, TransportError


def _inputs():
    return {key: path.read_bytes() for key, path in probe.INPUTS.items()}


def _cases():
    return {case["case_id"]: case for case in v1.load_request_cases(_inputs())}


def test_conditions_change_only_response_format():
    case = _cases()["ES01"]
    event = case["events"][0]
    baseline = probe.messages(case, event, "baseline")
    variant = probe.messages(case, event, "variant")
    assert baseline == variant
    schema = event_owner_schema(case["user_message"])
    policy = probe._policy({"request_policy": v1.REQUEST_POLICY})
    bodies = [
        json.loads(probe.request_bytes(baseline, schema, policy, condition))
        for condition in ("baseline", "variant")
    ]
    baseline_format = bodies[0].pop("response_format")
    variant_format = bodies[1].pop("response_format")
    assert bodies[0] == bodies[1]
    assert baseline_format == {"type": "json_object", "schema": schema}
    assert variant_format == {"type": "json_object"}


def test_frozen_request_hashes_cover_every_ordered_call_without_gold():
    hashes = probe._request_hashes(_inputs())
    assert set(hashes) == {f"{case_id}:{condition}" for case_id, condition in probe.ORDER}
    assert len(set(hashes.values())) == len(probe.ORDER)
    historical = probe._historical_hashes()
    for case_id in probe.CASE_IDS:
        assert hashes[f"{case_id}:baseline"] == historical[f"{case_id}:baseline"]
    case = _cases()["ES01"]
    body = json.loads(
        probe.request_bytes(
            probe.messages(case, case["events"][0], "baseline"),
            event_owner_schema(case["user_message"]),
            probe._policy({"request_policy": v1.REQUEST_POLICY}),
            "baseline",
        )
    )
    serialized = json.dumps(body, ensure_ascii=False)
    assert "hazard_owner_span" not in serialized
    assert "owner_to_target" not in serialized
    assert "expected_route" not in serialized
    assert "event_subject_kind" in serialized  # Output schema, not gold label.


def test_plain_transport_sends_exact_variant_bytes(monkeypatch):
    case = _cases()["ES01"]
    messages = probe.messages(case, case["events"][0], "variant")
    schema = event_owner_schema(case["user_message"])
    policy = probe._policy({"request_policy": v1.REQUEST_POLICY})
    sent = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(
                {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
            ).encode()

    class Opener:
        def open(self, request, timeout):
            sent.append((request.data, timeout))
            return Response()

    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *_args: Opener())
    completion = probe.post_format_completion(
        messages,
        schema,
        condition="variant",
        policy=policy,
        endpoint=v1.ENDPOINT,
        model_id=v1.MODEL_ID,
    )
    assert completion.content == "{}"
    assert sent == [
        (probe.request_bytes(messages, schema, policy, "variant"), policy.timeout_seconds)
    ]


@pytest.mark.parametrize("first_failure", ["timeout", "invalid_utf8"])
def test_runner_records_ten_calls_and_does_not_retry_first_failure(
    tmp_path, monkeypatch, first_failure
):
    verified = _inputs()
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(verified),
    }
    monkeypatch.setattr(
        probe,
        "load_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    monkeypatch.setattr(probe, "_container_identity", lambda name: ("same-id", "same-start"))
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        calls.append((messages, condition))
        if len(calls) == 1:
            if first_failure == "timeout":
                raise TransportError("timeout")
            return Completion("\ud800", "stop")
        return Completion(
            json.dumps(
                {
                    "subject_span": None,
                    "event_subject_kind": "unresolved",
                    "event_subject_evidence_span": None,
                }
            ),
            "stop",
        )

    output = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    probe.run(
        argparse.Namespace(
            output=output,
            private_dir=private,
            protocol=tmp_path / "protocol.json",
            model_path=tmp_path / "model.gguf",
            container_name=probe.CONTAINER_NAME,
        ),
        completion_call=fake_completion,
    )
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(calls) == 10
    cases = _cases()
    assert calls == [
        (probe.messages(cases[case_id], cases[case_id]["events"][0], condition), condition)
        for case_id, condition in probe.ORDER
    ]
    assert len(rows) == 11
    assert [(row["case_id"], row["condition"]) for row in rows[1:]] == list(probe.ORDER)
    assert rows[1]["error_code"] == (
        "timeout" if first_failure == "timeout" else "response_fields_invalid"
    )
    assert rows[1]["raw_sha256"] is None
    assert rows[2]["raw_sha256"] is not None
    assert not (private / "ES01-baseline.json.txt").exists()
    assert (private / "ES01-variant.json.txt").stat().st_mode & 0o777 == 0o600
    assert private.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    ("matching_identity_checks", "expected_journal_lines"),
    [(3, 1), (4, 2)],
    ids=["during-first-request", "before-second-request"],
)
def test_runner_stops_on_container_replacement_without_next_call(
    tmp_path, monkeypatch, matching_identity_checks, expected_journal_lines
):
    verified = _inputs()
    protocol = {**probe._identity(), "request_sha256_by_call": probe._request_hashes(verified)}
    monkeypatch.setattr(
        probe,
        "load_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    identities = iter(
        [("first-id", "first-start")] * matching_identity_checks + [("second-id", "second-start")]
    )
    monkeypatch.setattr(probe, "_container_identity", lambda name: next(identities))
    calls = []

    def fake_completion(messages, schema, *, condition, policy, endpoint, model_id):
        calls.append(messages)
        return Completion(
            json.dumps(
                {
                    "subject_span": None,
                    "event_subject_kind": "unresolved",
                    "event_subject_evidence_span": None,
                }
            ),
            "stop",
        )

    output = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    with pytest.raises(ValueError, match="model server changed"):
        probe.run(
            argparse.Namespace(
                output=output,
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            ),
            completion_call=fake_completion,
        )
    assert len(calls) == 1
    assert len(output.read_text().splitlines()) == expected_journal_lines
    assert (private / "ES01-baseline.json.txt").exists()


def test_runner_rejects_server_replacement_during_configuration_check(tmp_path, monkeypatch):
    verified = _inputs()
    protocol = {**probe._identity(), "request_sha256_by_call": probe._request_hashes(verified)}
    monkeypatch.setattr(
        probe,
        "load_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    monkeypatch.setattr(probe.v4, "verify_container", lambda name, model_path: None)
    identities = iter([("first-id", "first-start"), ("second-id", "second-start")])
    monkeypatch.setattr(probe, "_container_identity", lambda name: next(identities))
    output = tmp_path / "journal.jsonl"
    private = tmp_path / "private"
    with pytest.raises(ValueError, match="configuration check"):
        probe.run(
            argparse.Namespace(
                output=output,
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not output.exists()
    assert not private.exists()


def test_prepare_rejects_protocol_path_outside_repository_before_creating_file(tmp_path):
    protocol = tmp_path / "protocol.json"
    with pytest.raises(ValueError, match="inside repository"):
        probe.prepare_protocol(protocol, tmp_path / "model.gguf")
    assert not protocol.exists()


def test_load_protocol_rejects_float_timeout_before_model_check(tmp_path):
    protocol = {
        **probe._identity(),
        "frozen_code_commit": "0" * 40,
        "source_manifest": {},
        "input_hashes": {},
        "request_sha256_by_call": {},
    }
    protocol["request_policy"] = {**protocol["request_policy"], "timeout_seconds": 180.0}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="timeout type"):
        probe.load_protocol(path, tmp_path / "model.gguf")
    with pytest.raises(verify.VerificationError, match="timeout type"):
        verify.check_protocol(path, tmp_path / "model.gguf")


def test_runner_rejects_public_journal_inside_private_directory(tmp_path):
    private = tmp_path / "private"
    with pytest.raises(ValueError, match="journal must be outside"):
        probe.run(
            argparse.Namespace(
                output=private / "journal.jsonl",
                private_dir=private,
                protocol=tmp_path / "protocol.json",
                model_path=tmp_path / "model.gguf",
                container_name=probe.CONTAINER_NAME,
            )
        )
    assert not private.exists()


def test_runner_rejects_duplicate_protocol_json_keys(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text('{"kind": 1, "kind": 2}')
    with pytest.raises(ValueError, match="duplicate protocol JSON key"):
        probe.load_protocol(protocol, tmp_path / "model.gguf")


@pytest.mark.parametrize(
    "tamper", ["wrong_hash", "duplicate_condition", "bad_status", "bool_index", "float_index"]
)
def test_replay_rejects_tampered_request_or_response_metadata(tmp_path, tamper):
    sources = verify._source_cases(_inputs())
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(_inputs()),
    }
    rows = [{"event": "header", "protocol_sha256": "protocol-sha"}]
    for case_id, condition in probe.ORDER:
        rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": protocol["request_sha256_by_call"][f"{case_id}:{condition}"],
                "finish_reason": None,
                "error_code": "timeout",
                "http_status": None,
                "raw_sha256": None,
                "raw_bytes": None,
                "request_latency_ms": 1.0,
            }
        )
    if tamper == "wrong_hash":
        rows[1]["request_sha256"] = "0" * 64
    elif tamper == "duplicate_condition":
        rows[2]["condition"] = "baseline"
    elif tamper == "bool_index":
        rows[1]["event_index"] = True
    elif tamper == "float_index":
        rows[1]["event_index"] = 1.0
    else:
        rows[1]["http_status"] = 200
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(verify.VerificationError):
        verify._journal(journal, "protocol-sha", sources, protocol)


def _synthetic_full_replay(tmp_path, monkeypatch, *, variant_es01_raw=None, variant_es17_raw=None):
    verified = _inputs()
    protocol = {
        **probe._identity(),
        "request_sha256_by_call": probe._request_hashes(verified),
    }
    monkeypatch.setattr(
        verify,
        "check_protocol",
        lambda protocol_path, model_path: (protocol, "protocol-sha", verified),
    )
    prior_raw = json.dumps(
        {
            "subject_span": None,
            "event_subject_kind": "unresolved",
            "event_subject_evidence_span": None,
        }
    )
    prior_sha = probe.digest(prior_raw.encode())
    monkeypatch.setattr(
        verify.v2, "check_protocol", lambda *args: ({}, verify.REFERENCE_PROTOCOL_SHA256, verified)
    )
    monkeypatch.setattr(verify.v2, "_source_cases", lambda *args: verify._source_cases(verified))
    monkeypatch.setattr(
        verify.v2,
        "_journal",
        lambda *args: [
            {
                "case_id": case_id,
                "condition": "baseline",
                "raw_sha256": prior_sha,
                "raw_bytes": len(prior_raw.encode()),
                "finish_reason": "stop",
                "error_code": None,
            }
            for case_id in probe.CASE_IDS
        ],
    )
    monkeypatch.setattr(verify.v2, "_raw", lambda *args: prior_raw)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    rows = [{"event": "header", "protocol_sha256": "protocol-sha"}]
    for case_id, condition in probe.ORDER:
        raw = (
            variant_es17_raw
            if case_id == "ES17" and condition == "variant" and variant_es17_raw is not None
            else (
                variant_es01_raw
                if case_id == "ES01" and condition == "variant" and variant_es01_raw is not None
                else prior_raw
            )
        )
        raw_path = private / f"{case_id}-{condition}.json.txt"
        raw_path.write_text(raw)
        raw_path.chmod(0o600)
        rows.append(
            {
                "event": "result",
                "case_id": case_id,
                "event_index": 1,
                "condition": condition,
                "request_sha256": protocol["request_sha256_by_call"][f"{case_id}:{condition}"],
                "finish_reason": "stop",
                "error_code": None,
                "http_status": None,
                "raw_sha256": probe.digest(raw.encode()),
                "raw_bytes": len(raw.encode()),
                "request_latency_ms": 1.0,
            }
        )
    journal = tmp_path / "journal.jsonl"
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (tmp_path / "reference-private").mkdir(mode=0o700)
    reference_protocol = v1.DATA / "as-safety-eb-abstention-v2-development-protocol.json"
    reference_journal = v1.DATA / "as-safety-eb-abstention-v2-development-journal.v1.jsonl"
    return verify.verify_result(
        tmp_path / "protocol.json",
        tmp_path / "model.gguf",
        journal,
        private,
        reference_protocol,
        reference_journal,
        tmp_path / "reference-private",
    )


def test_full_replay_reports_fixed_denominators_and_reproduced_baseline(tmp_path, monkeypatch):
    report = _synthetic_full_replay(tmp_path, monkeypatch)
    assert report["historical_baseline_all_reproduced"] is True
    assert len(report["historical_baseline_reproduced"]) == 5
    assert len(report["paired_cases"]) == 10
    for condition in ("baseline", "variant"):
        result = report["summary"][condition]
        assert result["contract_pass"] == 5
        assert result["abstentions"] == 5
        assert result["B_exact_resolved"] == 0
        assert result["B_resolved_denominator"] == 4
        assert result["evidence_exact"] == 1
        assert result["resolved_evidence_exact"] == 0
        assert result["resolved_evidence_denominator"] == 4
        assert result["ES17_correct_abstention"] == 1
        assert result["ES17_false_resolution"] == 0
        assert result["ES17_evaluable"] is True


@pytest.mark.parametrize(
    "malformed",
    [
        {
            "subject_span": None,
            "event_subject_kind": "invented",
            "event_subject_evidence_span": None,
        },
        {
            "subject_span": None,
            "event_subject_kind": "unresolved",
            "event_subject_evidence_span": None,
            "unexpected": 1,
        },
        {
            "subject_span": {"clause_index": 2, "quote": " "},
            "event_subject_kind": "location",
            "event_subject_evidence_span": {"clause_index": 2, "quote": " "},
        },
        {
            "subject_span": "다른 위치",
            "event_subject_kind": "location",
            "event_subject_evidence_span": "다른 근거",
        },
    ],
    ids=["invalid-kind", "extra-field", "blank-quote", "string-quote"],
)
def test_full_replay_counts_malformed_model_output_as_contract_error(
    tmp_path, monkeypatch, malformed
):
    report = _synthetic_full_replay(
        tmp_path,
        monkeypatch,
        variant_es01_raw=json.dumps(malformed, ensure_ascii=False),
    )
    assert report["historical_baseline_all_reproduced"] is True
    assert report["summary"]["baseline"]["contract_pass"] == 5
    assert report["summary"]["variant"]["contract_pass"] == 4
    assert report["summary"]["variant"]["contract_errors"] == 1
    assert report["summary"]["variant"]["B_resolved_denominator"] == 4
    assert report["summary"]["variant"]["resolved_evidence_denominator"] == 4
    if type(malformed["subject_span"]) is str:
        assert (
            next(
                row
                for row in report["paired_cases"]
                if row["case_id"] == "ES01" and row["condition"] == "variant"
            )["contract_error_code"]
            == "quote_fields_invalid"
        )
    assert (
        next(
            row
            for row in report["paired_cases"]
            if row["case_id"] == "ES01" and row["condition"] == "variant"
        )["contract_pass"]
        is False
    )


def test_replay_marks_invalid_es17_as_not_evaluable(tmp_path, monkeypatch):
    malformed = json.dumps(
        {
            "subject_span": "잘못된 형식",
            "event_subject_kind": "location",
            "event_subject_evidence_span": "잘못된 근거",
        },
        ensure_ascii=False,
    )
    report = _synthetic_full_replay(tmp_path, monkeypatch, variant_es17_raw=malformed)
    variant = report["summary"]["variant"]
    assert variant["ES17_evaluable"] is False
    assert variant["ES17_correct_abstention"] == 0
    assert variant["ES17_false_resolution"] == 0
    assert (
        next(
            row
            for row in report["paired_cases"]
            if row["case_id"] == "ES17" and row["condition"] == "variant"
        )["contract_error_code"]
        == "quote_fields_invalid"
    )
