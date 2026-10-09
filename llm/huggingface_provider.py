# llm/huggingface_provider.py
from __future__ import annotations

import logging
import threading
import time

from core.config import (
    HF_LOCAL_FILES_ONLY,
    HF_LOCAL_MODEL_ENABLED,
    HF_MODEL_DTYPE,
    HF_MODEL_NAME,
    HF_MODEL_REVISION,
)
from llm.errors import AIProviderExecutionError, AIProviderUnavailableError

# Uvicorn configures this logger at INFO; module loggers otherwise inherit the
# process default WARNING level and hide the latency measurements.
logger = logging.getLogger("uvicorn.error.maeumcall.huggingface")

_tokenizer = None
_model = None
_loaded_model_name: str | None = None
_loaded_model_revision: str | None = None
_MODEL_LOCK = threading.Lock()


def local_model_ready() -> bool:
    """Report whether the configured model and tokenizer are loaded in this process."""
    if not HF_LOCAL_MODEL_ENABLED:
        return False
    with _MODEL_LOCK:
        return (
            _tokenizer is not None
            and _model is not None
            and _loaded_model_name == HF_MODEL_NAME
            and _loaded_model_revision == HF_MODEL_REVISION
        )


def _get_device_dtype():
    """
    Mac M 계열에서는 MPS 사용 가능 여부를 확인한다.
    단, fast CI에서는 torch import 자체가 collection 단계에서 부담이 되므로
    실제 필요한 시점에만 torch를 import한다.
    """
    import torch

    if HF_MODEL_DTYPE:
        return getattr(torch, HF_MODEL_DTYPE)
    if torch.cuda.is_available():
        return torch.float16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.float16
    return torch.float32


def load_hf_model(
    model_name: str = HF_MODEL_NAME,
    revision: str = HF_MODEL_REVISION,
):
    """
    Hugging Face 모델을 최초 1회만 로드한다.
    서버 요청마다 모델을 다시 로드하면 너무 느리므로 전역 캐시를 사용한다.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    global _tokenizer, _model, _loaded_model_name, _loaded_model_revision

    with _MODEL_LOCK:
        if (
            _tokenizer is not None
            and _model is not None
            and _loaded_model_name == model_name
            and _loaded_model_revision == revision
        ):
            return _tokenizer, _model

        load_started_at = time.perf_counter()
        logger.info("Loading Hugging Face model: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            local_files_only=HF_LOCAL_FILES_ONLY,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            revision=revision,
            dtype=_get_device_dtype(),
            device_map="auto",
            local_files_only=HF_LOCAL_FILES_ONLY,
        )
        model.eval()
        _tokenizer = tokenizer
        _model = model
        _loaded_model_name = model_name
        _loaded_model_revision = revision
        logger.info(
            "Hugging Face model loaded: %s load_seconds=%.2f",
            model_name,
            time.perf_counter() - load_started_at,
        )
        return _tokenizer, _model


def _messages_to_prompt(tokenizer, messages: list[dict[str, str]]) -> str:
    """Use the configured tokenizer's chat template or fail explicitly."""
    normalized_messages = []

    for message in messages:
        role = (message.get("role") or "user").strip()
        content = (message.get("content") or "").strip()

        if not content:
            continue

        if role not in {"system", "user", "assistant"}:
            role = "user"

        normalized_messages.append(
            {
                "role": role,
                "content": content,
            }
        )

    if not hasattr(tokenizer, "apply_chat_template") or not tokenizer.chat_template:
        raise AIProviderExecutionError("Configured tokenizer has no chat template")
    return tokenizer.apply_chat_template(
        normalized_messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def _complete_hf_messages(
    messages: list[dict[str, str]],
    model_name: str = HF_MODEL_NAME,
    revision: str = HF_MODEL_REVISION,
    max_new_tokens: int = 80,
    repetition_penalty: float = 1.1,
) -> str:
    """
    Hugging Face 로컬 모델에서 재현 가능한 구조화 출력을 생성한다.
    """
    if not HF_LOCAL_MODEL_ENABLED:
        raise AIProviderUnavailableError("HF local model is disabled")

    try:
        tokenizer, model = load_hf_model(model_name, revision)

        prompt = _messages_to_prompt(tokenizer, messages)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        start = time.perf_counter()

        import torch

        with torch.no_grad():
            generate_kwargs = {
                **inputs,
                "max_new_tokens": max_new_tokens,
                "do_sample": False,
                "repetition_penalty": repetition_penalty,
                "pad_token_id": tokenizer.eos_token_id,
            }

            outputs = model.generate(**generate_kwargs)

        elapsed = time.perf_counter() - start

        input_length = inputs["input_ids"].shape[-1]
        generated_tokens = outputs[0][input_length:]
        decoded = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        logger.info(
            "HF generation completed input_tokens=%d output_tokens=%d generate_seconds=%.2f",
            input_length,
            len(generated_tokens),
            elapsed,
        )

        return decoded

    except (AIProviderUnavailableError, AIProviderExecutionError):
        raise
    except Exception as exc:
        logger.exception("Hugging Face generation failed")
        raise AIProviderExecutionError("Hugging Face generation failed") from exc


def complete_hf_json(messages: list[dict[str, str]]) -> str:
    """Generate deterministic JSON for state-transition analysis."""
    return _complete_hf_messages(
        messages,
        max_new_tokens=180,
        repetition_penalty=1.05,
    )
