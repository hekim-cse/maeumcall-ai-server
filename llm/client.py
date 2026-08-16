# llm/client.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from core.config import OPENAI_API_KEY, OPENAI_MODEL
import logging
from llm.errors import AIProviderExecutionError, AIProviderUnavailableError

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI as _OpenAIClientRuntime
except ImportError:
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
        logger.debug("OpenAI client disabled (SDK or API key unavailable)")
        return None
    _client = _OpenAIClientRuntime(api_key=OPENAI_API_KEY)
    return _client

def _call_openai_sync(
    model: str,
    messages: List[Dict],
    timeout_s: int = 8,
    *,
    json_mode: bool = False,
) -> str:
    client = _get_client()
    if not client:
        raise AIProviderUnavailableError("OpenAI SDK or API key is unavailable")
    try:
        request: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0 if json_mode else 0.2,
            "presence_penalty": 0 if json_mode else 0.1,
            "timeout": timeout_s,
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(
            **request,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.exception("OpenAI call failed")
        raise AIProviderExecutionError("OpenAI request failed") from exc

def complete_messages(messages: List[Dict], timeout_s: int = 8) -> str:
    return _call_openai_sync(model=OPENAI_MODEL, messages=messages, timeout_s=timeout_s)


def complete_json_messages(messages: List[Dict], timeout_s: int = 8) -> str:
    return _call_openai_sync(
        model=OPENAI_MODEL,
        messages=messages,
        timeout_s=timeout_s,
        json_mode=True,
    )
