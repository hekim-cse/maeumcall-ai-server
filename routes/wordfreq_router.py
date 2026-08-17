# routes/wordfreq_router.py
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Dict, List, Literal, Optional, Tuple
from collections import Counter
import re, unicodedata

router = APIRouter(prefix="/analysis", tags=["analysis"])

FILLERS = {
    "어","음","아","에","어어","음음","그냥","약간","뭔가","그..","음..","어..","그럼","그러니까",
    "진짜","되게","좀","막","그렇죠","뭐지","아니","어쩌지","그","그러네","뭐랄까","일단"
}

STOPWORDS = {
    "은","는","이","가","을","를","에","의","과","와","도","만","에서","에게","부터","까지",
    "근데","그리고","하지만","그래서","또","혹시","좀","너무"
}

def _normalize_line(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r'[~`^"\'“”‘’(){}<>/\\|@#\$%\^&\*_+=:;]', " ", s)
    s = re.sub(r"[.,!?…‥·ㆍ•‧、，]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokenize(messages: List[str]) -> List[str]:
    toks: List[str] = []
    for line in messages:
        line = _normalize_line(line or "")
        if not line:
            continue
        toks.extend([t for t in line.split(" ") if t])
    return toks

# ---------- 공통 헬퍼: 사용자 메시지 추출 ----------
class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user","assistant","system"]
    text: str = Field(min_length=1, max_length=4_000)

# ─────────────────────────────────────────────────────────
# ① 단일 엔드포인트 (/analysis/wordfreq)
# ─────────────────────────────────────────────────────────
class WordFreqRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: Optional[List[str]] = Field(default=None, max_length=1_000)
    turns: Optional[List[Turn]] = Field(default=None, max_length=1_000)
    scope: Literal["user", "assistant", "all"] = "user"
    top_k: int = Field(default=5, ge=1, le=100)
    min_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "WordFreqRequest":
        if (self.messages is None) == (self.turns is None):
            raise ValueError("exactly one of messages or turns is required")
        return self

@router.post("/wordfreq")
def wordfreq_single(req: WordFreqRequest):
    # ⬇︎ 여기 한 줄로 사용자만/어시만/전체 중 필터 적용
    user_texts = _select_texts(req.messages, req.turns, req.scope)

    tokens = _tokenize(user_texts)
    total_words = len(tokens)
    # 이하 기존 로직 동일
    fill_toks = [t for t in tokens if t in FILLERS]
    c_fill = Counter(fill_toks)

    word_toks = [t for t in tokens if t not in FILLERS and t not in STOPWORDS and len(t) > 1]
    c_words = Counter(word_toks)

    def filt_top(c: Counter, min_cnt: int) -> List[Tuple[str, int]]:
        arr = [(w, n) for (w, n) in c.most_common(100) if n >= min_cnt]
        return arr[:req.top_k]

    top_words   = filt_top(c_words, req.min_count)
    top_fillers = filt_top(c_fill,  req.min_count)

    filler_count = sum(c_fill.values())
    filler_ratio = round((filler_count / total_words) * 100, 1) if total_words else 0.0

    return {
        "scope": req.scope,  # ← 응답에 무엇을 집계했는지 표시(디버그용)
        "total_messages": len(user_texts),
        "total_words": total_words,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
        "top_words": top_words,
        "top_fillers": top_fillers,
        "top_k": req.top_k,
        "min_count": req.min_count,
    }

# ─────────────────────────────────────────────────────────
# ② 카테고리 집계 (/analysis/wordfreq/by-category)
# ─────────────────────────────────────────────────────────
class WordFreqByCategoryItem(BaseModel):
    category: str
    messages: Optional[List[str]] = Field(default=None, max_length=1_000)
    turns: Optional[List[Turn]] = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "WordFreqByCategoryItem":
        if (self.messages is None) == (self.turns is None):
            raise ValueError("exactly one of messages or turns is required")
        return self

class WordFreqByCategoryRequest(BaseModel):
    items: List[WordFreqByCategoryItem]
    scope: Literal["user", "assistant", "all"] = "user"
    top_k: int = Field(default=5, ge=1, le=100)
    min_count_words: int = Field(default=2, ge=1)
    min_count_fillers: int = Field(default=2, ge=1)

@router.post("/wordfreq/by-category")
def wordfreq_by_category(req: WordFreqByCategoryRequest):
    summary: Dict[str, Dict] = {}
    for item in req.items:
        user_texts = _select_texts(item.messages, item.turns, req.scope)

        tokens = _tokenize(user_texts)
        total_words = len(tokens)

        fill_toks = [t for t in tokens if t in FILLERS]
        c_fill = Counter(fill_toks)

        word_toks = [t for t in tokens if t not in FILLERS and t not in STOPWORDS and len(t) > 1]
        c_words = Counter(word_toks)

        def filt_top_words(c: Counter) -> List[Tuple[str, int]]:
            arr = [(w, n) for (w, n) in c.most_common(100) if n >= req.min_count_words]
            return arr[:req.top_k]

        def filt_top_fillers(c: Counter) -> List[Tuple[str, int]]:
            arr = [(w, n) for (w, n) in c.most_common(100) if n >= req.min_count_fillers]
            return arr[:req.top_k]

        top_words   = filt_top_words(c_words)
        top_fillers = filt_top_fillers(c_fill)

        filler_count = sum(c_fill.values())
        filler_ratio = round((filler_count / total_words) * 100, 1) if total_words else 0.0

        summary[item.category] = {
            "scope": req.scope,
            "total_messages": len(user_texts),
            "total_words": total_words,
            "filler_count": filler_count,
            "filler_ratio": filler_ratio,
            "top_words": top_words,
            "top_fillers": top_fillers,
        }

    return {
        "top_k": req.top_k,
        "min_count_words": req.min_count_words,
        "min_count_fillers": req.min_count_fillers,
        "categories": summary,
    }

# ─────────────────────────────────────────
# 공통 유틸: 입력(normalize) + 역할별 필터
# ─────────────────────────────────────────
def _select_texts(
    messages: Optional[List[str]],
    turns: Optional[List[Turn]],
    scope: Literal["user", "assistant", "all"],
) -> List[str]:
    if turns is not None:
        return [
            turn.text
            for turn in turns
            if scope == "all" or turn.role == scope
        ]
    return [message.strip() for message in (messages or []) if message.strip()]
