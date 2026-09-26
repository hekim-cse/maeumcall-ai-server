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
    "배달:배달 지연 문의": "나무젓가락이 아직 안왔어요",
    "배달:주문 변경": "배달이 아직 안 왔어요",
    "배달:환불/재배달 문의": "혹시 짜장면을 짬뽕으로 변경 가능한가요?",
    "교수님:결석 사유 전달": "교수님 안녕하세요. 혹시 오늘 면담 요청해도 되나요?",
    "교수님:과제 문의": "교수님 안녕하세요. 혹시 오늘 오늘 공결 처리는 어떻게 하나요?",
    "교수님:면담 예약": "교수님 혹시 시험 범위 한 번 더 알려주실 수 있으신가요?",
    "예약:미용실 예약": "아우 배고파.",
    "예약:병원 예약": "여기 근처 맛집 알려줘.",
    "예약:스터디룸 예약": "쓰읍. 슬슬 머리 잘라야하는데.",
    "예약:식당 예약": "나 다리 아퍼.",
    "시청:대형폐기물 배출": "계란 껍질은 일반쓰레기로 버리나요?",
    "시청:여권 발급 문의": "가족 증명서 발급하고 싶어.",
    "시청:주민등록 등본 문의": "여기 가로등 불 꺼졌어요",
    "고객센터:a/s 접수": "아니 나 요금제 너무 비싸. 다른 걸로 바꿔줘.",
    "고객센터:요금/약정 상담": "아니 나 멤버십 vip 혜택 받고 싶은데 어떻게 사용해.",
    "고객센터:인터넷/통화 문제 문의": "나 핸드폰이 안켜져.",
}


def test_committed_human_draft_corpus_matches_its_authoring_sources() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    verified, _, _ = verify_compiled_authoring_corpus(
        SOURCE_DIR,
        SPLIT_ASSIGNMENTS_PATH,
        COMPILED_PATH,
    )

    assert verified == dataset
    assert len(dataset.cases) == 16
    assert {case.scenario_key: case.user_message for case in dataset.cases} == (
        EXPECTED_HUMAN_DRAFTS
    )
    assert {case.provenance for case in dataset.cases} == {"human_authored"}
    assert {case.review_status.value for case in dataset.cases} == {"draft"}
    assert {case.split.value for case in dataset.cases} == {"development"}
    assert {case.conversation_state for case in dataset.cases} == {"greeting"}
    assert {case.labels.user_action for case in dataset.cases} == {"unknown"}
    assert all(case.tags == ("hard_negative",) for case in dataset.cases)
