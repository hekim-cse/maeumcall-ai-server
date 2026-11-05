"""Two independent prompt candidates for reviewed development contrasts."""

POLICY_BY_GROUP = {
    "workflow_field_presence": (
        "추가 기준: 이번 발화에서 새로 확인되는 업무 필드 값을 먼저 추출하세요. "
        "질문형이어도 발화에 명시된 사실은 필드에 넣습니다. 새 비공란 필드가 "
        "하나라도 있을 때만 provide_details를 선택하고 그 필드를 함께 반환하세요. "
        "새 필드가 하나도 없으면 unknown과 모든 필드 null을 반환하세요. "
        "사용자가 말하지 않은 값은 추측하지 마세요."
    ),
    "date_normalization": (
        "추가 기준: date에는 발화에 지정된 단일 날짜 또는 반복 요일의 의미와 "
        "명시된 연도를 보존하세요. 날짜를 정하지 않았다고 하면 date=null입니다. "
        "시작 시각과 이용 시간은 날짜와 독립적으로 추출하세요. "
        "반복 예약이 가능하거나 완료됐다고 가정하지 마세요."
    ),
}
