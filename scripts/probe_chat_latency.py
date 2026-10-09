"""Run an exploratory, fixed-input /chat latency probe on development cases.

This is not the adjudicated structured-NLU benchmark. The output intentionally
omits user messages and response text; case IDs resolve to the committed corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

CORPUS = (
    Path(__file__).resolve().parents[1] / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
)


def select_cases(corpus: dict, case_ids: list[str], all_development: bool) -> list[dict]:
    cases = [
        case
        for case in corpus["cases"]
        if case["split"] == "development" and case["review_status"] == "draft"
    ]
    by_id = {case["id"]: case for case in cases}
    if case_ids:
        unknown = sorted(set(case_ids) - set(by_id))
        if unknown:
            raise ValueError(f"unknown development draft case IDs: {unknown}")
        return [by_id[case_id] for case_id in case_ids]
    if all_development:
        return sorted(cases, key=lambda case: case["id"])

    selected: dict[str, dict] = {}
    for case in sorted(cases, key=lambda item: item["id"]):
        if "human-information-provision" in case["id"]:
            selected.setdefault(case["scenario_key"], case)
    if len(selected) != 16:
        raise ValueError(f"expected 16 detailed scenarios, found {len(selected)}")
    return [selected[key] for key in sorted(selected)]


def probe(endpoint: str, case: dict, timeout: int) -> dict:
    category, title = case["scenario_key"].split(":", 1)
    payload = {
        "category": category,
        "title": title,
        "description": f"{title} 통화 연습",
        "userMessage": case["user_message"],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.load(exc)
    except (TimeoutError, urllib.error.URLError) as exc:
        return {
            "case_id": case["id"],
            "scenario_key": case["scenario_key"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error_type": type(exc).__name__,
        }

    result = {
        "case_id": case["id"],
        "scenario_key": case["scenario_key"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "http_status": status,
    }
    if status == 200:
        result["conversation_state"] = body.get("conversationState")
        result["external_effect"] = body.get("simulation", {}).get("externalEffect")
    else:
        result["error_code"] = body.get("error", {}).get("code")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8001/chat")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--service-artifact", required=True)
    parser.add_argument("--service-provider-sha256", required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--all-development", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout < 1:
        parser.error("repeats and timeout must be positive")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    corpus_bytes = CORPUS.read_bytes()
    cases = select_cases(json.loads(corpus_bytes), args.case_id, args.all_development)
    observations = [
        probe(args.endpoint, case, args.timeout) for case in cases for _ in range(args.repeats)
    ]
    successful = [
        item["elapsed_seconds"] for item in observations if item.get("http_status") == 200
    ]
    report = {
        "kind": "exploratory_chat_latency_v1",
        "not_official_quality_score": True,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "probe_checkout_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CORPUS.parents[4], text=True
        ).strip(),
        "probe_runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "service_artifact": args.service_artifact,
        "service_provider_sha256": args.service_provider_sha256,
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "endpoint": args.endpoint,
        "case_count": len(cases),
        "repeats": args.repeats,
        "http_200_count": len(successful),
        "median_seconds_http_200": statistics.median(successful) if successful else None,
        "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"exploratory cases={len(cases)} requests={len(observations)} "
        f"http_200={len(successful)} output={args.output}"
    )


if __name__ == "__main__":
    main()
