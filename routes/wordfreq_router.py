from __future__ import annotations

import asyncio
from collections import Counter
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from services.korean_text_analyzer import KoreanTextAnalysis, korean_text_analyzer


router = APIRouter(prefix="/analysis", tags=["analysis"])

MessageText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]
Scope = Literal["user", "assistant", "all"]


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant", "system"]
    text: MessageText


class WordFreqRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: Optional[List[MessageText]] = Field(default=None, max_length=1_000)
    turns: Optional[List[Turn]] = Field(default=None, max_length=1_000)
    scope: Scope = "user"
    top_k: int = Field(default=5, ge=1, le=100)
    min_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "WordFreqRequest":
        if (self.messages is None) == (self.turns is None):
            raise ValueError("exactly one of messages or turns is required")
        return self


class WordFreqByCategoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=100)
    messages: Optional[List[MessageText]] = Field(default=None, max_length=1_000)
    turns: Optional[List[Turn]] = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "WordFreqByCategoryItem":
        if (self.messages is None) == (self.turns is None):
            raise ValueError("exactly one of messages or turns is required")
        return self


class WordFreqByCategoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WordFreqByCategoryItem] = Field(min_length=1, max_length=100)
    scope: Scope = "user"
    top_k: int = Field(default=5, ge=1, le=100)
    min_count_words: int = Field(default=2, ge=1)
    min_count_fillers: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def require_unique_categories(self) -> "WordFreqByCategoryRequest":
        categories = [item.category for item in self.items]
        if len(categories) != len(set(categories)):
            raise ValueError("category values must be unique")
        return self


@router.post("/wordfreq")
async def wordfreq_single(req: WordFreqRequest):
    texts = _select_texts(req.messages, req.turns, req.scope)
    analysis = await asyncio.to_thread(korean_text_analyzer.analyze, texts)
    return _serialize_analysis(
        analysis,
        scope=req.scope,
        total_messages=len(texts),
        top_k=req.top_k,
        min_count_words=req.min_count,
        min_count_fillers=req.min_count,
    ) | {"top_k": req.top_k, "min_count": req.min_count}


@router.post("/wordfreq/by-category")
async def wordfreq_by_category(req: WordFreqByCategoryRequest):
    summary: Dict[str, Dict] = {}
    for item in req.items:
        texts = _select_texts(item.messages, item.turns, req.scope)
        analysis = await asyncio.to_thread(korean_text_analyzer.analyze, texts)
        summary[item.category] = _serialize_analysis(
            analysis,
            scope=req.scope,
            total_messages=len(texts),
            top_k=req.top_k,
            min_count_words=req.min_count_words,
            min_count_fillers=req.min_count_fillers,
        )

    return {
        "top_k": req.top_k,
        "min_count_words": req.min_count_words,
        "min_count_fillers": req.min_count_fillers,
        "categories": summary,
    }


def _serialize_analysis(
    analysis: KoreanTextAnalysis,
    *,
    scope: Scope,
    total_messages: int,
    top_k: int,
    min_count_words: int,
    min_count_fillers: int,
) -> Dict:
    filler_count = sum(analysis.fillers.values())
    filler_ratio = (
        round((filler_count / analysis.total_words) * 100, 1)
        if analysis.total_words
        else 0.0
    )
    return {
        "scope": scope,
        "total_messages": total_messages,
        "total_words": analysis.total_words,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
        "top_words": _top_counts(analysis.words, min_count_words, top_k),
        "top_fillers": _top_counts(analysis.fillers, min_count_fillers, top_k),
    }


def _top_counts(
    counts: Counter[str],
    minimum: int,
    limit: int,
) -> List[Tuple[str, int]]:
    return [(form, count) for form, count in counts.most_common() if count >= minimum][
        :limit
    ]


def _select_texts(
    messages: Optional[List[str]],
    turns: Optional[List[Turn]],
    scope: Scope,
) -> List[str]:
    if turns is not None:
        return [turn.text for turn in turns if scope == "all" or turn.role == scope]
    return list(messages or [])
