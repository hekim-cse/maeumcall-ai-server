import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.generate_scenario_tts_auditions import (
    SCENARIO_AUDITION_LINES,
    validate_audition_contract,
)
from services.flow.registry import FLOW_REGISTRY
from services.tts.casting import (
    SCENARIO_VOICE_CAST,
    TTSProviderId,
    get_scenario_voice_assignment,
)

pytestmark = pytest.mark.unit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_scenario_cast_and_lines_cover_every_registered_flow():
    validate_audition_contract()

    assert len(FLOW_REGISTRY) == 32
    assert set(SCENARIO_VOICE_CAST) == set(FLOW_REGISTRY)
    assert set(SCENARIO_AUDITION_LINES) == set(FLOW_REGISTRY)


def test_user_selected_cast_is_explicit_for_every_category():
    expected = {
        "예약": ("nvidia-magpie", "sofia"),
        "교수님": ("qwen3-tts", "eric"),
        "배달": ("nvidia-magpie", "jason"),
        "시청": ("nvidia-magpie", "sofia"),
        "고객센터": ("nvidia-magpie", "sofia"),
        "가족": ("nvidia-magpie", "aria"),
        "친구": ("qwen3-tts", "serena"),
        "연인": ("qwen3-tts", "uncle_fu"),
        "회사": ("nvidia-magpie", "leo"),
    }

    for scenario_key, registration in FLOW_REGISTRY.items():
        assignment = SCENARIO_VOICE_CAST[scenario_key]
        assert (assignment.provider.value, assignment.voice) == expected[registration.category]


def test_cast_provider_counts_match_selected_32_scenarios():
    counts = Counter(assignment.provider for assignment in SCENARIO_VOICE_CAST.values())

    assert counts == {
        TTSProviderId.QWEN3_TTS: 12,
        TTSProviderId.NVIDIA_MAGPIE: 20,
    }


def test_mobile_label_variants_resolve_to_the_approved_cast():
    assignment = get_scenario_voice_assignment(" 고객센터 ", "🛠️ A/S 접수")

    assert assignment is not None
    assert assignment.provider is TTSProviderId.NVIDIA_MAGPIE
    assert assignment.voice == "sofia"


def test_audition_lines_are_short_public_role_lines():
    for line in SCENARIO_AUDITION_LINES.values():
        assert line.text.strip() == line.text
        assert 10 <= len(line.text) <= 100
        assert line.rationale


def test_committed_qwen_cast_manifest_matches_approved_scenarios():
    manifest_path = (
        REPOSITORY_ROOT / "artifacts/tts-scenario-auditions/cast-v1/qwen3-tts/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]

    assert manifest["castVersion"] == 1
    assert manifest["provider"] == "qwen3-tts"
    assert len(artifacts) == 12
    assert {artifact["scenarioKey"] for artifact in artifacts} == {
        key
        for key, assignment in SCENARIO_VOICE_CAST.items()
        if assignment.provider is TTSProviderId.QWEN3_TTS
    }
    for artifact in artifacts:
        assignment = SCENARIO_VOICE_CAST[artifact["scenarioKey"]]
        line = SCENARIO_AUDITION_LINES[artifact["scenarioKey"]]
        assert artifact["voice"] == assignment.voice
        assert artifact["text"] == line.text
        assert len(artifact["sha256"]) == 64
