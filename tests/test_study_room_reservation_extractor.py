from services.flow.reservation.study_room.extractor import extract_study_room_reservation_info


def test_extract_study_room_reservation_full_info():
    result = extract_study_room_reservation_info(
        "내일 오후 두 시부터 두 시간 4명 김개굴 이름으로 예약하고 싶어요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "김개굴"


def test_extract_study_room_reservation_numeric_time_and_duration():
    result = extract_study_room_reservation_info(
        "오늘 오후 3시부터 2시간 3명 이용 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["start_time"] == "오후 3시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "3명"
    assert result["user_name"] is None


def test_extract_study_room_reservation_weekend():
    result = extract_study_room_reservation_info(
        "이번 주말 오전 10시부터 세 시간 다섯 명 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "이번 주말"
    assert result["start_time"] == "오전 10시"
    assert result["duration"] == "3시간"
    assert result["party_size"] == "5명"


def test_extract_study_room_reservation_user_name_with_reserver_phrase():
    result = extract_study_room_reservation_info(
        "예약자는 홍길동입니다. 내일 오후 2시부터 두 시간 4명 예약하고 싶어요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "홍길동"


def test_extract_study_room_reservation_missing_duration():
    result = extract_study_room_reservation_info(
        "내일 오후 2시에 4명 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] is None
    assert result["party_size"] == "4명"


def test_extract_study_room_reservation_missing_party_size():
    result = extract_study_room_reservation_info(
        "내일 오후 2시부터 두 시간 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["start_time"] == "오후 2시"
    assert result["duration"] == "2시간"
    assert result["party_size"] is None
