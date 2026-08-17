import pytest

from services.call_policy import choose_opening, is_incoming_scenario


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("title", ["보고서 제출", "진행상황 보고", "회의 일정 조율"])
def test_registered_company_scenarios_are_incoming(title):
    assert is_incoming_scenario("회사", title) is True


def test_partial_title_does_not_match_incoming_scenario():
    assert is_incoming_scenario("회사", "보고서 제출 일정 변경") is False


def test_unregistered_incoming_opening_fails_explicitly():
    with pytest.raises(ValueError, match="must be registered"):
        choose_opening("회사", "미등록 업무", incoming=True)
