"""Probe reviewed development cases without storing prompts or completions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.action_field_dev_cases import load_cases as load_development_cases
from scripts.fresh_scope_ai_cases import load_cases as load_fresh_cases
from scripts.probe_gguf_structured_nlu import run_case

CASE_IDS = ("F15", "F17", "F23", "F29", "D05")


def _docker_inspect(*args: str) -> dict:
    """Read a single Docker object without writing its full configuration to the report."""
    objects = json.loads(subprocess.check_output(["docker", *args], text=True))
    if len(objects) != 1:
        raise ValueError("exactly one Docker object is required")
    return objects[0]


def _option(command: list[str], name: str) -> str:
    """Read one option from the observed model-server command."""
    if command.count(name) != 1:
        raise ValueError(f"server command must contain one {name}")
    index = command.index(name)
    if index + 1 >= len(command):
        raise ValueError(f"server command is missing the value for {name}")
    return command[index + 1]


def inspect_runtime(container_name: str) -> dict:
    """Verify the running container, mounted model, image and local endpoint."""
    container = _docker_inspect("inspect", container_name)
    if not container["State"]["Running"]:
        raise ValueError("model server container is not running")
    image = _docker_inspect("image", "inspect", container["Config"]["Image"])
    if image["Id"] != container["Image"]:
        raise ValueError("container image ID differs from inspected image")
    image_name = container["Config"]["Image"].rsplit(":", 1)[0]
    matching_digests = [
        digest for digest in image.get("RepoDigests", []) if digest.startswith(image_name + "@")
    ]
    if len(matching_digests) != 1:
        raise ValueError("server image must have one matching repository digest")
    command = container["Config"]["Cmd"]
    model_target = _option(command, "-m")
    mounts = [mount for mount in container["Mounts"] if mount["Destination"] == model_target]
    if len(mounts) != 1 or mounts[0]["RW"] is not False:
        raise ValueError("model must be a single read-only Docker mount")
    model_file = Path(mounts[0]["Source"])
    with model_file.open("rb") as model_stream:
        model_sha256 = hashlib.file_digest(model_stream, "sha256").hexdigest()
    ports = container["HostConfig"]["PortBindings"].get("8080/tcp", [])
    if len(ports) != 1 or ports[0]["HostIp"] != "127.0.0.1":
        raise ValueError("model server must bind one localhost port")
    host_port = int(ports[0]["HostPort"])
    return {
        "endpoint": f"http://127.0.0.1:{host_port}/v1/chat/completions",
        "model_sha256": model_sha256,
        "model_sha256_provenance": "sha256_of_inspected_read_only_mount_source",
        "server_image_digest": matching_digests[0].split("@", 1)[1],
        "server_image_id": image["Id"],
        "runtime": f"local-docker-{image['Architecture']}-cpu",
        "container_cpu_limit": container["HostConfig"]["NanoCpus"] / 1_000_000_000,
        "container_memory_bytes": container["HostConfig"]["Memory"],
        "server_threads": int(_option(command, "-t")),
        "server_parallel": int(_option(command, "-np")),
        "context_size": int(_option(command, "-c")),
    }


def main() -> None:
    """Run one ordered repetition and save only bounded diagnostic output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--constrain-workflow", action="store_true")
    parser.add_argument("--repetition", type=int, choices=(1, 2), required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    runtime = inspect_runtime(args.container_name)
    cases = {case["id"]: case for case in [*load_fresh_cases(), *load_development_cases()]}
    selected = tuple(
        case_id for case_id in CASE_IDS if not args.constrain_workflow or case_id != "F29"
    )
    order = selected if args.repetition == 1 else tuple(reversed(selected))
    observations = []
    for case_id in order:
        result = run_case(
            cases[case_id],
            endpoint=runtime["endpoint"],
            model="kanana-1.5-2.1b-instruct-q5",
            timeout=180,
            capture_shape=True,
            constrain_workflow=args.constrain_workflow,
            schema_format="json_object",
        )
        observations.append(result)
        print(
            f"{args.mode} r{args.repetition} {case_id} contract={result['contract_valid']}",
            flush=True,
        )
    files = (
        "services/flow/service_workflow/structured.py",
        "services/flow/reservation/study_room/llm_structured.py",
        "services/flow/delivery/contracts.py",
    )
    source_sha256 = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files}
    report = {
        "kind": "exploratory_nlu_boundary_pair_v1",
        "not_official_quality_score": True,
        "mode": args.mode,
        "constrain_workflow": args.constrain_workflow,
        "schema_format": "json_object" if args.constrain_workflow else None,
        "repetition": args.repetition,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_ids": list(order),
        "source_sha256": source_sha256,
        "model_sha256": runtime["model_sha256"],
        "model_sha256_provenance": runtime["model_sha256_provenance"],
        "server_image_digest": runtime["server_image_digest"],
        "server_image_id": runtime["server_image_id"],
        "runtime": runtime["runtime"],
        "container_cpu_limit": runtime["container_cpu_limit"],
        "container_memory_bytes": runtime["container_memory_bytes"],
        "server_threads": runtime["server_threads"],
        "server_parallel": runtime["server_parallel"],
        "context_size": runtime["context_size"],
        "observations": observations,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
