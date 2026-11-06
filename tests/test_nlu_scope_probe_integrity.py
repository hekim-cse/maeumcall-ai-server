"""The development probe binds its local Q5 hash to the served Docker mount."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutRequestPolicy
from scripts import probe_nlu_scope_boundary as probe

POLICY = AIHeldoutRequestPolicy.model_validate_json(probe.POLICY.read_bytes())


def test_probe_rejects_a_different_served_model_file(monkeypatch) -> None:
    observed = {
        "State": {"Running": True},
        "Image": POLICY.server_image_digest,
        "HostConfig": {
            "PortBindings": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18081"}]}
        },
        "Mounts": [
            {"Source": "/private/tmp/other.gguf", "Destination": "/models/kanana.gguf", "RW": False}
        ],
    }
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps([observed])),
    )

    with pytest.raises(ValueError, match="serving the checked model file"):
        probe._verify_served_model(
            container_name="local-q5",
            endpoint="http://127.0.0.1:18081/v1/chat/completions",
            model_path=Path("/private/tmp/maeumcall-kanana-q5.gguf"),
            policy=POLICY,
        )
