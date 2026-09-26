from __future__ import annotations

import hashlib
import json
import unicodedata

from evals.structured_nlu.draft_seed_policy import AI_DRAFT_SEED_SPECS_V1
from evals.structured_nlu.subagent_candidate_policy import AI_SUBAGENT_CANDIDATE_SPECS_V1

AI_ORIGIN_ID_PREFIXES_V1 = ("ai-seed-", "ai-subagent-")
AI_ORIGIN_POLICY_ID_V1 = "maeumcall-structured-nlu-ai-origin-policy-v1"
AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1 = "nfc-utf8-sha256-v1"
EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1 = (
    "75074881c33a8c6174f6827c58d2b593783c5e77190d6b6f6219f55fd1f87b78"
)


def canonical_ai_origin_text_v1(value: str) -> str:
    """Canonicalize exact AI-origin text without fuzzy or whitespace heuristics."""
    return unicodedata.normalize("NFC", value)


def ai_origin_text_fingerprint_v1(value: str) -> str:
    canonical = canonical_ai_origin_text_v1(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_AI_ORIGIN_TEXTS_V1 = tuple(
    spec.user_message
    for spec in (
        *AI_DRAFT_SEED_SPECS_V1.values(),
        *AI_SUBAGENT_CANDIDATE_SPECS_V1.values(),
    )
)
AI_ORIGIN_TEXT_FINGERPRINTS_V1 = frozenset(
    ai_origin_text_fingerprint_v1(value) for value in _AI_ORIGIN_TEXTS_V1
)
if len(AI_ORIGIN_TEXT_FINGERPRINTS_V1) != len(_AI_ORIGIN_TEXTS_V1):
    raise RuntimeError("AI-origin texts must be globally unique after NFC normalization")


def ai_origin_policy_payload_v1() -> dict[str, object]:
    entries = []
    for scenario_key, spec in AI_DRAFT_SEED_SPECS_V1.items():
        entries.append(
            {
                "origin_id": f"ai-seed-{spec.slug}",
                "origin_kind": "bootstrap_seed",
                "scenario_key": scenario_key,
                "text_fingerprint": ai_origin_text_fingerprint_v1(spec.user_message),
            }
        )
    for scenario_key, spec in AI_SUBAGENT_CANDIDATE_SPECS_V1.items():
        entries.append(
            {
                "origin_id": f"ai-subagent-{spec.slug}",
                "origin_kind": "subagent_candidate",
                "scenario_key": scenario_key,
                "text_fingerprint": ai_origin_text_fingerprint_v1(spec.user_message),
            }
        )
    return {
        "ai_origin_policy_schema_version": 1,
        "policy_id": AI_ORIGIN_POLICY_ID_V1,
        "text_fingerprint_algorithm": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1,
        "reserved_id_prefixes": sorted(AI_ORIGIN_ID_PREFIXES_V1),
        "entries": sorted(entries, key=lambda entry: str(entry["origin_id"])),
    }


def ai_origin_policy_fingerprint_v1() -> str:
    canonical = json.dumps(
        ai_origin_policy_payload_v1(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_ai_origin_policy_v1() -> str:
    payload = {
        **ai_origin_policy_payload_v1(),
        "policy_fingerprint": ai_origin_policy_fingerprint_v1(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if ai_origin_policy_fingerprint_v1() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1:
    raise RuntimeError("AI-origin policy V1 changed; create a new version instead of rewriting V1")


def is_reserved_ai_origin_id_v1(value: str) -> bool:
    return value.startswith(AI_ORIGIN_ID_PREFIXES_V1)


def is_verbatim_ai_origin_text_v1(user_message: str) -> bool:
    """Reject exact NFC-equivalent AI text globally, regardless of scenario or ID."""
    return ai_origin_text_fingerprint_v1(user_message) in AI_ORIGIN_TEXT_FINGERPRINTS_V1
