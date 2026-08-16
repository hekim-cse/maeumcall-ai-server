from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from llm.system_prompts import build_system_prompt
from schemas.chat_models import ChatRequest
from services.flow.common.scenario_keys import canonicalize_scenario_label
from services.prompt_loader import load_prompt_config


COMMON_CONVERSATION_RULES = """
[대화 규칙]
- 통화의 상대역만 연기하고 AI, 시스템, 해설자 같은 메타 발화를 하지 않는다.
- 현재 시나리오의 역할, 관계, 목표를 유지한다.
- 이전 대화에서 이미 확인된 사실을 다시 묻지 않는다.
- 사용자의 마지막 발화와 전체 대화 기록을 함께 읽고 답한다.
- 한 응답에는 질문 하나 또는 제안 하나만 포함한다.
- 응답은 자연스러운 한국어 1~2문장으로 작성한다.
- 사용자가 명확히 종료 의사를 표현한 경우 질문을 추가하지 않고 짧게 마무리한다.
- 교수님이나 회사 역할은 승인, 거절, 조건부 승인처럼 역할상 직접 내려야 하는 결정을 제3자에게 넘기지 않는다.
""".strip()


REPORT_SUBMISSION_RULES = """
[보고서 제출 시나리오 규칙]
- 사용자의 일정 변경 요청을 자동 승인하지 않는다.
- 지연 원인, 현재 장애 요인, 확정 가능한 제출 시각 중 가장 중요한 정보 하나만 확인한다.
- 정보가 충분하면 승인, 거절, 조건부 승인 중 하나를 분명히 전달한다.
- 업무와 관계없는 사적 대화를 하지 않는다.
""".strip()


def load_scenario_prompt(category: str, title: str) -> Dict[str, Any]:
    config = load_prompt_config(category, title)
    data = asdict(config)
    meta = data.pop("meta", {})
    return {**meta, **data}


def _format_lines(values: List[str], *, empty: str) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in cleaned)


def _is_report_submission_scenario(request: ChatRequest) -> bool:
    return (
        canonicalize_scenario_label(request.category) == "회사"
        and canonicalize_scenario_label(request.title) == "보고서 제출"
    )


def generate_prompts(request: ChatRequest) -> tuple[str, str]:
    """등록된 시나리오 설정으로 시스템·사용자 프롬프트를 구성한다."""
    scenario = load_scenario_prompt(request.category, request.title)
    system_prompt = build_system_prompt(
        category=request.category,
        nickname=request.nickname,
    )

    preferred_expressions = _format_lines(
        scenario.get("prefer", []),
        empty="시나리오와 관계에 맞는 자연스러운 표현",
    )
    prohibited_expressions = _format_lines(
        scenario.get("avoid", []),
        empty="역할을 벗어나는 표현과 과도한 친절 표현",
    )
    topic_hints = _format_lines(
        scenario.get("topic_hints", []),
        empty="사용자의 현재 용건을 우선한다",
    )
    examples = _format_lines(
        list(scenario.get("examples", []))[:8],
        empty="등록된 예시 없음",
    )
    scenario_rules = REPORT_SUBMISSION_RULES if _is_report_submission_scenario(request) else ""

    user_prompt = f"""
{COMMON_CONVERSATION_RULES}
{scenario_rules}

[역할]
- 상대역: {scenario.get('gpt_role', '통화 상대방')}
- 사용자 역할: {scenario.get('user_role', '사용자')}
- 사용자 호칭: {scenario.get('address_user') or '관계에 맞는 호칭'}

[상황]
- 카테고리: {request.category}
- 제목: {request.title}
- 설명: {request.description}

[현재 사용자 발화]
{request.userMessage}

[응답 정책]
- 톤: {scenario.get('tone', '자연스럽고 간결한 한국어 구어체')}
- 권장 표현:
{preferred_expressions}
- 금지 표현:
{prohibited_expressions}
- 대화를 이어갈 때 참고할 주제:
{topic_hints}
- 시나리오 참고 대화:
{examples}

참고 대화는 역할과 진행 목표만 이해하는 데 사용하고 문장을 그대로 복사하지 않는다.
""".strip()
    return system_prompt, user_prompt
