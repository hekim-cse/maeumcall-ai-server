from services.flow.reservation.restaurant.extractor import (
    extract_restaurant_reservation_info,
)


def test_extract_restaurant_reservation_full_info():
    result = extract_restaurant_reservation_info(
        "오늘 저녁 7시에 두 명 예약할 수 있나요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 7시"
    assert result["party_size"] == "2명"


def test_extract_restaurant_reservation_tomorrow_evening():
    result = extract_restaurant_reservation_info(
        "내일 오후 6시 반에 4명 예약하고 싶습니다."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 6시 반"
    assert result["party_size"] == "4명"


def test_extract_restaurant_reservation_weekend():
    result = extract_restaurant_reservation_info(
        "이번 주말 7시에 네 명 자리 있을까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "이번 주말"
    assert result["time"] == "7시"
    assert result["party_size"] == "4명"


def test_extract_restaurant_reservation_missing_party_size():
    result = extract_restaurant_reservation_info(
        "오늘 저녁 7시에 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 7시"
    assert result["party_size"] is None


def test_extract_restaurant_reservation_with_user_name():
    result = extract_restaurant_reservation_info(
        "오늘 저녁 7시에 두 명 김개굴 이름으로 예약해주세요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 7시"
    assert result["party_size"] == "2명"
    assert result["user_name"] == "김개굴"


def test_extract_restaurant_reservation_user_name_with_reserver_phrase():
    result = extract_restaurant_reservation_info(
        "예약자는 홍길동입니다. 내일 오후 6시에 4명 예약하고 싶어요."
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "내일"
    assert result["time"] == "오후 6시"
    assert result["party_size"] == "4명"
    assert result["user_name"] == "홍길동"


def test_extract_restaurant_reservation_missing_user_name():
    result = extract_restaurant_reservation_info(
        "오늘 저녁 7시에 두 명 예약 가능할까요?"
    )

    assert result["intent"] == "reservation"
    assert result["date"] == "오늘"
    assert result["time"] == "저녁 7시"
    assert result["party_size"] == "2명"
    assert result["user_name"] is None
