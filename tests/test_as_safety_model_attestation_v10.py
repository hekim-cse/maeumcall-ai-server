"""Offline failure gates for future model-file attestation."""

import hashlib
import json
import os

import pytest

from experiments.as_safety_atomic_edges_v10 import model_attestation as guard


def _fixture(tmp_path, monkeypatch):
    path = tmp_path / "kanana.gguf"
    path.write_bytes(b"pinned model bytes")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    observed = {
        "Id": "container-a",
        "Created": "2030-01-01T00:00:00Z",
        "State": {"Running": True},
        "Mounts": [{"Source": str(path), "Destination": "/models/kanana.gguf", "RW": False}],
    }
    state = {"digest": digest, "container": observed}

    def fake_docker(*args):
        if args[0] == "inspect":
            return json.dumps([state["container"]])
        if args[0] == "exec":
            return f"{state['digest']}  /models/kanana.gguf\n"
        raise AssertionError(args)

    monkeypatch.setattr(guard, "_docker", fake_docker)
    return path, digest, state


def test_guard_requires_snapshot_before_container_and_checks_each_request(tmp_path, monkeypatch):
    path, digest, _ = _fixture(tmp_path, monkeypatch)
    attestor = guard.ModelAttestor(path, digest, "model-server")
    with pytest.raises(ValueError, match="not activated"):
        attestor.check()
    attestor.activate()
    attestor.check()
    with pytest.raises(ValueError, match="already activated"):
        attestor.activate()


def test_guard_rejects_host_path_replacement_after_container_start(tmp_path, monkeypatch):
    path, digest, _ = _fixture(tmp_path, monkeypatch)
    attestor = guard.ModelAttestor(path, digest, "model-server")
    attestor.activate()
    replacement = tmp_path / "replacement"
    replacement.write_bytes(path.read_bytes())  # Same bytes, different inode.
    os.replace(replacement, path)
    with pytest.raises(ValueError, match="inode or metadata"):
        attestor.check()


def test_guard_rejects_in_place_model_mutation(tmp_path, monkeypatch):
    path, digest, _ = _fixture(tmp_path, monkeypatch)
    attestor = guard.ModelAttestor(path, digest, "model-server")
    attestor.activate()
    path.write_bytes(b"other model bytes")
    with pytest.raises(ValueError, match="inode or metadata"):
        attestor.check()


@pytest.mark.parametrize("change", ["digest", "identity", "mount", "read_write", "stopped"])
def test_guard_rejects_container_model_or_identity_change(tmp_path, monkeypatch, change):
    path, digest, state = _fixture(tmp_path, monkeypatch)
    attestor = guard.ModelAttestor(path, digest, "model-server")
    attestor.activate()
    if change == "digest":
        state["digest"] = "0" * 64
    elif change == "identity":
        state["container"]["Id"] = "container-b"
    elif change == "mount":
        state["container"]["Mounts"][0]["Source"] = "/other/model.gguf"
    elif change == "read_write":
        state["container"]["Mounts"][0]["RW"] = True
    else:
        state["container"]["State"]["Running"] = False
    with pytest.raises(ValueError):
        attestor.check()


def test_guard_rejects_container_created_before_snapshot(tmp_path, monkeypatch):
    path, digest, state = _fixture(tmp_path, monkeypatch)
    state["container"]["Created"] = "2000-01-01T00:00:00Z"
    attestor = guard.ModelAttestor(path, digest, "model-server")
    with pytest.raises(ValueError, match="predates"):
        attestor.activate()


def test_guard_rejects_missing_container_identity(tmp_path, monkeypatch):
    path, digest, state = _fixture(tmp_path, monkeypatch)
    state["container"]["Id"] = ""
    attestor = guard.ModelAttestor(path, digest, "model-server")
    with pytest.raises(ValueError, match="container ID invalid"):
        attestor.activate()


def test_guard_fails_when_container_digest_command_unavailable(tmp_path, monkeypatch):
    path, digest, _ = _fixture(tmp_path, monkeypatch)
    attestor = guard.ModelAttestor(path, digest, "model-server")

    def unavailable(*args):
        if args[0] == "inspect":
            return json.dumps(
                [
                    {
                        "Id": "container-a",
                        "Created": "2030-01-01T00:00:00Z",
                        "State": {"Running": True},
                        "Mounts": [
                            {"Source": str(path), "Destination": "/models/kanana.gguf", "RW": False}
                        ],
                    }
                ]
            )
        raise OSError("sha256sum unavailable")

    monkeypatch.setattr(guard, "_docker", unavailable)
    with pytest.raises(OSError):
        attestor.activate()


def test_guarded_call_requires_checks_before_and_after_result():
    events = []

    class FakeAttestor:
        def check(self):
            events.append("check")

    result = guard.guarded_call(FakeAttestor(), lambda: events.append("call") or "response")
    events.append("journal")
    assert result == "response"
    assert events == ["check", "call", "check", "journal"]


def test_guarded_call_does_not_return_when_postcheck_fails():
    events = []

    class FakeAttestor:
        def check(self):
            events.append("check")
            if len(events) == 3:
                raise ValueError("identity changed")

    with pytest.raises(ValueError, match="identity changed"):
        guard.guarded_call(FakeAttestor(), lambda: events.append("call") or "response")
    assert events == ["check", "call", "check"]
