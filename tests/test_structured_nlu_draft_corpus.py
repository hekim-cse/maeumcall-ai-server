from pathlib import Path

from evals.structured_nlu.authoring import (
    compile_authoring_directory,
    verify_compiled_authoring_corpus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "evals/structured_nlu/data/source"
SPLIT_ASSIGNMENTS_PATH = REPO_ROOT / "evals/structured_nlu/data/manifests/split-assignments.v1.json"
COMPILED_PATH = REPO_ROOT / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"

EXPECTED_HUMAN_DRAFTS = {
    "교수님:결석 사유 전달": "교수님 안녕하세요. 혹시 오늘 면담 요청해도 되나요?",
    "교수님:과제 문의": "교수님 안녕하세요. 혹시 오늘 오늘 공결 처리는 어떻게 하나요?",
    "교수님:면담 예약": "교수님 혹시 시험 범위 한 번 더 알려주실 수 있으신가요?",
    "예약:미용실 예약": "아우 배고파.",
    "예약:병원 예약": "여기 근처 맛집 알려줘.",
    "예약:스터디룸 예약": "쓰읍. 슬슬 머리 잘라야하는데.",
    "예약:식당 예약": "나 다리 아퍼.",
}


def test_committed_human_draft_corpus_matches_its_authoring_sources() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    verified, _, _ = verify_compiled_authoring_corpus(
        SOURCE_DIR,
        SPLIT_ASSIGNMENTS_PATH,
        COMPILED_PATH,
    )

    assert verified == dataset
    assert len(dataset.cases) == 7
    assert {case.scenario_key: case.user_message for case in dataset.cases} == (
        EXPECTED_HUMAN_DRAFTS
    )
    assert {case.provenance for case in dataset.cases} == {"human_authored"}
    assert {case.review_status.value for case in dataset.cases} == {"draft"}
    assert {case.split.value for case in dataset.cases} == {"development"}
    assert {case.conversation_state for case in dataset.cases} == {"greeting"}
    assert {case.labels.user_action for case in dataset.cases} == {"unknown"}
    assert all(case.tags == ("hard_negative",) for case in dataset.cases)
