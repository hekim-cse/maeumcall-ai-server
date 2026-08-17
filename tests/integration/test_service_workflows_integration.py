from __future__ import annotations

import pytest

from services.flow.cityhall.contracts import (
    BULKY_WASTE_SPEC,
    CITYHALL_BULKY_WASTE_CONTRACT,
    CITYHALL_PASSPORT_CONTRACT,
    CITYHALL_RESIDENT_CERTIFICATE_CONTRACT,
    PASSPORT_SPEC,
    RESIDENT_CERTIFICATE_SPEC,
)
from services.flow.delivery.contracts import (
    DELIVERY_DELAY_CONTRACT,
    DELIVERY_DELAY_SPEC,
    DELIVERY_ORDER_CHANGE_CONTRACT,
    DELIVERY_REFUND_REDELIVERY_CONTRACT,
    ORDER_CHANGE_SPEC,
    REFUND_REDELIVERY_SPEC,
)
from services.flow.support.contracts import (
    NETWORK_CALL_SPEC,
    PLAN_CONTRACT_SPEC,
    SERVICE_REQUEST_SPEC,
    SUPPORT_NETWORK_CALL_CONTRACT,
    SUPPORT_PLAN_CONTRACT,
    SUPPORT_SERVICE_REQUEST_CONTRACT,
)


pytestmark = pytest.mark.integration


CASES = (
    (
        ORDER_CHANGE_SPEC,
        DELIVERY_ORDER_CHANGE_CONTRACT,
        "주문번호 MC-1001이고 배송 주소를 천안시 서북구 새 주소로 변경하고 싶습니다. 변경할 수 없으면 취소 가능 여부를 확인해 주세요.",
    ),
    (
        DELIVERY_DELAY_SPEC,
        DELIVERY_DELAY_CONTRACT,
        "주문번호 MC-1002인데 예정 시간을 30분 넘겼습니다. 예상 도착 시간을 확인하고, 더 늦으면 상담원 연결을 원합니다.",
    ),
    (
        REFUND_REDELIVERY_SPEC,
        DELIVERY_REFUND_REDELIVERY_CONTRACT,
        "주문번호 MC-1003에서 주문한 메뉴 대신 다른 메뉴가 왔고 사진이 있습니다. 재배달을 원합니다.",
    ),
    (
        PASSPORT_SPEC,
        CITYHALL_PASSPORT_CONTRACT,
        "성인 본인의 최초 여권 발급이고 시청에 방문할 예정입니다. 필요한 서류를 문의합니다.",
    ),
    (
        RESIDENT_CERTIFICATE_SPEC,
        CITYHALL_RESIDENT_CERTIFICATE_CONTRACT,
        "본인 주민등록표 등본을 정부24에서 발급할 때 필요한 준비물을 문의합니다.",
    ),
    (
        BULKY_WASTE_SPEC,
        CITYHALL_BULKY_WASTE_CONTRACT,
        "천안시 서북구에서 2인용 소파 한 개를 버리려고 합니다. 온라인 신고 방법을 알려주세요.",
    ),
    (
        NETWORK_CALL_SPEC,
        SUPPORT_NETWORK_CALL_CONTRACT,
        "유선 인터넷이 오늘 오전부터 집의 모든 기기에서 끊깁니다. 공유기 재부팅과 케이블 확인을 했고 원격 점검을 원합니다.",
    ),
    (
        PLAN_CONTRACT_SPEC,
        SUPPORT_PLAN_CONTRACT,
        "휴대폰 요금제를 이용 중이고 월 요금을 낮추려고 요금제 변경 상담을 원합니다. 본인 확인 후 계정 조회까지 동의합니다.",
    ),
    (
        SERVICE_REQUEST_SPEC,
        SUPPORT_SERVICE_REQUEST_CONTRACT,
        "휴대폰 모델 MC-Phone 1이 오늘부터 사용 중 반복해서 꺼집니다. 발열이나 배터리 팽창은 없고 이번 주 금요일 오후 서비스센터 방문을 원합니다.",
    ),
)


@pytest.mark.parametrize(
    "spec,contract,user_message",
    CASES,
    ids=[spec.graph_name for spec, _, _ in CASES],
)
def test_service_workflow_real_model_extracts_required_fields(
    spec,
    contract,
    user_message,
):
    result = contract.graph.invoke(
        {
            "user_message": user_message,
            "conversation_state": "greeting",
            "intent": spec.intent,
            "fields": {key: None for key in spec.field_keys},
            "workflow_status": "in_progress",
            "history": [],
            "recommended_replies": [],
            "should_end_call": False,
        }
    )

    assert result["conversation_state"] == spec.confirming_state
    assert result["missing_fields"] == []
    assert all(result["fields"].get(key) for key in spec.field_keys)
    assert result.get("ai_message")
