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
    assert len(dataset.cases) == 4
    assert {case.scenario_key: case.user_message for case in dataset.cases} == (
        EXPECTED_HUMAN_DRAFTS
    )
    assert {case.provenance for case in dataset.cases} == {"human_authored"}
    assert {case.review_status.value for case in dataset.cases} == {"draft"}
    assert {case.split.value for case in dataset.cases} == {"development"}
    assert {case.conversation_state for case in dataset.cases} == {"greeting"}
    assert {case.labels.user_action for case in dataset.cases} == {"unknown"}
    assert all(case.tags == ("hard_negative",) for case in dataset.cases)
