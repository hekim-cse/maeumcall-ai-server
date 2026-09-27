from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.structured_nlu.authoring import AuthoringGroup, compile_authoring_directory
from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.coverage_progress import build_development_coverage_progress
from evals.structured_nlu.drafting import (
    AICoverageCandidateManifestV2,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    render_ai_coverage_candidate_review_packet_v2,
    serialize_ai_coverage_candidate_manifest_v1,
    serialize_ai_coverage_candidate_manifest_v2,
    serialize_ai_coverage_candidate_schema_v1,
    serialize_ai_coverage_candidate_schema_v2,
)
from evals.structured_nlu.schema import ReviewStatus

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "evals/structured_nlu/data"
SOURCE_DIR = DATA_ROOT / "source"
SPLIT_ASSIGNMENTS = DATA_ROOT / "manifests/split-assignments.v1.json"
V1_CANDIDATE_PATH = REPO_ROOT / "evals/structured_nlu/drafts/coverage-candidates.v1.json"
V1_SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_coverage_candidate.schema.json"
V2_CANDIDATE_PATH = REPO_ROOT / "evals/structured_nlu/drafts/coverage-candidates.v2.json"
V2_SCHEMA_PATH = REPO_ROOT / "evals/structured_nlu/ai_coverage_candidate_v2.schema.json"
V2_PACKET_PATH = REPO_ROOT / "evals/structured_nlu/drafts/coverage-review-packet.v2.md"


def _diagnostic_cases(*manifests):
    return tuple(
        SimpleNamespace(
            id=suggestion.proposed_case.id,
            scenario_key=suggestion.scenario_key,
            conversation_state=suggestion.proposed_case.conversation_state,
            current_fields=suggestion.proposed_case.current_fields,
            offered_alternative_times=suggestion.proposed_case.offered_alternative_times,
            labels=suggestion.proposed_case.labels,
            tags=suggestion.proposed_case.tags,
            review_status=ReviewStatus.DRAFT,
        )
        for manifest in manifests
        for suggestion in manifest.suggestions
    )


def _missing_keys(report):
    return {
        (gap.scenario_key, gap.dimension, value)
        for gap in report.missing_obligations
        for value in gap.missing_values
    }


def test_v2_targets_the_exact_current_field_present_frontier_after_v1() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS)
    v1 = build_ai_coverage_candidate_manifest_v1()
    v2 = build_ai_coverage_candidate_manifest_v2()
    baseline = build_development_coverage_progress(
        dataset,
        diagnostic_cases=_diagnostic_cases(v1),
    )
    missing = {
        (gap.scenario_key, value)
        for gap in baseline.missing_obligations
        if gap.dimension is CoverageDimension.CURRENT_FIELD_PRESENT
        for value in gap.missing_values
    }
    primary = {(item.scenario_key, item.primary_obligation.value) for item in v2.suggestions}

    assert baseline.covered_obligation_count == 582
    assert baseline.missing_obligation_count == 980
    assert primary == missing
    assert len(primary) == 4
    assert v2.predecessor_candidate_set_id == v1.candidate_set_id
    assert (
        v2.predecessor_candidate_manifest_sha256
        == hashlib.sha256(serialize_ai_coverage_candidate_manifest_v1().encode("utf-8")).hexdigest()
    )


def test_v2_cases_clear_one_existing_field_and_pass_live_semantics() -> None:
    manifest = build_ai_coverage_candidate_manifest_v2()

    for suggestion in manifest.suggestions:
        proposed = suggestion.proposed_case
        assert proposed.current_fields[suggestion.target_field] is not None
        assert any(value is None for value in proposed.current_fields.values())
        assert all(value is None for value in proposed.labels.fields.values())
        assert proposed.labels.user_action == "change_detail"
        assert proposed.labels.change_field == suggestion.target_field
        assert tuple(tag.value for tag in proposed.tags) == ("correction",)
        assert suggestion.semantic_valid is True
        assert suggestion.baseline_obligation_missing is True


def test_v2_projection_is_the_exact_31_obligation_delta() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS)
    v1 = build_ai_coverage_candidate_manifest_v1()
    v2 = build_ai_coverage_candidate_manifest_v2()
    before = build_development_coverage_progress(
        dataset,
        diagnostic_cases=_diagnostic_cases(v1),
    )
    after = build_development_coverage_progress(
        dataset,
        diagnostic_cases=_diagnostic_cases(v1, v2),
    )
    gained = _missing_keys(before) - _missing_keys(after)
    declared = {
        (item.scenario_key, reference.dimension, reference.value)
        for item in v2.suggestions
        for reference in item.projected_obligations
    }

    assert gained == declared
    assert len(gained) == v2.projected_marginal_gain == 31
    assert after.covered_obligation_count == v2.projected_covered_obligation_count == 613
    assert after.missing_obligation_count == v2.projected_missing_obligation_count == 949
    assert len(dataset.cases) == 36
    assert all(
        gap.dimension is not CoverageDimension.CURRENT_FIELD_PRESENT
        for gap in after.missing_obligations
    )
    missing_by_scenario = Counter(
        {
            scenario_key: sum(
                len(gap.missing_values)
                for gap in after.missing_obligations
                if gap.scenario_key == scenario_key
            )
            for scenario_key in {
                gap.scenario_key
                for gap in after.missing_obligations
                if gap.scenario_key is not None
            }
        }
    )
    assert missing_by_scenario == {
        "고객센터:a/s 접수": 86,
        "고객센터:요금/약정 상담": 60,
        "고객센터:인터넷/통화 문제 문의": 78,
        "교수님:결석 사유 전달": 28,
        "교수님:과제 문의": 15,
        "교수님:면담 예약": 28,
        "배달:배달 지연 문의": 64,
        "배달:주문 변경": 62,
        "배달:환불/재배달 문의": 70,
        "시청:대형폐기물 배출": 58,
        "시청:여권 발급 문의": 73,
        "시청:주민등록 등본 문의": 68,
        "예약:미용실 예약": 43,
        "예약:병원 예약": 59,
        "예약:스터디룸 예약": 43,
        "예약:식당 예약": 39,
    }


def test_v2_artifacts_are_deterministic_and_v1_artifacts_stay_unchanged() -> None:
    assert V1_CANDIDATE_PATH.read_text(encoding="utf-8") == (
        serialize_ai_coverage_candidate_manifest_v1()
    )
    assert V1_SCHEMA_PATH.read_text(encoding="utf-8") == (
        serialize_ai_coverage_candidate_schema_v1()
    )
    assert V2_CANDIDATE_PATH.read_text(encoding="utf-8") == (
        serialize_ai_coverage_candidate_manifest_v2()
    )
    assert V2_SCHEMA_PATH.read_text(encoding="utf-8") == (
        serialize_ai_coverage_candidate_schema_v2()
    )
    assert V2_PACKET_PATH.read_text(encoding="utf-8") == (
        render_ai_coverage_candidate_review_packet_v2()
    )


def test_v2_payload_cannot_be_promoted_or_drifted() -> None:
    payload = json.loads(serialize_ai_coverage_candidate_manifest_v2())
    with pytest.raises(ValidationError):
        AuthoringGroup.model_validate(payload)

    payload["suggestions"][0]["proposed_case"]["user_message"] += " 수정"
    with pytest.raises(ValidationError, match="drifted from policy"):
        AICoverageCandidateManifestV2.model_validate(payload)


def test_v2_review_packet_keeps_candidates_unqualified() -> None:
    packet = render_ai_coverage_candidate_review_packet_v2()

    assert packet.count("[ ] 승인  [ ] 수정 필요  [ ] 거부") == 4
    assert "자동 승격 허용: `false`" in packet
    assert "투영 추가 충족 의무: `31`" in packet
    assert "human_authored로 표시할 수 없습니다" in packet


def test_v2_chain_check_requires_the_exact_predecessor_artifact(tmp_path: Path) -> None:
    predecessor = tmp_path / "coverage-candidates.v1.json"
    predecessor.write_text("{}\n", encoding="utf-8")
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]

    result = subprocess.run(
        [
            *base,
            "check-draft-coverage-candidates-v2",
            str(SOURCE_DIR),
            str(SPLIT_ASSIGNMENTS),
            str(predecessor),
            str(V2_CANDIDATE_PATH),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "predecessor manifest fingerprint differs" in result.stderr


@pytest.mark.parametrize(
    ("write_command", "check_command", "expected"),
    [
        (
            "draft-coverage-candidates-v2",
            "check-draft-coverage-candidates-v2",
            serialize_ai_coverage_candidate_manifest_v2,
        ),
        (
            "draft-coverage-schema-v2",
            "check-draft-coverage-schema-v2",
            serialize_ai_coverage_candidate_schema_v2,
        ),
        (
            "draft-coverage-review-packet-v2",
            "check-draft-coverage-review-packet-v2",
            render_ai_coverage_candidate_review_packet_v2,
        ),
    ],
)
def test_v2_cli_writes_and_checks_exact_artifacts(
    tmp_path: Path,
    write_command: str,
    check_command: str,
    expected,
) -> None:
    output = tmp_path / f"{write_command}.txt"
    base = [sys.executable, "-m", "scripts.compile_structured_nlu_corpus"]

    subprocess.run([*base, write_command, str(output)], cwd=REPO_ROOT, check=True)
    assert output.read_text(encoding="utf-8") == expected()
    check_args = (
        [str(SOURCE_DIR), str(SPLIT_ASSIGNMENTS), str(V1_CANDIDATE_PATH), str(output)]
        if check_command == "check-draft-coverage-candidates-v2"
        else [str(output)]
    )
    subprocess.run([*base, check_command, *check_args], cwd=REPO_ROOT, check=True)

    original = output.read_bytes()
    overwrite = subprocess.run(
        [*base, write_command, str(output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert overwrite.returncode != 0
    assert output.read_bytes() == original

    output.write_text("{}\n", encoding="utf-8")
    stale = subprocess.run(
        [*base, check_command, *check_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0
