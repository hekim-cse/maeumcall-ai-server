import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import llm.huggingface_provider as provider
import main

pytestmark = pytest.mark.unit


def test_local_model_readiness_requires_loaded_configured_revision(monkeypatch):
    monkeypatch.setattr(provider, "HF_LOCAL_MODEL_ENABLED", True)
    monkeypatch.setattr(provider, "_tokenizer", object())
    monkeypatch.setattr(provider, "_model", object())
    monkeypatch.setattr(provider, "_loaded_model_name", provider.HF_MODEL_NAME)
    monkeypatch.setattr(provider, "_loaded_model_revision", "different-revision")
    assert provider.local_model_ready() is False

    monkeypatch.setattr(provider, "_loaded_model_revision", provider.HF_MODEL_REVISION)
    assert provider.local_model_ready() is True


def test_missing_chat_template_is_rejected():
    tokenizer = SimpleNamespace(chat_template=None)
    with pytest.raises(provider.AIProviderExecutionError, match="no chat template"):
        provider._messages_to_prompt(tokenizer, [{"role": "user", "content": "안녕하세요"}])


def test_explicit_model_dtype_is_used(monkeypatch):
    dtype = object()
    monkeypatch.setattr(provider, "HF_MODEL_DTYPE", "bfloat16")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(bfloat16=dtype))

    assert provider._get_device_dtype() is dtype


def test_enabled_local_model_is_loaded_during_startup(monkeypatch):
    loaded = []
    monkeypatch.setattr(main, "HF_LOCAL_MODEL_ENABLED", True)
    monkeypatch.setattr(main, "load_hf_model", lambda: loaded.append(True))

    with TestClient(main.app):
        assert loaded == [True]


def test_readiness_does_not_trust_enable_flag_alone(monkeypatch):
    monkeypatch.setattr(main, "HF_LOCAL_MODEL_ENABLED", True)
    monkeypatch.setattr(main, "local_model_ready", lambda: False)

    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["components"]["local_nlu"] == {"ready": False}
