from pathlib import Path

from evals.structured_nlu.authoring import (
    compile_authoring_directory,
    verify_compiled_authoring_corpus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "evals/structured_nlu/data/source"
SPLIT_ASSIGNMENTS_PATH = REPO_ROOT / "evals/structured_nlu/data/manifests/split-assignments.v1.json"
COMPILED_PATH = REPO_ROOT / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"

EXPECTED_HARD_NEGATIVE_DRAFTS = {
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

EXPECTED_INFORMATION_DRAFTS = {
    "교수님:결석 사유 전달": {
        "message": "교수님 안녕하세요. 인공지능 수업 수강하는 홍길동입니다. 오늘 예비군으로 결석하게될 거 같아 연락드립니다.",
        "intent": "absence_notice",
        "user_action": "provide_absence_info",
        "fields": {
            "absence_date": "오늘",
            "absence_reason": "예비군",
            "class_name": "인공지능",
            "user_name": "홍길동",
        },
    },
    "교수님:과제 문의": {
        "message": "교수님 안녕하세요. ~수업듣는 홍길동입니다. ~수업에서 과제로 내주신 범위를 다시 확인하고 싶어 연락드립니다.",
        "intent": "assignment_inquiry",
        "user_action": "provide_assignment_info",
        "fields": {
            "assignment_topic": "과제 범위 확인",
            "course_name": "~",
            "question": "과제 범위 확인",
            "user_name": "홍길동",
        },
    },
    "교수님:면담 예약": {
        "message": "교수님 안녕하세요. ~학과 홍길동입니다. 혹시 취업에 관해 오늘 5시에 면담 가능하시나요?",
        "intent": "appointment_booking",
        "user_action": "provide_appointment_info",
        "fields": {
            "appointment_purpose": "취업",
            "date": "오늘",
            "time": "5시",
            "user_name": "홍길동",
        },
    },
    "예약:미용실 예약": {
        "message": "안녕하세요. 내일 2시에 컷으로 예약 가능하나요?",
        "intent": "reservation",
        "user_action": "continue_collecting",
        "fields": {"date": "내일", "service_type": "컷", "time": "2시"},
    },
    "예약:병원 예약": {
        "message": "안녕하세요. 오늘 3시에 이비인후과 예약하려고 하는데요.",
        "intent": "reservation",
        "user_action": "continue_collecting",
        "fields": {"date": "오늘", "department": "이비인후과", "time": "3시"},
    },
    "예약:스터디룸 예약": {
        "message": "안녕하세요. 오늘 5시에 1명 예약 가능하나요?",
        "intent": "reservation",
        "user_action": "continue_collecting",
        "fields": {"date": "오늘", "party_size": "1명", "start_time": "5시"},
    },
    "예약:식당 예약": {
        "message": "안녕하세요. 9/26일날 5명 예약하려고 하는데 가능하나요?",
        "intent": "reservation",
        "user_action": "continue_collecting",
        "fields": {"date": "9/26", "party_size": "5명"},
    },
}


def test_committed_human_draft_corpus_matches_its_authoring_sources() -> None:
    dataset = compile_authoring_directory(SOURCE_DIR, SPLIT_ASSIGNMENTS_PATH)
    verified, _, _ = verify_compiled_authoring_corpus(
        SOURCE_DIR,
        SPLIT_ASSIGNMENTS_PATH,
        COMPILED_PATH,
    )

    assert verified == dataset
    assert len(dataset.cases) == 23
    assert {case.provenance for case in dataset.cases} == {"human_authored"}
    assert {case.review_status.value for case in dataset.cases} == {"draft"}
    assert {case.split.value for case in dataset.cases} == {"development"}
    assert {case.conversation_state for case in dataset.cases} == {"greeting"}

    hard_negatives = [case for case in dataset.cases if case.tags == ("hard_negative",)]
    assert len(hard_negatives) == 16
    assert {case.scenario_key: case.user_message for case in hard_negatives} == (
        EXPECTED_HARD_NEGATIVE_DRAFTS
    )
    assert {case.labels.user_action for case in hard_negatives} == {"unknown"}

    information_cases = [case for case in dataset.cases if case.tags == ("multi_field",)]
    assert len(information_cases) == 7
    assert {case.scenario_key for case in information_cases} == set(EXPECTED_INFORMATION_DRAFTS)
    for case in information_cases:
        expected = EXPECTED_INFORMATION_DRAFTS[case.scenario_key]
        assert case.user_message == expected["message"]
        assert case.labels.intent == expected["intent"]
        assert case.labels.user_action == expected["user_action"]
        assert case.offered_alternative_times == ()
        assert case.current_fields == {}
        if "selected_time" in case.labels.fields:
            assert case.labels.fields["selected_time"] is None
        for field_name, label in case.labels.fields.items():
            expected_value = expected["fields"].get(field_name)
            if expected_value is None:
                assert label is None
            else:
                assert label is not None
                assert label.accepted_values == (expected_value,)
