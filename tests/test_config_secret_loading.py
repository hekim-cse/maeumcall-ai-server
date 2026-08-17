from __future__ import annotations

import pytest

from core.config import getenv_secret

pytestmark = pytest.mark.unit


def test_secret_can_be_loaded_from_absolute_file(tmp_path, monkeypatch):
    secret_file = tmp_path / "auth-secret"
    secret_file.write_text("file-secret-value\n", encoding="utf-8")
    monkeypatch.delenv("TEST_SECRET", raising=False)
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))

    assert getenv_secret("TEST_SECRET") == "file-secret-value"


def test_direct_and_file_secret_are_mutually_exclusive(tmp_path, monkeypatch):
    secret_file = tmp_path / "auth-secret"
    secret_file.write_text("file-secret-value", encoding="utf-8")
    monkeypatch.setenv("TEST_SECRET", "direct-secret-value")
    monkeypatch.setenv("TEST_SECRET_FILE", str(secret_file))

    with pytest.raises(ValueError, match="only one"):
        getenv_secret("TEST_SECRET")


def test_secret_file_path_must_be_absolute(monkeypatch):
    monkeypatch.delenv("TEST_SECRET", raising=False)
    monkeypatch.setenv("TEST_SECRET_FILE", "relative/secret")

    with pytest.raises(ValueError, match="absolute path"):
        getenv_secret("TEST_SECRET")
