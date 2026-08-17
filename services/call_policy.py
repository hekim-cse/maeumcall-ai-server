import random

from services.flow.common.scenario_keys import canonicalize_scenario_label


COMPANY_INCOMING_OPENINGS = {
    "보고서 제출": (
        "전산팀입니다. 이번 주 수요일까지 제출하기로 한 보고서, 언제까지 올리실 수 있습니까?",
        "전산팀입니다. 보고서 마감 일정 확인 건입니다. ETA를 구체적으로 말씀해 주십시오.",
        "전산팀입니다. 보고서 마감 건으로 연락드렸습니다. 오늘 중 제출 가능합니까?",
        "전산팀입니다. 보고서 제출 일정 확인하려고 연락드렸습니다. 정확한 제출 시점 말씀해 주세요.",
        "전산팀입니다. 보고서 제출 지연 사유와 보완 일정 제출 바랍니다.",
    ),
    "진행상황 보고": (
        "전산팀입니다. 이번 프로젝트 진행 현황 간단히 브리핑해 주시죠. 지금 바로 가능합니까?",
        "전산팀입니다. 진행 상황 업데이트 필요합니다. 핵심만 바로 보고해 주세요.",
        "전산팀입니다. 현재까지 달성률과 리스크 요인 짚어서 보고해 주세요.",
    ),
    "회의 일정 조율": (
        "전산팀입니다. 오늘 4시 회의를 5시로 미루고자 합니다. 조정 가능합니까?",
        "전산팀입니다. 회의 시간을 1시간 뒤로 이동하려 합니다. 가능 여부 지금 확인해 주세요.",
        "전산팀입니다. 회의 조정 건입니다. 5시로 재조정 문제없습니까?",
    ),
}

def is_incoming_scenario(category: str, title: str) -> bool:
    return (
        canonicalize_scenario_label(category) == "회사"
        and canonicalize_scenario_label(title) in COMPANY_INCOMING_OPENINGS
    )

def random_connect_delay_ms() -> int:
    return random.choice([1000, 2000, 3000])

def _company_incoming_opening(title: str) -> str:
    normalized_title = canonicalize_scenario_label(title)
    try:
        variants = COMPANY_INCOMING_OPENINGS[normalized_title]
    except KeyError as exc:
        raise ValueError("incoming company scenario must be registered") from exc
    return random.choice(variants)

def choose_opening(category: str, title: str, *, incoming: bool = False) -> str:
    """
    incoming=True  → 상대가 먼저 용건을 제시(회사 3개 케이스)
    incoming=False → 수신자가 '용건 확인'으로 받음
    """
    if category == '회사' and incoming:
        # ✅ 회사-수신(상대가 거는 전화): 바로 용건 제시
        return _company_incoming_opening(title)

    # 그 외: 중립 오프닝 + 용건 확인
    variants = [
        "네, 전화 받았습니다. 무슨 용건이신가요?",
        "네, 연결됐습니다. 어떤 일로 전화하셨죠?",
        "네. 어떤 용건으로 전화 주셨을까요?",
    ]
    return random.choice(variants)
