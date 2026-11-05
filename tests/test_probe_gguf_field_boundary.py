"""Verify that exploratory probe provenance comes from the inspected runtime."""

import hashlib

import pytest

from scripts import probe_gguf_field_boundary as probe

pytestmark = pytest.mark.unit


def test_runtime_provenance_uses_mounted_file_and_container_settings(monkeypatch, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model bytes")
    container = {
        "State": {"Running": True},
        "Config": {
            "Image": "example.test/llama:server",
            "Cmd": ["-m", "/models/model.gguf", "-c", "4096", "-t", "4", "-np", "1"],
        },
        "Image": "sha256:image-id",
        "Mounts": [{"Destination": "/models/model.gguf", "Source": str(model), "RW": False}],
        "HostConfig": {
            "PortBindings": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]},
            "NanoCpus": 4_000_000_000,
            "Memory": 6 * 1024**3,
        },
    }
    image = {
        "Id": "sha256:image-id",
        "RepoDigests": ["example.test/llama@sha256:manifest-id"],
        "Architecture": "arm64",
    }
    monkeypatch.setattr(
        probe,
        "_docker_inspect",
        lambda *args: container if args[0] == "inspect" else image,
    )

    observed = probe.inspect_runtime("test-container")

    assert observed["model_sha256"] == hashlib.sha256(b"model bytes").hexdigest()
    assert observed["server_image_digest"] == "sha256:manifest-id"
    assert observed["endpoint"] == "http://127.0.0.1:18080/v1/chat/completions"
    assert observed["container_cpu_limit"] == 4
    assert observed["container_memory_bytes"] == 6 * 1024**3
    assert observed["server_threads"] == 4

    container["Mounts"][0]["RW"] = True
    with pytest.raises(ValueError, match="read-only"):
        probe.inspect_runtime("test-container")
