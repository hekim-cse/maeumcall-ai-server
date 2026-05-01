# 📄 services/correction_service.py
from __future__ import annotations
from typing import List, Optional, Dict, Tuple
import re
from schemas.chat_models import ChatMessage
import unicodedata
from llm.client import rewrite_with_llm

def _norm_for_compare(s: str) -> str:
    """구두점/기호/공백을 제거하고 비교용으로 정규화 (NFKC 포함)."""
    s = unicodedata.normalize("NFKC", s)
    # 일반/한중일 구두점, 따옴표류, 괄호류, 중점 등 폭넓게 제거
    s = re.sub(r'[.,!?…·‥:;“”"\'‘’()\[\]{}<>/\\|`~^@#\$%&*_+=-]+', '', s)
    s = re.sub(r'[·ㆍ•‧、，]', '', s)  # 추가로 종종 섞이는 문자
    s = re.sub(r'\s+', '', s)        # 공백 전부 제거
    return s.strip()

def _is_punct_only_change(a: str, b: str) -> bool:
    """구두점/공백만 다른 경우 True."""
    return _norm_for_compare(a) == _norm_for_compare(b)

# ─────────────────────────────────────────
# 카테고리별 톤 가이드
# ─────────────────────────────────────────
CATEGORY_TONE_HINT: Dict[str, str] = {
    "교수님": "존댓말, 과도한 요구 피하기, 일정·맥락 명확히, 정중한 요청형",
    "가족":   "따뜻하고 배려있는 톤, 걱정 덜어주는 어휘, 직설은 부드럽게",
    "친구":   "친근하지만 무례하지 않게, 과격한 표현 순화, 캐주얼 톤 유지",
    "직장상사": "겸손하고 간결, 핵심 먼저, 요청은 근거와 일정 포함",
    "상담원": "정중·명확·간결, 요구·제약·기한 명시, 감정 배제",
    "일반":   "정중·간결·명확",
}

# 공통 정중화 치환(휴리스틱)
BASE_REPL: List[Tuple[str, str]] = [
    (r"\b빨리\b", "가능하실 때"),
    (r"\b당장\b", "가능하실 때"),
    (r"\b안돼요\b", "어려울 것 같아요"),
    (r"\b안돼\b", "조금 어려울 것 같아"),
]

# 카테고리별 추가 치환(휴리스틱)
CATEGORY_REPL: Dict[str, List[Tuple[str, str]]] = {
    "교수님": [
        (r"\b해주세요\b", "부탁드립니다"),
        (r"\b할게요\b", "진행하겠습니다"),
        (r"\b봐주세요\b", "검토 부탁드립니다"),
    ],
    "직장상사": [
        (r"\b해주세요\b", "요청드립니다"),
        (r"\b봐주세요\b", "확인 부탁드립니다"),
    ],
    "상담원": [
        (r"\b가능한가요\b", "가능할지 문의드립니다"),
        (r"\b좀\b", "조금"),
    ],
    "가족": [
        (r"\b빨리\b", "시간 되면"),
        (r"\b지금\b", "지금이나 편할 때"),
    ],
    "친구": [
        (r"\b지금\b", "지금이나 시간 될 때"),
    ],
}

# ─────────────────────────────────────────
# 말투(존댓말/반말) 감지 & 끝맺음 유지
# ─────────────────────────────────────────
def detect_tone_ko(s: str) -> str:
    """
    returns: 'formal' or 'casual'
    - '요', '니다', '세요', '주시겠어요' 등 → formal
    - 명백한 반말 어미('해', '해줘', '할게', '해줄래?')가 보이면 casual
    - 혼재 시: 존댓말 우선
    """
    t = s.strip()
    if not t:
        return "formal"

    formal_hits = [
        r"요[.?!]?$", r"니다[.?!]?$", r"세요[.?!]?$", r"십시오", r"주시겠[어요]?", "부탁드립니다", "요청드립니다"
    ]
    casual_hits = [
        r"해[.?!]?$", r"해줘[.?!]?$", r"할게[.?!]?$", r"줄래[?]?$", r"해라[.?!]?$"
    ]
    if any(re.search(p, t) for p in formal_hits):
        return "formal"
    if any(re.search(p, t) for p in casual_hits):
        return "casual"
    # 존댓말 단서가 있으면 formal 우선
    polite_tokens = ["죄송", "감사", "부탁", "실례", "가능하실", "괜찮으실까요"]
    if any(k in t for k in polite_tokens):
        return "formal"
    return "casual"

def finish_sentence_preserving_tone(text: str, tone: str) -> str:
    """
    ✅ 문장부호를 강제로 추가하지 않는다.
    - 원문이 ?/./! 없이 끝나도 그대로 둔다 (구어체 보존).
    - 오탈자 교정 외에는 구두점 미세교정 금지.
    """
    return text.strip()

# ─────────────────────────────────────────
# 휴리스틱 재작성 (카테고리 + 말투 유지)
# ─────────────────────────────────────────
def heuristic_rewrite(text: str, category: str, tone: str) -> str:
    # ✅ 첫 통화 인사말은 그대로 둔다
    if text.strip() in {"여보세요", "여보세요?", "여보세요."}:
        return text.strip()

    t = text
    repls = list(BASE_REPL)
    if tone == "formal":
        repls.append((r"\b지금\b", "지금 혹은 편하실 때"))
    else:
        repls.append((r"\b지금\b", "지금이나 시간 될 때"))

    for pat, rep in repls:
        t = re.sub(pat, rep, t)

    if category in CATEGORY_REPL:
        for pat, rep in CATEGORY_REPL[category]:
            t = re.sub(pat, rep, t)

    return t.strip()

# ─────────────────────────────────────────
# 라벨 추정
# ─────────────────────────────────────────
def guess_tags(original: str, improved: str) -> List[str]:
    tags: List[str] = []
    if len(improved) < len(original) - 3:
        tags.append("길이↓")
    elif len(improved) > len(original) + 3:
        tags.append("길이↑")
    polite_tokens = ["가능하실 때","부탁","감사","실례","괜찮으실까요","주시겠어요","부탁드립니다","요청드립니다"]
    if any(tok in improved for tok in polite_tokens):
        tags.append("정중함↑")
    if re.search(r"\d", improved) or re.search(r"(오늘|내일|이번|다음|시간|분|시|요일)", improved):
        tags.append("명확성↑")
    return tags or ["자연스러움↑"]

# ─────────────────────────────────────────
# 메인 엔트리: 메시지 개선
# ─────────────────────────────────────────
async def improve_messages(messages: List[ChatMessage], category: Optional[str]):
    cat = (category or "일반").strip()
    if cat not in CATEGORY_TONE_HINT:
        cat = "일반"

    improved: List[Optional[str]] = [None] * len(messages)
    tags: List[Optional[List[str]]] = [None] * len(messages)

    for i, m in enumerate(messages):
        text = (m.text or "").strip()
        if not text or m.role != "user":
            continue

        tone = detect_tone_ko(text)
        system_hint = (
            "역할: 한국어 문장 재작성기.\n"
            f"목표: {CATEGORY_TONE_HINT[cat]}.\n"
            "핵심: **의미/톤/정중함**만 보완. 맞춤법이 명백히 틀린 경우만 최소한으로 수정.\n"
            "다음은 절대 수정하지 마세요:\n"
            "- 문장부호/띄어쓰기의 미세한 취향 차이(예: '응 괜찮아'에 쉼표/마침표 추가 금지)\n"
            "- 감탄사/짧은 반응(응, 어, 네, 웅, 그래, 알겠어 등)의 구두점 추가/변경 금지\n"
            "- 구어체 어조(반말/존댓말)와 줄바꿈, 이모지, 반복 글자(헉, ㅎㅎ 등) 보존\n"
            "- '여보세요' 같은 첫 통화 인사말은 그대로 유지\n"
            "출력: 한 줄. 불필요한 쉼표/마침표/따옴표를 새로 추가하지 마세요.\n"
            f"현재 메시지 말투: { '존댓말' if tone=='formal' else '반말' }.\n"
        )

        llm_out = await rewrite_with_llm(text=text, system_hint=system_hint)
        if llm_out:
            new_text = finish_sentence_preserving_tone(llm_out, tone)
        else:
            new_text = heuristic_rewrite(text=text, category=cat, tone=tone)

        # ✅ 구두점/공백만 다른 경우 → 개선 없음 처리
        if _is_punct_only_change(text, new_text):
            improved[i] = None
            tags[i] = None
        else:
            improved[i] = new_text.strip()
            tags[i] = guess_tags(original=text, improved=new_text)

    return improved, tags