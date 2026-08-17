import pytest

from schemas.chat_models import ChatRequest
from services.flow.scenario import graph as graph_module
from services.flow.scenario.registry import SCENARIOS, get_scenario_config
from services.flow.scenario.response import complete_scenario_graph_if_supported

pytestmark = pytest.mark.graph_flow


@pytest.mark.parametrize("config", list(SCENARIOS.values()), ids=lambda item: item.key)
def test_all_registered_scenarios_route_through_graph(monkeypatch, config):
    monkeypatch.setattr(
        graph_module,
        "complete_json_messages",
        lambda messages: (
            '{"action":"continue","response":"상황을 이어서 말씀해 주세요.","etiquette_tip":null}'
        ),
    )
    request = ChatRequest(
        category=config.category,
        title=f"📞 {config.title}",
        description="모바일 시나리오",
        userMessage="상황을 말씀드릴게요.",
    )

    response = complete_scenario_graph_if_supported(request)

    assert response is not None
    assert response.response == "상황을 이어서 말씀해 주세요."
    assert response.conversationState == "active"
    assert response.shouldEndCall is False
    assert len(response.recommendedReplies) == 3
    assert response.scenarioState["scenario_key"] == config.key
    assert response.scenarioState["turn_count"] == 1
    assert response.simulation.mode == "simulation"
    assert response.simulation.externalEffect is False


def test_scenario_graph_preserves_turn_count(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "complete_json_messages",
        lambda messages: (
            '{"action":"continue","response":"응, 이어서 말해줘.","etiquette_tip":null}'
        ),
    )
    request = ChatRequest(
        category="친구",
        title="🗣 심심해서 거는 전화",
        description="편한 통화",
        userMessage="아까 이야기 이어서 할게.",
        conversationState="active",
        scenarioState={
            "scenario_key": "친구:심심해서 거는 전화",
            "state_version": 2,
            "conversation_state": "active",
            "turn_count": 2,
        },
    )

    response = complete_scenario_graph_if_supported(request)

    assert response.scenarioState["turn_count"] == 3
    assert response.response == "응, 이어서 말해줘."


def test_scenario_graph_ends_call_from_validated_model_action(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "complete_json_messages",
        lambda messages: (
            '{"action":"end","response":"문의해 주셔서 감사합니다.","etiquette_tip":null}'
        ),
    )
    request = ChatRequest(
        category="회사",
        title="📄 보고서 제출",
        description="보고서 제출 문의",
        userMessage="네, 감사합니다.",
    )

    response = complete_scenario_graph_if_supported(request)

    assert response.conversationState == "END"
    assert response.shouldEndCall is True
    assert response.recommendedReplies == []


def test_unknown_scenario_is_not_claimed_by_registry():
    request = ChatRequest(
        category="기타",
        title="등록되지 않은 상황",
        description="",
        userMessage="안녕하세요.",
    )

    assert complete_scenario_graph_if_supported(request) is None


def test_registry_normalizes_emoji_and_spacing():
    assert get_scenario_config(" 친구 ", "🎉 생일 축하 전화") is not None


def test_scenario_graph_appends_current_message_after_prior_history(monkeypatch):
    captured = {}

    def complete(messages):
        captured["messages"] = messages
        return '{"action":"continue","response":"확인했습니다.","etiquette_tip":null}'

    monkeypatch.setattr(graph_module, "complete_json_messages", complete)
    request = ChatRequest(
        category="친구",
        title="심심해서 거는 전화",
        description="편한 통화",
        userMessage="지금 통화 괜찮아?",
        turns=[{"role": "assistant", "text": "응, 지금은 괜찮아."}],
    )

    complete_scenario_graph_if_supported(request)

    occurrence_count = sum(
        message["content"].count("지금 통화 괜찮아?") for message in captured["messages"]
    )
    assert occurrence_count == 1
