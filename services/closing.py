# services/closing.py
from __future__ import annotations
import random
import re
from typing import Optional

CLOSING_TRIGGERS = [
    "네 감사합니다","감사합니다","고맙습니다","넵","네 수고하셨습니다","수고하세요",
    "그럼 이만","다음에 뵙겠습니다","들어가세요","연락드릴게요","여기까지","끝","종료",
    "끊어","끊을게","끊겠습니다","끊는다","수고요","수고했습니다","고생하셨습니다"
]

_thanks_kw = ("감사", "고맙")
_bye_kw    = ("들어가세요","수고","안녕","또 연락","다음에","끊")
_apol_kw   = ("죄송","미안")

def is_closing_utterance(s: str) -> bool:
    t = (s or "").strip()
    if not t: return False
    return any(k in t for k in CLOSING_TRIGGERS)

def _is_formal(s: str) -> bool:
    # 아주 러프하게: '요/니다/세요/부탁/감사' 등 포함 → 존댓말
    t = (s or "").strip()
    if not t: return True
    return bool(re.search(r"(요$|니다$|세요$|십시오|부탁|감사)", t))

def _intent(s: str) -> str:
    t = (s or "").strip()
    if any(k in t for k in _apol_kw):   return "apology"
    if any(k in t for k in _thanks_kw): return "thanks"
    if any(k in t for k in _bye_kw):    return "bye"
    return "neutral"

_TEMPLATES = {
    "교수님": {
        "formal": {
            "thanks": ["네, 감사합니다.", "네, 수고하세요.", "네, 다음 일정대로 진행하겠습니다."],
            "bye":    ["네, 여기서 마무리하겠습니다.", "네, 들어가세요.", "네, 이만 끊겠습니다."],
            "apology":["네, 다음엔 일정만 미리 알려주세요.", "네, 이해했습니다. 일정은 지켜주세요."],
            "neutral":["네, 알겠습니다.", "네, 그렇게 하죠."]
        }
    },
    "회사": {
        "formal": {
            "thanks": ["네, 수고하세요.", "네, 감사합니다."],
            "bye":    ["네, 여기까지 하겠습니다.", "네, 이만 끊겠습니다."],
            "apology":["네, 다음엔 사전 공유 부탁드립니다.", "네, 재발 방지 계획만 정리해 주세요."],
            "neutral":["네, 정리해서 공유하겠습니다.", "네, 그렇게 진행하죠."]
        }
    },
    # 기본(다른 카테고리)
    "_default": {
        "formal": {
            "thanks": ["네, 감사합니다.", "네, 수고하세요."],
            "bye":    ["네, 들어가세요.", "네, 여기서 마무리할게요."],
            "apology":["네, 괜찮습니다. 다음엔 미리 알려주세요."],
            "neutral":["네, 알겠습니다."]
        },
        "casual": {
            "thanks": ["응, 고마워.", "응, 수고!",],
            "bye":    ["응, 이만 끊자.", "응, 들어가~"],
            "apology":["응, 괜찮아. 다음엔 미리 말해줘."],
            "neutral":["응, 알겠어."]
        }
    }
}

def closing_line(category: Optional[str], user_msg: Optional[str] = "") -> str:
    cat = (category or "").strip()
    intent = _intent(user_msg or "")
    formal = _is_formal(user_msg or "")

    bank = _TEMPLATES.get(cat) or _TEMPLATES["_default"]
    style = "formal" if formal else "casual"
    bank_style = bank.get(style) or _TEMPLATES["_default"][style]

    choices = bank_style.get(intent) or bank_style["neutral"]
    # 중복 방지를 원하면 random.choice 대신 random.sample 후 첫 개 등으로 관리 가능
    return random.choice(choices)