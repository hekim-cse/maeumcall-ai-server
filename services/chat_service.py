# services/chat_service.py

from llm.prompt_builder import generate_prompts
from schemas.chat_models import ChatRequest
from llm.client import complete_messages  # ✅ 이것만 사용

def build_messages(req: ChatRequest):
    def _norm_role(r: str) -> str:
        r = (r or "").lower()
        if r in {"ai", "assistant", "bot", "agent"}: return "assistant"
        if r in {"user", "system"}: return r
        return ""

    # ❌ generate_prompts(req)를 그대로 system에 넣으면 tuple 타입 오류
    system_prompt, user_prompt = generate_prompts(req)

    msgs = [{"role": "system", "content": system_prompt}]

    hist = getattr(req, "history", None) or getattr(req, "turns", None) or []
    for h in hist:
        role = _norm_role(h.get("role") or h.get("sender"))
        content = h.get("content") or h.get("text")
        if role and content:
            msgs.append({"role": role, "content": content})

    # 여기서는 user에 실제 user_prompt(요약/가드레일 포함)를 사용
    msgs.append({"role": "user", "content": user_prompt})
    return msgs


def complete(req: ChatRequest, timeout_s: int = 8) -> str:
    system_prompt, user_prompt = generate_prompts(req)

    # system 먼저
    messages = [{"role": "system", "content": system_prompt}]

    # ✅ 과거 대화(턴) 먼저 재생
    hist = getattr(req, "turns", None) or getattr(req, "history", None) or []
    for h in hist:
        role = (h.get("role") or h.get("sender") or "").lower()
        if role in {"assistant", "user"}:
            text = h.get("content") or h.get("text") or ""
            if text:
                messages.append({"role": role, "content": text})

    # ✅ 마지막으로 user_prompt 추가 (요약+현재 입력)
    messages.append({"role": "user", "content": user_prompt})

    return complete_messages(messages, timeout_s=timeout_s)