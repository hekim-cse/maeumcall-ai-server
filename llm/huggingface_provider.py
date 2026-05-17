# llm/huggingface_provider.py
from __future__ import annotations

import time
from typing import Dict, List, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# 마음콜 1차 메인 후보
DEFAULT_HF_MODEL_NAME = "kakaocorp/kanana-1.5-2.1b-instruct-2505"

_tokenizer = None
_model = None
_loaded_model_name: Optional[str] = None


def _get_device_dtype():
    """
    Mac M 계열에서는 MPS 사용 가능 여부를 확인한다.
    단, device_map='auto'를 사용할 것이므로 dtype만 명확히 지정한다.
    """
    return torch.float16


def load_hf_model(model_name: str = DEFAULT_HF_MODEL_NAME):
    """
    Hugging Face 모델을 최초 1회만 로드한다.
    서버 요청마다 모델을 다시 로드하면 너무 느리므로 전역 캐시를 사용한다.
    """
    global _tokenizer, _model, _loaded_model_name

    if _tokenizer is not None and _model is not None and _loaded_model_name == model_name:
        return _tokenizer, _model

    print(f"Loading Hugging Face model: {model_name}")

    _tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )

    _model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=_get_device_dtype(),
        device_map="auto",
        trust_remote_code=True,
    )

    _model.eval()
    _loaded_model_name = model_name

    print(f"Hugging Face model loaded: {model_name}")

    return _tokenizer, _model


def _messages_to_prompt(tokenizer, messages: List[Dict[str, str]]) -> str:
    """
    모델별 chat_template이 있으면 사용하고,
    없으면 system/user 내용을 단순 문자열로 합친다.
    """
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

    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(
            normalized_messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    prompt_parts = []
    for message in normalized_messages:
        prompt_parts.append(f"{message['role']}: {message['content']}")

    prompt_parts.append("assistant:")
    return "\n".join(prompt_parts)


def complete_hf_messages(
    messages: List[Dict[str, str]],
    model_name: str = DEFAULT_HF_MODEL_NAME,
    max_new_tokens: int = 80,
    do_sample: bool = True,
    temperature: float = 0.4,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
) -> str:
    """
    Hugging Face 로컬 모델로 메시지를 생성한다.
    병원 예약 LangGraph에서는 ai_message 한 문장 생성을 목적으로 사용한다.
    """
    try:
        tokenizer, model = load_hf_model(model_name)

        prompt = _messages_to_prompt(tokenizer, messages)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        start = time.perf_counter()

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=temperature if do_sample else None,
                top_p=top_p if do_sample else None,
                repetition_penalty=repetition_penalty,
                pad_token_id=tokenizer.eos_token_id,
            )

        elapsed = time.perf_counter() - start

        input_length = inputs["input_ids"].shape[-1]
        generated_tokens = outputs[0][input_length:]
        decoded = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        print(f"HF generation latency: {elapsed:.2f}s")

        return decoded

    except Exception as e:
        print(f"❌ Hugging Face generation failed: {e}")
        return ""