"""Pair baseline and scope-instruction runs on AI-authored development cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts.broad_ai_exploration_cases import FIELD_DRAFT, SENTENCES, load_cases
from scripts.probe_gguf_broad_ai_dev import file_sha256, summarize
from scripts.probe_gguf_structured_nlu import run_case

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTION = (
    "현재 시나리오의 업무 목적과 직접 관련 없는 질문이나 요청은, 문장에 다른 업무의 "
    "구체적인 정보가 있더라도 현재 업무의 정보 제공으로 분류하지 마세요. "
    "그 경우 현재 상태에서 허용된 user_action 중 unknown을 선택하고, "
    "현재 업무의 필드에는 모두 null을 반환하세요. "
    "현재 업무에 실제로 필요한 정보를 제공한 발화에는 기존 행동 기준을 그대로 적용하세요."
)
REQUEST_SETTINGS = {
    "max_tokens": 180,
    "temperature": 0,
    "repeat_penalty": 1.05,
    "stop": ["<|eot_id|>"],
}
SOURCE_PATHS = (
    "scripts/probe_gguf_scope_instruction.py",
    "scripts/probe_gguf_structured_nlu.py",
    "scripts/broad_ai_exploration_cases.py",
    "scripts/probe_gguf_broad_ai_dev.py",
)


def inject_scope_instruction(request: urllib.request.Request) -> urllib.request.Request:
    payload = json.loads(request.data)
    messages = payload["messages"]
    if not messages or messages[0].get("role") != "system":
        raise ValueError("scope instruction requires a system message")
    payload["messages"] = [
        {**messages[0], "content": messages[0]["content"] + "\n" + INSTRUCTION},
        *messages[1:],
    ]
    return urllib.request.Request(
        request.full_url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def paired_summary(observations: list[dict], case_ids: list[str], repetitions: int) -> dict:
    expected = {
        (case_id, repetition, mode)
        for case_id in case_ids
        for repetition in range(1, repetitions + 1)
        for mode in ("baseline", "scope_instruction")
    }
    indexed = {(item["case_id"], item["repetition"], item["mode"]): item for item in observations}
    if len(indexed) != len(observations) or set(indexed) != expected:
        raise ValueError("observations must cover every case, repetition and mode once")

    by_mode = {}
    by_polarity = {}
    for mode in ("baseline", "scope_instruction"):
        mode_items = [item for item in observations if item["mode"] == mode]
        by_mode[mode] = summarize(mode_items)
        by_polarity[mode] = {
            polarity: summarize(
                [item for item in mode_items if int(item["case_id"][1:]) % 2 == parity]
            )
            for polarity, parity in (("in_scope", 1), ("near_scope_out", 0))
        }

    discordance = {"baseline_only": [], "scope_instruction_only": []}
    for case_id in case_ids:
        for repetition in range(1, repetitions + 1):
            baseline = indexed[case_id, repetition, "baseline"]
            intervention = indexed[case_id, repetition, "scope_instruction"]
            baseline_match = baseline["contract_valid"] and baseline["action_draft_match"] is True
            intervention_match = (
                intervention["contract_valid"] and intervention["action_draft_match"] is True
            )
            if baseline_match != intervention_match:
                winner = "baseline_only" if baseline_match else "scope_instruction_only"
                discordance[winner].append(f"{case_id}.r{repetition}")
    return {
        "by_mode": by_mode,
        "by_polarity": by_polarity,
        "paired_contract_and_action_discordance": discordance,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080/v1/chat/completions")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-file", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-image-digest", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--container-cpu-limit", required=True, type=int)
    parser.add_argument("--container-memory-gib", required=True, type=int)
    parser.add_argument("--server-threads", required=True, type=int)
    parser.add_argument("--server-parallel", required=True, type=int)
    parser.add_argument("--context-size", required=True, type=int)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (
        min(
            args.container_cpu_limit,
            args.container_memory_gib,
            args.server_threads,
            args.server_parallel,
            args.context_size,
            args.repetitions,
            args.timeout,
        )
        < 1
    ):
        parser.error("numeric settings must be positive")
    if args.output.exists():
        parser.error("output already exists")
    if file_sha256(args.model_file) != args.model_sha256:
        parser.error("model file SHA-256 differs from declared SHA-256")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=False).returncode:
        parser.error("probe requires committed tracked files")
    tracked = [*SOURCE_PATHS, str(SENTENCES.relative_to(ROOT)), str(FIELD_DRAFT.relative_to(ROOT))]
    if subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *tracked],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode:
        parser.error("probe requires committed source files")

    cases = load_cases()
    case_ids = [case["id"] for case in cases]
    code_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    code_sha = hashlib.sha256()
    for name in SOURCE_PATHS:
        code_sha.update(name.encode() + b"\0" + (ROOT / name).read_bytes())
    original_urlopen = urllib.request.urlopen
    active_mode = "baseline"

    def paired_urlopen(request, *, timeout):
        if active_mode == "scope_instruction":
            request = inject_scope_instruction(request)
        return original_urlopen(request, timeout=timeout)

    observations = []
    try:
        with patch("urllib.request.urlopen", paired_urlopen):
            for repetition in range(1, args.repetitions + 1):
                ordered_cases = cases if repetition % 2 else list(reversed(cases))
                modes = (
                    ("baseline", "scope_instruction")
                    if repetition % 2
                    else ("scope_instruction", "baseline")
                )
                for case in ordered_cases:
                    for mode in modes:
                        active_mode = mode
                        result = run_case(
                            case,
                            endpoint=args.endpoint,
                            model=args.model,
                            timeout=args.timeout,
                            capture_shape=True,
                        )
                        observations.append({"repetition": repetition, "mode": mode, **result})
                        print(
                            f"{len(observations)}/{len(cases) * args.repetitions * 2} "
                            f"case={case['id']} mode={mode} valid={result['contract_valid']}",
                            flush=True,
                        )
    finally:
        report = {
            "kind": "exploratory_scope_instruction_pair_v1",
            "not_official_quality_score": True,
            "candidate_status": "ai_assisted_unreviewed",
            "sentence_action_review": "user_accepted_for_exploration_2026-11-04",
            "normalized_value_status": "ai_draft_unreviewed",
            "complete": len(observations) == len(cases) * args.repetitions * 2,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "sentence_source_sha256": file_sha256(SENTENCES),
            "field_draft_sha256": file_sha256(FIELD_DRAFT),
            "implementation_sha256": code_sha.hexdigest(),
            "code_git_commit": code_commit,
            "model": args.model,
            "model_sha256": args.model_sha256,
            "server_image_digest": args.server_image_digest,
            "runtime": args.runtime,
            "container_cpu_limit": args.container_cpu_limit,
            "container_memory_gib": args.container_memory_gib,
            "server_threads": args.server_threads,
            "server_parallel": args.server_parallel,
            "context_size": args.context_size,
            "request_settings": REQUEST_SETTINGS,
            "instruction": INSTRUCTION,
            "case_ids": case_ids,
            "repetitions": args.repetitions,
            "observations": observations,
        }
        if report["complete"]:
            report["summary"] = paired_summary(observations, case_ids, args.repetitions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
