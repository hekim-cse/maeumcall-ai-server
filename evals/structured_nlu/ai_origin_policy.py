from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.coverage_candidate_policy import COVERAGE_CANDIDATE_SPECS_V1
from evals.structured_nlu.coverage_candidate_policy_v2 import COVERAGE_CANDIDATE_SPECS_V2
from evals.structured_nlu.coverage_candidate_policy_v3 import COVERAGE_CANDIDATE_SPECS_V3
from evals.structured_nlu.draft_seed_policy import AI_DRAFT_SEED_SPECS_V1
from evals.structured_nlu.subagent_candidate_policy import AI_SUBAGENT_CANDIDATE_SPECS_V1

AI_ORIGIN_ID_PREFIXES_V1 = ("ai-seed-", "ai-subagent-")
AI_ORIGIN_ID_PREFIXES_V2 = (*AI_ORIGIN_ID_PREFIXES_V1, "ai-coverage-")
AI_ORIGIN_ID_PREFIXES_V3 = AI_ORIGIN_ID_PREFIXES_V2
AI_ORIGIN_ID_PREFIXES_V4 = AI_ORIGIN_ID_PREFIXES_V3
AI_ORIGIN_POLICY_ID_V1 = "maeumcall-structured-nlu-ai-origin-policy-v1"
AI_ORIGIN_POLICY_ID_V2 = "maeumcall-structured-nlu-ai-origin-policy-v2"
AI_ORIGIN_POLICY_ID_V3 = "maeumcall-structured-nlu-ai-origin-policy-v3"
AI_ORIGIN_POLICY_ID_V4 = "maeumcall-structured-nlu-ai-origin-policy-v4"
CURRENT_AI_ORIGIN_POLICY_SCHEMA_VERSION = 4
AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1 = "nfc-utf8-sha256-v1"
EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1 = (
    "75074881c33a8c6174f6827c58d2b593783c5e77190d6b6f6219f55fd1f87b78"
)
EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2 = (
    "25dbf8816653a97d6f8e7fc84cfa2f7676745febd9af80a04257bbf4b98ccee1"
)
EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3 = (
    "aaef2c3919acd490c34327a2bee214ffdb7d62da416124953f7571812bd0f190"
)
EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4 = (
    "2fa6122b17724edf036a1734b5da2d37f94843a229f3de87bbc07ac9a93c5f96"
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

_AI_ORIGIN_TEXTS_V2 = (
    *_AI_ORIGIN_TEXTS_V1,
    *(spec.user_message for spec in COVERAGE_CANDIDATE_SPECS_V1.values()),
)
AI_ORIGIN_TEXT_FINGERPRINTS_V2 = frozenset(
    ai_origin_text_fingerprint_v1(value) for value in _AI_ORIGIN_TEXTS_V2
)
if len(AI_ORIGIN_TEXT_FINGERPRINTS_V2) != len(_AI_ORIGIN_TEXTS_V2):
    raise RuntimeError("AI-origin V2 texts must be globally unique after NFC normalization")

_AI_ORIGIN_TEXTS_V3 = (
    *_AI_ORIGIN_TEXTS_V2,
    *(spec.user_message for spec in COVERAGE_CANDIDATE_SPECS_V2.values()),
)
AI_ORIGIN_TEXT_FINGERPRINTS_V3 = frozenset(
    ai_origin_text_fingerprint_v1(value) for value in _AI_ORIGIN_TEXTS_V3
)
if len(AI_ORIGIN_TEXT_FINGERPRINTS_V3) != len(_AI_ORIGIN_TEXTS_V3):
    raise RuntimeError("AI-origin V3 texts must be globally unique after NFC normalization")

_AI_ORIGIN_TEXTS_V4 = (
    *_AI_ORIGIN_TEXTS_V3,
    *(spec.user_message for spec in COVERAGE_CANDIDATE_SPECS_V3.values()),
)
AI_ORIGIN_TEXT_FINGERPRINTS_V4 = frozenset(
    ai_origin_text_fingerprint_v1(value) for value in _AI_ORIGIN_TEXTS_V4
)
if len(AI_ORIGIN_TEXT_FINGERPRINTS_V4) != len(_AI_ORIGIN_TEXTS_V4):
    raise RuntimeError("AI-origin V4 texts must be globally unique after NFC normalization")


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


def ai_origin_policy_payload_v2() -> dict[str, object]:
    """Extend immutable V1 with coverage candidates without rewriting its entries."""
    v1_entries = ai_origin_policy_payload_v1()["entries"]
    if not isinstance(v1_entries, list):
        raise RuntimeError("AI-origin policy V1 entries must be a list")
    coverage_entries = [
        {
            "origin_id": f"ai-coverage-v1-{spec.slug}",
            "origin_kind": "coverage_candidate",
            "scenario_key": spec.scenario_key,
            "text_fingerprint": ai_origin_text_fingerprint_v1(spec.user_message),
        }
        for spec in COVERAGE_CANDIDATE_SPECS_V1.values()
    ]
    return {
        "ai_origin_policy_schema_version": 2,
        "policy_id": AI_ORIGIN_POLICY_ID_V2,
        "text_fingerprint_algorithm": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1,
        "reserved_id_prefixes": sorted(AI_ORIGIN_ID_PREFIXES_V2),
        "entries": sorted(
            [*v1_entries, *coverage_entries], key=lambda entry: str(entry["origin_id"])
        ),
    }


def ai_origin_policy_fingerprint_v2() -> str:
    canonical = json.dumps(
        ai_origin_policy_payload_v2(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_ai_origin_policy_v2() -> str:
    payload = {
        **ai_origin_policy_payload_v2(),
        "policy_fingerprint": ai_origin_policy_fingerprint_v2(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def ai_origin_policy_payload_v3() -> dict[str, object]:
    """Extend immutable V2 with coverage batch-002 without rewriting history."""
    v2_entries = ai_origin_policy_payload_v2()["entries"]
    if not isinstance(v2_entries, list):
        raise RuntimeError("AI-origin policy V2 entries must be a list")
    coverage_entries = [
        {
            "origin_id": f"ai-coverage-v2-{spec.slug}",
            "origin_kind": "coverage_candidate_batch_002",
            "scenario_key": spec.scenario_key,
            "text_fingerprint": ai_origin_text_fingerprint_v1(spec.user_message),
        }
        for spec in COVERAGE_CANDIDATE_SPECS_V2.values()
    ]
    return {
        "ai_origin_policy_schema_version": 3,
        "policy_id": AI_ORIGIN_POLICY_ID_V3,
        "text_fingerprint_algorithm": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1,
        "reserved_id_prefixes": sorted(AI_ORIGIN_ID_PREFIXES_V3),
        "entries": sorted(
            [*v2_entries, *coverage_entries], key=lambda entry: str(entry["origin_id"])
        ),
    }


def ai_origin_policy_fingerprint_v3() -> str:
    canonical = json.dumps(
        ai_origin_policy_payload_v3(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_ai_origin_policy_v3() -> str:
    payload = {
        **ai_origin_policy_payload_v3(),
        "policy_fingerprint": ai_origin_policy_fingerprint_v3(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def ai_origin_policy_payload_v4() -> dict[str, object]:
    """Extend immutable V3 with coverage batch-003 without rewriting history."""
    v3_entries = ai_origin_policy_payload_v3()["entries"]
    if not isinstance(v3_entries, list):
        raise RuntimeError("AI-origin policy V3 entries must be a list")
    coverage_entries = [
        {
            "origin_id": f"ai-coverage-v3-{spec.slug}",
            "origin_kind": "coverage_candidate_batch_003",
            "scenario_key": spec.scenario_key,
            "text_fingerprint": ai_origin_text_fingerprint_v1(spec.user_message),
        }
        for spec in COVERAGE_CANDIDATE_SPECS_V3.values()
    ]
    return {
        "ai_origin_policy_schema_version": 4,
        "policy_id": AI_ORIGIN_POLICY_ID_V4,
        "text_fingerprint_algorithm": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1,
        "reserved_id_prefixes": sorted(AI_ORIGIN_ID_PREFIXES_V4),
        "entries": sorted(
            [*v3_entries, *coverage_entries], key=lambda entry: str(entry["origin_id"])
        ),
    }


def ai_origin_policy_fingerprint_v4() -> str:
    canonical = json.dumps(
        ai_origin_policy_payload_v4(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_ai_origin_policy_v4() -> str:
    payload = {
        **ai_origin_policy_payload_v4(),
        "policy_fingerprint": ai_origin_policy_fingerprint_v4(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def serialize_ai_origin_policy_schema_v3() -> str:
    """Serialize the committed validation contract for policy V3 artifacts."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:maeumcall:structured-nlu:ai-origin-policy:v3",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ai_origin_policy_schema_version",
            "policy_id",
            "text_fingerprint_algorithm",
            "reserved_id_prefixes",
            "entries",
            "policy_fingerprint",
        ],
        "properties": {
            "ai_origin_policy_schema_version": {"const": 3},
            "policy_id": {"const": AI_ORIGIN_POLICY_ID_V3},
            "text_fingerprint_algorithm": {"const": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1},
            "reserved_id_prefixes": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "entries": {
                "type": "array",
                "minItems": 60,
                "maxItems": 60,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "origin_id",
                        "origin_kind",
                        "scenario_key",
                        "text_fingerprint",
                    ],
                    "properties": {
                        "origin_id": {"type": "string", "minLength": 1},
                        "origin_kind": {"type": "string", "minLength": 1},
                        "scenario_key": {"type": "string", "minLength": 1},
                        "text_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    },
                },
            },
            "policy_fingerprint": {"const": EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3},
        },
    }
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def serialize_ai_origin_policy_schema_v4() -> str:
    """Serialize the committed validation contract for policy V4 artifacts."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:maeumcall:structured-nlu:ai-origin-policy:v4",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ai_origin_policy_schema_version",
            "policy_id",
            "text_fingerprint_algorithm",
            "reserved_id_prefixes",
            "entries",
            "policy_fingerprint",
        ],
        "properties": {
            "ai_origin_policy_schema_version": {"const": 4},
            "policy_id": {"const": AI_ORIGIN_POLICY_ID_V4},
            "text_fingerprint_algorithm": {"const": AI_ORIGIN_TEXT_FINGERPRINT_ALGORITHM_V1},
            "reserved_id_prefixes": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "entries": {
                "type": "array",
                "minItems": 91,
                "maxItems": 91,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "origin_id",
                        "origin_kind",
                        "scenario_key",
                        "text_fingerprint",
                    ],
                    "properties": {
                        "origin_id": {"type": "string", "minLength": 1},
                        "origin_kind": {"type": "string", "minLength": 1},
                        "scenario_key": {"type": "string", "minLength": 1},
                        "text_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    },
                },
            },
            "policy_fingerprint": {"const": EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4},
        },
    }
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if ai_origin_policy_fingerprint_v1() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1:
    raise RuntimeError("AI-origin policy V1 changed; create a new version instead of rewriting V1")
if ai_origin_policy_fingerprint_v2() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2:
    raise RuntimeError("AI-origin policy V2 changed; create a new version instead of rewriting V2")
if ai_origin_policy_fingerprint_v3() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3:
    raise RuntimeError("AI-origin policy V3 changed; create a new version instead of rewriting V3")
if ai_origin_policy_fingerprint_v4() != EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4:
    raise RuntimeError("AI-origin policy V4 changed; create a new version instead of rewriting V4")


@dataclass(frozen=True)
class AIOriginPolicyDescriptor:
    schema_version: int
    policy_id: str
    policy_fingerprint: str
    reserved_id_prefixes: tuple[str, ...]
    text_fingerprints: frozenset[str]


def _policy_descriptors() -> MappingProxyType[int, AIOriginPolicyDescriptor]:
    return MappingProxyType(
        {
            1: AIOriginPolicyDescriptor(
                1,
                AI_ORIGIN_POLICY_ID_V1,
                EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V1,
                AI_ORIGIN_ID_PREFIXES_V1,
                AI_ORIGIN_TEXT_FINGERPRINTS_V1,
            ),
            2: AIOriginPolicyDescriptor(
                2,
                AI_ORIGIN_POLICY_ID_V2,
                EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V2,
                AI_ORIGIN_ID_PREFIXES_V2,
                AI_ORIGIN_TEXT_FINGERPRINTS_V2,
            ),
            3: AIOriginPolicyDescriptor(
                3,
                AI_ORIGIN_POLICY_ID_V3,
                EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V3,
                AI_ORIGIN_ID_PREFIXES_V3,
                AI_ORIGIN_TEXT_FINGERPRINTS_V3,
            ),
            4: AIOriginPolicyDescriptor(
                4,
                AI_ORIGIN_POLICY_ID_V4,
                EXPECTED_AI_ORIGIN_POLICY_FINGERPRINT_V4,
                AI_ORIGIN_ID_PREFIXES_V4,
                AI_ORIGIN_TEXT_FINGERPRINTS_V4,
            ),
        }
    )


def ai_origin_policy_descriptor(schema_version: int) -> AIOriginPolicyDescriptor:
    if type(schema_version) is not int or schema_version not in (1, 2, 3, 4):
        raise ValueError("unsupported AI-origin policy schema version")
    return _policy_descriptors()[schema_version]


def serialize_ai_origin_policy(schema_version: int) -> str:
    serializers = {
        1: serialize_ai_origin_policy_v1,
        2: serialize_ai_origin_policy_v2,
        3: serialize_ai_origin_policy_v3,
        4: serialize_ai_origin_policy_v4,
    }
    ai_origin_policy_descriptor(schema_version)
    return serializers[schema_version]()


def is_reserved_ai_origin_id_v1(value: str) -> bool:
    return value.startswith(AI_ORIGIN_ID_PREFIXES_V1)


def is_verbatim_ai_origin_text_v1(user_message: str) -> bool:
    """Reject exact NFC-equivalent AI text globally, regardless of scenario or ID."""
    return ai_origin_text_fingerprint_v1(user_message) in AI_ORIGIN_TEXT_FINGERPRINTS_V1


def is_reserved_ai_origin_id_for_policy(value: str, schema_version: int) -> bool:
    descriptor = ai_origin_policy_descriptor(schema_version)
    return value.startswith(descriptor.reserved_id_prefixes)


def is_verbatim_ai_origin_text_for_policy(user_message: str, schema_version: int) -> bool:
    descriptor = ai_origin_policy_descriptor(schema_version)
    return ai_origin_text_fingerprint_v1(user_message) in descriptor.text_fingerprints


def is_reserved_ai_origin_id(value: str) -> bool:
    """Apply the latest additive AI-origin ID denylist."""
    return is_reserved_ai_origin_id_for_policy(value, CURRENT_AI_ORIGIN_POLICY_SCHEMA_VERSION)


def is_verbatim_ai_origin_text(user_message: str) -> bool:
    """Apply the latest additive exact-text denylist."""
    return is_verbatim_ai_origin_text_for_policy(
        user_message, CURRENT_AI_ORIGIN_POLICY_SCHEMA_VERSION
    )
