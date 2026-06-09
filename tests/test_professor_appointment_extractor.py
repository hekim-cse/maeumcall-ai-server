from services.flow.professor.appointment.extractor import (
    extract_professor_appointment_info,
)


def test_extract_professor_appointment_full_info():
    result = extract_professor_appointment_info(
        "진로 상담 관련해서 이번 주 수요일 오후 3시에 김개굴 학생입니다. 면담 가능할까요?"
    )

    assert result["intent"] == "appointment_booking"
    assert result["appointment_purpose"] == "진로 상담"
    assert result["date"] == "이번 주 수요일"
    assert result["time"] == "오후 3시"
    assert result["user_name"] == "김개굴"


def test_extract_professor_appointment_assignment_purpose():
    result = extract_professor_appointment_info(
        "과제 관련해서 면담 요청드리고 싶습니다."
    )

    assert result["appointment_purpose"] == "과제"


def test_extract_professor_appointment_date_and_time():
    result = extract_professor_appointment_info(
        "다음 주 월요일 오전 10시에 가능하실까요?"
    )

    assert result["date"] == "다음 주 월요일"
    assert result["time"] == "오전 10시"


def test_extract_professor_appointment_user_name():
    result = extract_professor_appointment_info(
        "김개굴이라고 합니다."
    )

    assert result["user_name"] == "김개굴"


def test_extract_professor_appointment_missing_fields():
    result = extract_professor_appointment_info(
        "면담 예약하고 싶습니다."
    )

    assert result["appointment_purpose"] == "면담"
    assert result["date"] is None
    assert result["time"] is None
    assert result["user_name"] is None
