"""Fail-closed model-file identity guard for a *future* one-shot experiment.

Construct before starting the model container, activate after it starts, and
check immediately before and after every request, before journaling its result.
This does not retroactively attest earlier experiments or inspect model RAM.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MODEL_DESTINATION = "/models/kanana.gguf"
_T = TypeVar("_T")


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _docker(*args: str) -> str:
    return subprocess.run(
        ("docker", *args), check=True, capture_output=True, text=True, timeout=120
    ).stdout


def _created_ns(value: str) -> int:
    if type(value) is not str:
        raise ValueError("container creation time missing")
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("container creation time invalid") from error
    if created.tzinfo is None:
        raise ValueError("container creation time lacks timezone")
    return int(created.timestamp() * 1e9)


@dataclass(frozen=True)
class FileIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def capture(cls, path: Path) -> FileIdentity:
        info = path.stat()
        if not os.path.isfile(path):
            raise ValueError("model source is not a regular file")
        return cls(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class ModelAttestor:
    """Pin a host inode and verify the container's mounted bytes at each gate."""

    def __init__(self, model_path: Path, expected_sha256: str, container_name: str) -> None:
        if type(expected_sha256) is not str or not _SHA.fullmatch(expected_sha256):
            raise ValueError("expected model digest invalid")
        if type(container_name) is not str or not container_name:
            raise ValueError("container name invalid")
        self.path = model_path.resolve(strict=True)
        self.expected_sha256 = expected_sha256
        self.container_name = container_name
        self.identity = FileIdentity.capture(self.path)
        if (
            _digest(self.path) != expected_sha256
            or FileIdentity.capture(self.path) != self.identity
        ):
            raise ValueError("model bytes changed during initial digest")
        self.captured_at_ns = time.time_ns()
        self.container_id: str | None = None

    def _host(self) -> None:
        if self.path.resolve(strict=True) != self.path:
            raise ValueError("model path changed")
        if FileIdentity.capture(self.path) != self.identity:
            raise ValueError("model inode or metadata changed")

    def _container(self) -> dict:
        observed = json.loads(_docker("inspect", self.container_name))
        if type(observed) is not list or len(observed) != 1 or type(observed[0]) is not dict:
            raise ValueError("container inspect invalid")
        container = observed[0]
        if not container.get("State", {}).get("Running"):
            raise ValueError("model container stopped")
        if _created_ns(container.get("Created")) < self.captured_at_ns:
            raise ValueError("container predates model snapshot")
        if self.container_id is not None and container.get("Id") != self.container_id:
            raise ValueError("model container identity changed")
        if not any(
            m.get("Source") == str(self.path)
            and m.get("Destination") == _MODEL_DESTINATION
            and m.get("RW") is False
            for m in container.get("Mounts", [])
        ):
            raise ValueError("model mount differs")
        return container

    def _mounted_digest(self) -> None:
        output = _docker("exec", self.container_name, "sha256sum", _MODEL_DESTINATION)
        parts = output.strip().split()
        if len(parts) != 2 or parts[0] != self.expected_sha256 or parts[1] != _MODEL_DESTINATION:
            raise ValueError("container model digest differs or is unavailable")

    def activate(self) -> None:
        """Call only after the container was created from this snapshot."""
        if self.container_id is not None:
            raise ValueError("model guard already activated")
        self._host()
        container = self._container()
        self._mounted_digest()
        self._host()
        self.container_id = container["Id"]

    def check(self) -> None:
        """Call before and after each request; append journal only on success."""
        if self.container_id is None:
            raise ValueError("model guard not activated")
        self._host()
        self._container()
        self._mounted_digest()
        self._host()


def guarded_call(attestor: ModelAttestor, call: Callable[[], _T]) -> _T:
    """Return only after both checks pass; callers journal after this returns."""
    attestor.check()
    try:
        return call()
    finally:
        attestor.check()
