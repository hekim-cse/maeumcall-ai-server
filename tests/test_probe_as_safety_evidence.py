"""An evidence gate must reject invented spans and keep uncertainty separate."""

import argparse
import io
import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts import probe_as_safety_evidence as probe
from scripts.probe_as_safety_evidence import route_evidence, validate_evidence

DATA_ROOT = Path("evals/structured_nlu/data/ai_heldout")


def test_exact_evidence_span_routes_current_observation_to_safety() -> None:
    utterance = "노트북 하판이 솟아오르고 트랙패드가 눌리지 않아요."
    evidence = validate_evidence(
        '{"evidence":"하판이 솟아오르고","target":"current","assertion":"observed"}',
        utterance,
    )
    assert route_evidence(evidence) == "safety_action_required"


@pytest.mark.parametrize(
    ("target", "assertion", "route"),
    [
        ("current", "uncertain", "confirming_safety_status"),
        ("unknown", "observed", "confirming_safety_status"),
        ("other", "observed", "collecting_service_request"),
        ("current", "negated_or_hypothetical", "collecting_service_request"),
    ],
)
def test_target_and_assertion_are_distinct_inputs(target: str, assertion: str, route: str) -> None:
    evidence = validate_evidence(
        f'{{"evidence":"타는 냄새","target":"{target}","assertion":"{assertion}"}}',
        "타는 냄새를 언급했습니다.",
    )
    assert route_evidence(evidence) == route


def test_missing_or_invented_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="exact nonempty source span"):
        validate_evidence(
            '{"evidence":"배터리가 부풀었어요","target":"current","assertion":"observed"}',
            "하판이 솟아올랐어요.",
        )
    with pytest.raises(ValueError, match="empty evidence fields disagree"):
        validate_evidence(
            '{"evidence":null,"target":"current","assertion":"none"}',
            "화면이 꺼져요.",
        )
    for raw, utterance in (
        ('{"evidence":"위험","target":"wrong","assertion":"observed"}', "위험"),
        ('{"evidence":"위험","target":"current","assertion":"wrong"}', "위험"),
        ('{"evidence":"위험","target":"current","assertion":"observed","extra":1}', "위험"),
        ('{"evidence":"   ","target":"current","assertion":"observed"}', "위험   "),
    ):
        with pytest.raises(ValueError):
            validate_evidence(raw, utterance)


def test_reviewed_corpus_change_is_rejected_before_model_call(tmp_path: Path) -> None:
    changed = tmp_path / "changed.json"
    changed.write_bytes(
        (DATA_ROOT / "nlu-safety-confirmation-reviewed.v1.json").read_bytes() + b" "
    )
    with pytest.raises(ValueError, match="SHA-256 differs"):
        probe.load_reviewed_cf_dataset(changed)


def test_empty_completion_choices_become_recordable_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeOpener:
        def open(self, *args: object, **kwargs: object) -> io.BytesIO:
            return io.BytesIO(b'{"choices":[]}')

    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *args: FakeOpener())
    policy = AIHeldoutRequestPolicy.model_validate_json(
        (DATA_ROOT / "q4-q5-request-policy.v1.json").read_bytes()
    )
    with pytest.raises(ValueError, match="choices are empty"):
        probe.post_constrained_completion(
            "http://127.0.0.1:18081/v1/chat/completions", "local", [], policy
        )


def test_request_failure_is_recorded_and_next_case_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_completion(*args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary local request failure")
        return '{"evidence":null,"target":"none","assertion":"none"}'

    monkeypatch.setattr(probe, "post_constrained_completion", fake_completion)
    output = tmp_path / "result.json"
    probe.run(
        argparse.Namespace(
            endpoint="http://127.0.0.1:18081/v1/chat/completions",
            model_id="local",
            dataset=DATA_ROOT / "nlu-safety-confirmation-reviewed.v1.json",
            policy=DATA_ROOT / "q4-q5-request-policy.v1.json",
            output=output,
        )
    )
    rows = json.loads(output.read_text())["rows"]
    assert calls == 32
    assert rows[0]["error_type"] == "OSError"
    assert rows[1]["route"] == "collecting_service_request"
