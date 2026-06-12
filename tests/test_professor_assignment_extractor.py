from services.flow.professor.assignment.extractor import (
    extract_professor_assignment_info,
)


def test_extract_professor_assignment_full_info():
    result = extract_professor_assignment_info(
        "김개굴 학생입니다. 과제 제출 형식을 여쭤보고 싶습니다."
    )

    assert result["intent"] == "assignment_inquiry"
    assert result["assignment_topic"] == "제출 형식"
    assert result["question"] is not None
    assert result["user_name"] == "김개굴"


def test_extract_professor_assignment_due_date_topic():
    result = extract_professor_assignment_info(
        "과제 제출 기한이 언제인지 궁금합니다."
    )

    assert result["assignment_topic"] == "제출 기한"
    assert result["question"] is not None


def test_extract_professor_assignment_report_topic():
    result = extract_professor_assignment_info(
        "보고서 과제 분량이 몇 장인지 여쭤보고 싶습니다."
    )

    assert result["assignment_topic"] == "보고서"
    assert result["question"] is not None


def test_extract_professor_assignment_user_name():
    result = extract_professor_assignment_info(
        "김개굴이라고 합니다."
    )

    assert result["user_name"] == "김개굴"


def test_extract_professor_assignment_missing_fields():
    result = extract_professor_assignment_info(
        "과제 문의드리고 싶습니다."
    )

    assert result["assignment_topic"] == "과제"
    assert result["question"] is None
    assert result["user_name"] is None
