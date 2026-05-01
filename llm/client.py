# llm/client.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from core.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODEL_SUGGEST, OPENAI_MODEL_REWRITE
import asyncio

try:
    from openai import OpenAI as _OpenAIClientRuntime
except Exception:
    _OpenAIClientRuntime = None

if TYPE_CHECKING:
    from openai import OpenAI as OpenAIClient
else:
    OpenAIClient = Any  # type: ignore

_client: Optional[OpenAIClient] = None

def _get_client() -> Optional[OpenAIClient]:
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY or _OpenAIClientRuntime is None:
        print("ℹ️ OpenAI client disabled (no SDK or no API key).")
        return None
    _client = _OpenAIClientRuntime(api_key=OPENAI_API_KEY)
    return _client

def _call_openai_sync(model: str, messages: List[Dict], timeout_s: int = 8) -> str:
    client = _get_client()
    if not client:
        return ""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,              # 0.15 → 0.2
            presence_penalty=0.1,         # ⬅︎ 선택 추가
            timeout=timeout_s,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"❌ OpenAI call failed: {e}")
        return ""

def call_gpt(prompt: str, timeout_s: int = 8) -> str:
    return _call_openai_sync(
        model=OPENAI_MODEL_SUGGEST,
        messages=[{"role": "user", "content": prompt}],
        timeout_s=timeout_s,
    )

def complete_messages(messages: List[Dict], timeout_s: int = 8) -> str:
    return _call_openai_sync(model=OPENAI_MODEL, messages=messages, timeout_s=timeout_s)

async def rewrite_with_llm(text: str, system_hint: str, timeout_s: int = 8) -> Optional[str]:
    if not OPENAI_API_KEY or _OpenAIClientRuntime is None:
        return None
    def _sync() -> str:
        msgs = [{"role": "system", "content": system_hint},
                {"role": "user", "content": f"다음 문장을 같은 의미로 간결하게 재작성해 주세요. 문장 1개만.\n\n문장: {text}"}]
        return _call_openai_sync(model=OPENAI_MODEL_REWRITE, messages=msgs, timeout_s=timeout_s)
    try:
        out = await asyncio.to_thread(_sync)
        return out or None
    except Exception:
        return None