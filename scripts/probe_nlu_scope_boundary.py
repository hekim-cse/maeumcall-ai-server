"""Development-only same-model scope prompt probe on already-exposed AH cases.

This is not a heldout evaluation. It never changes the frozen Q4/Q5 artifacts.
Only normalized predictions and request timing are saved, never model text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.parse
from pathlib import Path

from evals.structured_nlu.ai_heldout import (
    AIHeldoutDataset,
    AIHeldoutPredictionArtifact,
    AIHeldoutRequestPolicy,
)
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction
from scripts.run_ai_heldout_pair import _loopback_endpoint, _run_case, prompt_revision_sha256

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json"
POLICY = ROOT / "evals/structured_nlu/data/ai_heldout/q4-q5-request-policy.v1.json"
BASELINE = ROOT / "evals/structured_nlu/results/ai-heldout-q5-v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _score_slice(cases, predictions, *, boundary: bool) -> dict:
    selected = tuple(case for case in cases if ("hard_negative" in case.tags) == boundary)
    selected_ids = {case.id for case in selected}
    selected_predictions = tuple(p for p in predictions if p.case_id in selected_ids)
    return score_predictions(selected, selected_predictions).to_dict()


def _verify_served_model(
    *, container_name: str, endpoint: str, model_path: Path, policy: AIHeldoutRequestPolicy
) -> None:
    """Bind the local file hash to the actual loopback Docker server mount."""
    observed = json.loads(
        subprocess.run(
            ("docker", "inspect", container_name),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )[0]
    port = str(urllib.parse.urlsplit(endpoint).port)
    if not observed["State"]["Running"] or observed["Image"] != policy.server_image_digest:
        raise ValueError("development server image or running state differs from policy")
    if observed["HostConfig"]["PortBindings"].get("8080/tcp") != [
        {"HostIp": "127.0.0.1", "HostPort": port}
    ]:
        raise ValueError("development server is not bound to the selected loopback port")
    if not any(
        mount["Source"] == str(model_path.resolve())
        and mount["Destination"] == "/models/kanana.gguf"
        and not mount["RW"]
        for mount in observed["Mounts"]
    ):
        raise ValueError("development server is not serving the checked model file")


def run(*, endpoint: str, model_path: Path, container_name: str, output: Path) -> dict:
    """Keep each completed case if a development run is interrupted."""
    endpoint = _loopback_endpoint(endpoint)
    if output.exists():
        raise ValueError(f"development result already exists: {output}")
    partial = output.with_name(output.name + ".partial.jsonl")
    if partial.exists():
        raise ValueError(f"partial development result already exists: {partial}")
    dataset_bytes = DATASET.read_bytes()
    dataset = AIHeldoutDataset.model_validate_json(dataset_bytes)
    policy = AIHeldoutRequestPolicy.model_validate_json(POLICY.read_bytes())
    baseline = AIHeldoutPredictionArtifact.model_validate_json(BASELINE.read_bytes())
    cases = dataset.cases
    if {case.id for case in cases} != {p.case_id for p in baseline.predictions}:
        raise ValueError("baseline and development case IDs differ")
    model_sha = _sha256(model_path)
    if model_sha != baseline.model_sha256:
        raise ValueError("development model differs from the saved Q5 baseline")
    _verify_served_model(
        container_name=container_name, endpoint=endpoint, model_path=model_path, policy=policy
    )
    revision = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions: list[CasePrediction] = []
    with partial.open("x", encoding="utf-8") as file:
        for case in cases:
            prediction = _run_case(
                case,
                endpoint=endpoint,
                model_id="/models/kanana.gguf",
                policy=policy,
            )
            predictions.append(prediction)
            file.write(prediction.model_dump_json() + "\n")
            file.flush()
            os.fsync(file.fileno())
    report = {
        "kind": "ai_authored_development_scope_probe_v1",
        "claim_scope": "diagnostic_only_already_exposed_cases",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "baseline_prediction_sha256": _sha256(BASELINE),
        "candidate_revision": revision,
        "candidate_prompt_sha256": prompt_revision_sha256(),
        "model_sha256": model_sha,
        "request_policy_sha256": _sha256(POLICY),
        "baseline_scores": score_predictions(cases, baseline.predictions).to_dict(),
        "candidate_scores": score_predictions(cases, tuple(predictions)).to_dict(),
        "boundary_baseline_scores": _score_slice(cases, baseline.predictions, boundary=True),
        "boundary_candidate_scores": _score_slice(cases, tuple(predictions), boundary=True),
        "in_scope_baseline_scores": _score_slice(cases, baseline.predictions, boundary=False),
        "in_scope_candidate_scores": _score_slice(cases, tuple(predictions), boundary=False),
        "candidate_predictions": [prediction.model_dump(mode="json") for prediction in predictions],
    }
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    partial.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(
        endpoint=args.endpoint,
        model_path=args.model_path,
        container_name=args.container_name,
        output=args.output,
    )
    print(
        "development exact matches:",
        report["baseline_scores"]["counts"]["fully_correct_cases"],
        report["candidate_scores"]["counts"]["fully_correct_cases"],
        "of",
        report["candidate_scores"]["counts"]["cases"],
    )


if __name__ == "__main__":
    main()
