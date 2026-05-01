# -*- coding: utf-8 -*-
import random

INCOMING_TITLES_FOR_COMPANY = {"보고서 제출", "진행상황 보고", "회의 일정 조율"}

def is_incoming_scenario(category: str, title: str) -> bool:
    # ✅ 회사의 아래 3개는 '상대가 먼저 전화' → 수신(True)
    if category == '회사':
        t = (title or "").strip()
        if any(k in t for k in INCOMING_TITLES_FOR_COMPANY):
            return True
        # 그 외 회사 시나리오는 발신(False)
        return False
    # 회사 외는 기본 발신(False)
    return False

def random_connect_delay_ms() -> int:
    return random.choice([1000, 2000, 3000])

def _company_incoming_opening(title: str) -> str:
    t = (title or "").strip()
    # 🔻 상황별 “용건 먼저” 오프닝(여러 버전 중 랜덤)
    if "보고서 제출" in t:
        variants = [
            "전산팀입니다. 이번 주 수요일까지 제출하기로 한 보고서, 언제까지 올리실 수 있습니까?",
            "전산팀입니다. 보고서 마감 일정 확인 건입니다. ETA를 구체적으로 말씀해 주십시오.",
            "전산팀입니다. 보고서 마감 건으로 연락드렸습니다. 오늘 중 제출 가능합니까?",
            "전산팀입니다. 보고서 제출 일정 확인하려고 연락드렸습니다. 정확한 제출 시점 말씀해 주세요.",
            "전산팀입니다. 보고서 제출 지연 사유와 보완 일정 제출 바랍니다.",
        ]
    elif "진행상황 보고" in t:
        variants = [
            "전산팀입니다. 이번 프로젝트 진행 현황 간단히 브리핑해 주시죠. 지금 바로 가능합니까?",
            "전산팀입니다. 진행 상황 업데이트 필요합니다. 핵심만 바로 보고해 주세요.",
            "전산팀입니다. 현재까지 달성률과 리스크 요인 짚어서 보고해 주세요.",
        ]
    elif "회의 일정 조율" in t:
        variants = [
            "전산팀입니다. 오늘 4시 회의를 5시로 미루고자 합니다. 조정 가능합니까?",
            "전산팀입니다. 회의 시간을 1시간 뒤로 이동하려 합니다. 가능 여부 지금 확인해 주세요.",
            "전산팀입니다. 회의 조정 건입니다. 5시로 재조정 문제없습니까?",
        ]
    else:
        variants = [
            "전산팀입니다. 용건이 있어 연락드렸습니다. 지금 통화 가능하십니까?",
        ]
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