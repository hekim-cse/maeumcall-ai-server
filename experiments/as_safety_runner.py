"""Common lifecycle for new local A/S development experiments."""

import argparse
import json
import re
import stat
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from experiments.as_safety_atomic_edges_v1 import run as execution
from experiments.as_safety_atomic_edges_v4 import run as wire
from experiments.as_safety_atomic_edges_v5 import run as journal_io
from experiments.as_safety_atomic_edges_v7 import run as tokenizer
from experiments.as_safety_atomic_edges_v10.model_attestation import ModelAttestor, guarded_call
from experiments.as_safety_atomic_edges_v12 import run as repo
from experiments.as_safety_v2.json_contract import ValidationError
from experiments.as_safety_v2.transport import RequestPolicy, TransportError
from experiments.as_safety_v4.run import verify_container

RUNNER_SOURCE = "experiments/as_safety_runner.py"
RUNNER_DEPENDENCIES = (
    "experiments/as_safety_atomic_edges_v1/run.py",
    "experiments/as_safety_atomic_edges_v4/run.py",
    "experiments/as_safety_atomic_edges_v5/run.py",
    "experiments/as_safety_atomic_edges_v7/run.py",
    "experiments/as_safety_atomic_edges_v10/model_attestation.py",
    "experiments/as_safety_atomic_edges_v12/run.py",
    "experiments/as_safety_v2/json_contract.py",
    "experiments/as_safety_v2/transport.py",
    "experiments/as_safety_v4/run.py",
)
DATA = repo.ROOT / "evals/structured_nlu/data/ai_heldout"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")


@dataclass(frozen=True)
class Call:
    name: str
    messages: list[dict[str, str]]
    schema: dict
    decode: Callable[[str], int | None]


@dataclass(frozen=True)
class Model:
    sha256: str
    container: str
    server: Callable[[Path], AbstractContextManager[ModelAttestor]]


class Experiment:
    def __init__(
        self,
        name: str,
        model: Model,
        policy: RequestPolicy,
        calls: tuple[Call, ...],
        sources: tuple[str, ...],
        reference: dict[str, str],
    ):
        names = [call.name for call in calls]
        if (
            not calls
            or len(set(names)) != len(names)
            or not all(SAFE_NAME.fullmatch(x) for x in [name, *names])
        ):
            raise ValueError("invalid experiment or call names")
        self.name, self.model, self.policy = name, model, policy
        self.calls = {call.name: call for call in calls}
        self.sources = sorted({RUNNER_SOURCE, *RUNNER_DEPENDENCIES, *sources})
        self.reference = dict(reference)
        self.protocol = DATA / f"{name}-protocol.json"
        self.journal = DATA / f"{name}-journal.v1.jsonl"
        self.private = Path("/private/tmp") / f"{name}-raw"

    def request_body(self, call: Call) -> bytes:
        return wire.request_bytes(call.messages, call.schema, self.policy, "variant")

    def manifest(self, commit: str) -> dict:
        sources = {path: repo._sha(repo._git("show", f"{commit}:{path}")) for path in self.sources}
        if any(
            repo._sha((repo.ROOT / path).read_bytes()) != digest for path, digest in sources.items()
        ):
            raise ValueError("frozen sources differ")
        return {
            "experiment": self.name,
            "commit": commit,
            "source_sha256": sources,
            "reference": self.reference,
            "model_sha256": self.model.sha256,
            "container": self.model.container,
            "image_digest": execution.IMAGE,
            "server_args": list(execution.SERVER_ARGS),
            "order": list(self.calls),
            "request_sha256": {
                name: repo._sha(self.request_body(call)) for name, call in self.calls.items()
            },
        }

    def protocol_digest(self) -> str:
        raw = self.protocol.read_bytes()
        frozen = json.loads(raw, object_pairs_hook=wire._unique_pairs)
        if frozen != self.manifest(frozen["commit"]):
            raise ValueError("frozen protocol differs")
        if raw != repo._git("show", f"HEAD:{self.protocol.relative_to(repo.ROOT)}"):
            raise ValueError("protocol must be committed before calls")
        return repo._sha(raw)

    def require_unused(self):
        if self.journal.exists() or self.private.exists():
            raise FileExistsError("existing or partial run requires manual audit")
        repo._clean()

    def prepare(self, model_path: Path):
        self.require_unused()
        if execution.digest_file(model_path) != self.model.sha256:
            raise ValueError("model digest differs")
        frozen = self.manifest(repo._git("rev-parse", "HEAD").decode().strip())
        with self.protocol.open("x", encoding="utf-8") as stream:
            json.dump(frozen, stream, indent=2)
            stream.write("\n")

    @staticmethod
    def outcome(call: Call, finish: str, content: str) -> tuple[int | None, str | None]:
        if finish != "stop":
            return None, "finish_length"
        try:
            return call.decode(content), None
        except ValidationError as exc:
            return None, exc.code

    def capture(self, call: Call, attestor):
        row = {
            "call": call.name,
            "request_sha256": repo._sha(self.request_body(call)),
            "selected": None,
        }
        try:
            response = guarded_call(
                attestor,
                lambda: wire.post_format_completion(
                    call.messages,
                    call.schema,
                    condition="variant",
                    policy=self.policy,
                    endpoint=execution.ENDPOINT,
                    model_id=execution.MODEL_ID,
                ),
            )
        except TransportError as exc:
            return {**row, "error": exc.code, "http_status": exc.status_code}
        raw_sha, raw_bytes = execution._write_private_raw(
            self.private / f"{call.name}.json.txt", response.content
        )
        selected, error = self.outcome(call, response.finish_reason, response.content)
        return {
            **row,
            "selected": selected,
            "error": error,
            "finish_reason": response.finish_reason,
            "raw_sha256": raw_sha,
            "raw_bytes": raw_bytes,
        }

    def run(self, model_path: Path):
        self.require_unused()
        protocol_sha = self.protocol_digest()
        with self.model.server(model_path) as attestor:
            if (
                attestor.expected_sha256 != self.model.sha256
                or attestor.container_name != self.model.container
                or attestor.path != model_path.resolve()
            ):
                raise ValueError("running model differs from the experiment")
            verify_container(self.model.container, attestor.path)
            counts = {}
            for name, call in self.calls.items():
                body = self.request_body(call)
                counts[name] = guarded_call(
                    attestor, lambda body=body: tokenizer._tokenize_request(body)
                )
            if not self.valid_token_counts(counts):
                raise ValueError("invalid context budget")
            if self.private.resolve().is_relative_to(repo.ROOT):
                raise ValueError("raw output must be outside the repository")
            self.private.mkdir(mode=0o700)
            with self.journal.open("x", encoding="utf-8") as stream:
                journal_io._append(
                    stream, {"protocol_sha256": protocol_sha, "input_tokens": counts}
                )
                for call in self.calls.values():
                    row = self.capture(call, attestor)
                    journal_io._append(stream, row)
                    if row["error"] is not None:
                        break

    def valid_token_counts(self, counts: dict) -> bool:
        limit = execution.RUNTIME["context_tokens"]
        return set(counts) == set(self.calls) and all(
            type(count) is int and 0 < count < limit - self.policy.max_tokens
            for count in counts.values()
        )

    def replay(self) -> list[dict]:
        protocol_sha = self.protocol_digest()
        with self.journal.open(encoding="utf-8") as stream:
            header, *rows = [
                json.loads(line, object_pairs_hook=wire._unique_pairs) for line in stream
            ]
        if header["protocol_sha256"] != protocol_sha or not self.valid_token_counts(
            header["input_tokens"]
        ):
            raise ValueError("journal header differs")
        if [row["call"] for row in rows] != list(self.calls)[: len(rows)]:
            raise ValueError("journal order differs")
        if (
            not rows
            or any(row["error"] is not None for row in rows[:-1])
            or (len(rows) < len(self.calls) and rows[-1]["error"] is None)
        ):
            raise ValueError("inconsistent journal termination")
        if self.private.is_symlink() or stat.S_IMODE(self.private.stat().st_mode) != 0o700:
            raise ValueError("private directory differs")
        for row in rows:
            self.verify_row(row)
        return rows

    def verify_row(self, row: dict):
        call = self.calls[row["call"]]
        if row["request_sha256"] != repo._sha(self.request_body(call)):
            raise ValueError(f"request differs: {call.name}")
        if "raw_sha256" not in row:
            if not row["error"] or "http_status" not in row or row["selected"] is not None:
                raise ValueError(f"missing completion or transport error: {call.name}")
            return
        path = self.private / f"{call.name}.json.txt"
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError(f"raw response permissions differ: {call.name}")
        raw = path.read_bytes()
        if (repo._sha(raw), len(raw)) != (row["raw_sha256"], row["raw_bytes"]):
            raise ValueError(f"raw response differs: {call.name}")
        if self.outcome(call, row["finish_reason"], raw.decode()) != (
            row["selected"],
            row["error"],
        ):
            raise ValueError(f"outcome differs: {call.name}")

    def cli(self):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("command", choices=("prepare", "run", "replay"))
        parser.add_argument("--model-path", type=Path)
        args = parser.parse_args()
        if args.command == "replay":
            print(json.dumps(self.replay(), indent=2))
        elif args.model_path is None:
            parser.error("--model-path is required")
        elif args.command == "prepare":
            self.prepare(args.model_path)
        else:
            self.run(args.model_path)
