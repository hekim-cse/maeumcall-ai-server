from services.flow.reservation.hair_salon.extractor import extract_hair_salon_reservation_info


def test_extract_hair_salon_reservation_full_info():
    result = extract_hair_salon_reservation_info(
        "내일 오후 3시에 커트 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["service_type"] == "커트"
    assert result["designer"] is None
    assert result["user_name"] is None


def test_extract_hair_salon_reservation_with_user_name():
    result = extract_hair_salon_reservation_info(
        "오늘 저녁 6시에 김개굴 이름으로 펌 예약하고 싶어요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 6시"
    assert result["service_type"] == "펌"
    assert result["designer"] is None
    assert result["user_name"] == "김개굴"


def test_extract_hair_salon_reservation_with_designer():
    result = extract_hair_salon_reservation_info(
        "내일 오후 3시에 수진 디자이너님으로 커트 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "수진"


def test_extract_hair_salon_reservation_with_teacher_phrase():
    result = extract_hair_salon_reservation_info(
        "민지 선생님 내일 오후 5시에 염색 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 5시"
    assert result["service_type"] == "염색"
    assert result["designer"] == "민지"


def test_extract_hair_salon_reservation_any_designer():
    result = extract_hair_salon_reservation_info(
        "내일 오후 4시에 커트 예약하고 싶은데 아무 선생님이나 괜찮아요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 4시"
    assert result["service_type"] == "커트"
    assert result["designer"] == "가능한 디자이너"


def test_extract_hair_salon_reservation_cut_alias():
    result = extract_hair_salon_reservation_info(
        "이번 주말 2시에 컷 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "이번 주말"
    assert result["time"] == "2시"
    assert result["service_type"] == "커트"


def test_extract_hair_salon_reservation_perm_alias():
    result = extract_hair_salon_reservation_info(
        "내일 오후 4시에 파마 예약하고 싶습니다."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 4시"
    assert result["service_type"] == "펌"


def test_extract_hair_salon_reservation_missing_service_type():
    result = extract_hair_salon_reservation_info(
        "내일 오후 3시에 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 3시"
    assert result["service_type"] is None


def test_extract_hair_salon_reservation_user_name_with_reserver_phrase():
    result = extract_hair_salon_reservation_info(
        "예약자는 홍길동입니다. 내일 오후 5시에 염색 예약하고 싶어요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 5시"
    assert result["service_type"] == "염색"
    assert result["user_name"] == "홍길동"
