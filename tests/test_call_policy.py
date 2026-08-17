import pytest

from services.call_policy import CALL_POLICY_REGISTRY, create_call_plan
from services.flow.common.state_contract import build_scenario_key
from services.flow.registry import FLOW_REGISTRY


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("title", ["보고서 제출", "진행상황 보고", "회의 일정 조율"])
def test_registered_company_scenarios_are_incoming(title):
    plan = create_call_plan(build_scenario_key("회사", title))

    assert plan.direction == "incoming"
    assert plan.delay_ms == 0


def test_partial_title_does_not_match_incoming_scenario():
    with pytest.raises(ValueError, match="must be registered"):
        create_call_plan(build_scenario_key("회사", "보고서 제출 일정 변경"))


def test_unregistered_incoming_opening_fails_explicitly():
    with pytest.raises(ValueError, match="must be registered"):
        create_call_plan(build_scenario_key("회사", "미등록 업무"))


def test_every_registered_scenario_has_exactly_one_call_policy():
    assert set(CALL_POLICY_REGISTRY) == set(FLOW_REGISTRY)


def test_non_incoming_registered_scenario_is_outgoing():
    plan = create_call_plan(build_scenario_key("예약", "병원 예약"))

    assert plan.direction == "outgoing"
    assert plan.delay_ms in {1_000, 2_000, 3_000}
