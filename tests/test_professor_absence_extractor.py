from services.flow.professor.absence.extractor import (
    extract_professor_absence_info,
)


def test_extract_professor_absence_full_info():
    result = extract_professor_absence_info(
        "김개굴 학생입니다. 오늘 운영체제 수업에 몸이 좋지 않아 결석하게 되어 연락드렸습니다."
    )

    assert result["intent"] == "absence_notice"
    assert result["class_name"] == "운영체제"
    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "몸이 좋지 않음"
    assert result["user_name"] == "김개굴"


def test_extract_professor_absence_hospital_reason():
    result = extract_professor_absence_info(
        "내일 병원에 가게 되어 결석하게 되었습니다."
    )

    assert result["absence_date"] == "내일"
    assert result["absence_reason"] == "병원 방문"


def test_extract_professor_absence_personal_reason():
    result = extract_professor_absence_info(
        "오늘 개인 사정으로 결석하게 되어 연락드렸습니다."
    )

    assert result["absence_date"] == "오늘"
    assert result["absence_reason"] == "개인 사정"


def test_extract_professor_absence_user_name():
    result = extract_professor_absence_info(
        "김개굴이라고 합니다."
    )

    assert result["user_name"] == "김개굴"


def test_extract_professor_absence_missing_fields():
    result = extract_professor_absence_info(
        "결석 사유를 말씀드리려고 연락드렸습니다."
    )

    assert result["absence_date"] is None
    assert result["absence_reason"] is None
    assert result["user_name"] is None
