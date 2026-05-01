# 📄 services/etiquette.py
from __future__ import annotations
import re
from typing import List, Dict, Optional

def _count_user_turns(turns: List[Dict[str, str]]) -> int:
    return sum(1 for t in (turns or []) if (t.get("role") or "").lower() == "user")

def _has_intro(text: str) -> bool:
    t = (text or "").strip()
    if not t: return False
    has_greeting   = re.search(r"(안녕하세요|안녕하십니까)", t) is not None
    has_affiliation= re.search(r"(학과|학번|학생|팀|부서|회사|과목|과제)", t) is not None
    has_introverb  = re.search(r"(입니다|드립니다|전화드렸습니다|연락드렸습니다)", t) is not None
    # 신원/소속+용건 중 2개 이상 있으면 충분하다고 봄
    return sum([has_greeting, has_affiliation, has_introverb]) >= 2

def maybe_get_etiquette_tip(category: str, turns: List[Dict[str,str]], user_message: str) -> Optional[str]:
    cat = (category or "").strip()
    if cat not in {"교수님", "회사"}:
        return None
    # 초반 2턴까지만 권고
    if _count_user_turns(turns) >= 2:
        return None
    if _has_intro(user_message):
        return None
    return (
        "교수님과 통화할 때는 신원을 먼저 밝힌 뒤, 한 줄로 용건을 간단히 말씀하고 시작하는 게 좋아요."
        if cat == "교수님"
        else "회사 통화에서는 신원을 먼저 밝히고, 용건을 한 줄로 간단히 전한 뒤 본론으로 들어가는 게 좋아요."
    )