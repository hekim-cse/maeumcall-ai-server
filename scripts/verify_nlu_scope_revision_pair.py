"""Independently verify a completed NLU code-revision pair before reporting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from evals.structured_nlu.metrics import score_predictions
from evals.structured_nlu.schema import CasePrediction

LEGACY_RESULT_CLAIM_SCOPE = "single_owner_reviewed_ai_authored_32_case_evaluation"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact_mcnemar(gains: int, losses: int) -> float:
    discordant = gains + losses
    if discordant == 0:
        return 1.0
    small = min(gains, losses)
    return min(
        1.0,
        2 * sum(math.comb(discordant, index) for index in range(small + 1)) / 2**discordant,
    )


def verify(dataset: Path, ledger: Path, protocol: Path, result: Path) -> dict:
    frozen = json.loads(protocol.read_text(encoding="utf-8"))
    revision = frozen.get("protocol_revision")
    if revision == 3:
        if "scenario_keys" in frozen or "result_claim_scope" in frozen:
            raise ValueError("revision 3 cannot declare a targeted scenario or result scope")
        expected_scenarios = None
        expected_claim_scope = LEGACY_RESULT_CLAIM_SCOPE
    elif revision == 4:
        keys = frozen.get("scenario_keys")
        claim = frozen.get("result_claim_scope")
        if not isinstance(keys, list) or not keys or len(keys) != len(set(keys)):
            raise ValueError("revision 4 requires distinct scenario_keys")
        if not isinstance(claim, str) or not claim.strip() or claim == LEGACY_RESULT_CLAIM_SCOPE:
            raise ValueError("revision 4 requires an explicit targeted result_claim_scope")
        expected_scenarios = frozenset(keys)
        expected_claim_scope = claim
    else:
        raise ValueError("unsupported batch-restart protocol revision")
    reviewed = load_reviewed_ai_heldout(
        dataset,
        ledger,
        expected_scenario_keys=expected_scenarios,
    )
    observed = json.loads(result.read_text(encoding="utf-8"))
    if observed["kind"] != "ai_authored_code_revision_pair_result_v1":
        raise ValueError("unexpected result kind")
    if observed.get("claim_scope") != expected_claim_scope:
        raise ValueError("result claim scope differs from frozen protocol")
    for key, expected in (
        ("protocol_sha256", _sha256(protocol)),
        ("dataset_sha256", reviewed.dataset_sha256),
        ("model_sha256", frozen["model_sha256"]),
        ("baseline_revision", frozen["baseline_revision"]),
        ("candidate_revision", frozen["candidate_revision"]),
    ):
        if observed[key] != expected:
            raise ValueError(f"{key} differs from the committed protocol or dataset")
    if _sha256(ledger) != frozen["review_ledger_sha256"]:
        raise ValueError("review ledger differs from protocol")
    if len(reviewed.dataset.cases) != frozen["case_count"]:
        raise ValueError("case count differs from protocol")
    expected_restarts = list(
        range(frozen["restart_every_cases"], frozen["case_count"], frozen["restart_every_cases"])
    )
    if observed["restarts_after_case"] != expected_restarts:
        raise ValueError("scheduled server restarts were not all recorded")
    cases = reviewed.dataset.cases
    case_ids = [case.id for case in cases]
    predictions = {}
    allowed_validation_errors = {
        "ValueError",
        "StructuredKeyError",
        "JSONDecodeError",
        "InvalidJSONShape",
    }
    for role in ("baseline", "candidate"):
        raw = observed["predictions"][role]
        if [item["case_id"] for item in raw] != case_ids:
            raise ValueError(f"{role} cases differ from reviewed order")
        parsed = tuple(CasePrediction.model_validate(item) for item in raw)
        if any(
            attempt.error_type not in allowed_validation_errors
            for prediction in parsed
            for attempt in prediction.attempts
            if attempt.error_type is not None
        ):
            raise ValueError(f"{role} includes a transport or unexpected error")
        if any(len(prediction.attempts) > 2 for prediction in parsed):
            raise ValueError("request exceeded the one-retry policy")
        if any(
            len(prediction.attempts) == 1 and not prediction.attempts[0].contract_valid
            for prediction in parsed
        ):
            raise ValueError("a failed first contract attempt was not retried")
        predictions[role] = parsed
        if score_predictions(cases, parsed).to_dict() != observed[f"{role}_scores"]:
            raise ValueError(f"{role} score is not reproducible")
        for boundary, prefix in ((True, "boundary"), (False, "in_scope")):
            subset = tuple(case for case in cases if ("hard_negative" in case.tags) == boundary)
            ids = {case.id for case in subset}
            selected = tuple(item for item in parsed if item.case_id in ids)
            if score_predictions(subset, selected).to_dict() != observed[f"{prefix}_{role}_scores"]:
                raise ValueError(f"{prefix} {role} score is not reproducible")
    gains = losses = action_gains = action_losses = 0
    for index, case in enumerate(cases):
        before = score_predictions((case,), (predictions["baseline"][index],)).to_dict()["counts"]
        after = score_predictions((case,), (predictions["candidate"][index],)).to_dict()["counts"]
        gains += before["fully_correct_cases"] == 0 and after["fully_correct_cases"] == 1
        losses += before["fully_correct_cases"] == 1 and after["fully_correct_cases"] == 0
        action_gains += before["action_matches"] == 0 and after["action_matches"] == 1
        action_losses += before["action_matches"] == 1 and after["action_matches"] == 0
    return {
        "cases": len(cases),
        "restarts_after_case": expected_restarts,
        "full_exact": {
            "baseline": observed["baseline_scores"]["counts"]["fully_correct_cases"],
            "candidate": observed["candidate_scores"]["counts"]["fully_correct_cases"],
            "paired_gains": gains,
            "paired_losses": losses,
            "exact_mcnemar_two_sided": _exact_mcnemar(gains, losses),
        },
        "action": {
            "baseline": observed["baseline_scores"]["counts"]["action_matches"],
            "candidate": observed["candidate_scores"]["counts"]["action_matches"],
            "paired_gains": action_gains,
            "paired_losses": action_losses,
            "exact_mcnemar_two_sided": _exact_mcnemar(action_gains, action_losses),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.dataset, args.ledger, args.protocol, args.result), indent=2))


if __name__ == "__main__":
    main()
