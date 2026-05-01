# llm/postprocessor.py
import re

_LABEL_RE = re.compile(r"\s*\((?:A|F|S)\)\s*")

def strip_labels(text: str) -> str:
    if not text:
        return text
    text = _LABEL_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()

def demote_question_if_repeated(text: str, turns) -> str:
    if not text or "?" not in text:
        return text
    last_q = ""
    for t in reversed(turns or []):
        if (t.get("role") == "assistant") and "?" in (t.get("text") or t.get("content") or ""):
            last_q = (t.get("text") or t.get("content") or "").strip()
            break
    if not last_q:
        return text
    if text.endswith("?"):
        text = text[:-1] + "."
    else:
        text = text.replace("?", ".", 1)
    return re.sub(r"(먹었|했|갔|잤)어\.", r"\1어.", text)

SMALLTALK_KWS = ["날씨", "건강은", "주말", "요즘", "밥은", "식사는", "괜찮으신가요", "잘 지내", "감기"]

def strip_smalltalk_for_strict_categories(text: str, category: str) -> str:
    if category not in {"회사", "교수님"}:
        return text
    # 사적 키워드가 있고 문장이 2개 이상이면, 첫 문장만 남기거나
    # 사적 문장을 제거 (간단 로직)
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    def is_smalltalk(s): return any(k in s for k in SMALLTALK_KWS)
    filtered = [s for s in sents if not is_smalltalk(s)]
    return " ".join(filtered) if filtered else text