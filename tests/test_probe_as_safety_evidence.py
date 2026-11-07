"""An evidence gate must reject invented spans and keep uncertainty separate."""

import pytest

from scripts.probe_as_safety_evidence import route_evidence, validate_evidence


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
