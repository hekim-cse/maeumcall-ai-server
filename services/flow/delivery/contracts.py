from __future__ import annotations

from services.flow.service_workflow import (
    FieldContract,
    FieldOption,
    ServiceWorkflowSpec,
    build_service_workflow_contract,
)


ORDER_CHANGE_SPEC = ServiceWorkflowSpec(
    category="배달",
    title="주문 변경",
    graph_name="delivery_order_change",
    intent="delivery_order_change",
    collecting_state="collecting_order_change",
    confirming_state="confirming_order_change",
    ready_state="order_change_request_ready",
    fields=(
        FieldContract(
            "order_number",
            "주문번호",
            "변경 대상 주문을 식별할 수 있는 주문번호",
            "변경할 주문의 주문번호를 말씀해 주세요.",
            ("주문번호를 말씀드릴게요.", "주문내역에서 확인하겠습니다."),
        ),
        FieldContract(
            "change_type",
            "변경 항목",
            "주소, 메뉴·수량, 옵션, 연락처 중 변경하려는 항목",
            "어떤 주문 정보를 변경하시겠습니까?",
            ("배송 주소를 변경하고 싶어요.", "메뉴 옵션을 변경하고 싶어요.", "연락처를 변경하고 싶어요."),
            (
                FieldOption("delivery_address", "배송 주소"),
                FieldOption("menu_or_quantity", "메뉴 또는 수량"),
                FieldOption("menu_option", "메뉴 옵션"),
                FieldOption("contact", "수령 연락처"),
            ),
        ),
        FieldContract(
            "requested_change",
            "변경 내용",
            "기존 값과 구분되는 구체적인 변경 요청",
            "변경하려는 내용을 구체적으로 말씀해 주세요.",
            ("새 배송 주소를 말씀드릴게요.", "변경할 메뉴와 수량을 말씀드릴게요."),
        ),
        FieldContract(
            "unavailable_preference",
            "변경 불가 시 처리",
            "가게 접수 또는 조리 진행으로 변경할 수 없을 때 원하는 후속 처리",
            "이미 처리가 시작되어 변경할 수 없다면 어떻게 안내받기를 원하시나요?",
            ("취소 가능 여부를 확인해 주세요.", "현재 주문을 그대로 진행할게요.", "상담원 연결을 원해요."),
            (
                FieldOption("check_cancellation", "취소 가능 여부 확인"),
                FieldOption("keep_order", "기존 주문 유지"),
                FieldOption("agent_handoff", "상담원 연결"),
            ),
        ),
    ),
    confirmation_prefix="주문 변경 요청을 정리했습니다.",
    ready_message=(
        "변경 요청 정보와 최종 확인이 완료되었습니다. 실제 변경 가능 여부는 주문 시스템의 "
        "접수·조리 상태를 조회한 뒤 확정해야 하며, 현재 통화에서는 변경 완료로 처리하지 않습니다."
    ),
    cancelled_message="주문 변경 요청을 취소했습니다. 실제 주문 상태에는 변경이 없습니다.",
    closing_message="확인했습니다. 주문 상태 조회나 실제 변경 처리가 필요하면 연결된 주문 시스템에서 이어서 진행해야 합니다.",
    ready_replies=("네, 확인했습니다.", "변경 가능 여부를 조회해 주세요.", "수정할 내용이 있습니다."),
    branch_field="unavailable_preference",
    ready_messages_by_branch=(
        (
            "check_cancellation",
            "주문 변경 정보와 변경 불가 시 취소 가능 여부 확인 요청까지 준비되었습니다. 실제 변경·취소 여부는 주문 시스템의 현재 상태를 조회한 뒤 확정해야 합니다.",
        ),
        (
            "agent_handoff",
            "주문 변경 정보와 상담원 연결 요청이 준비되었습니다. 실제 상담원 연결이나 주문 변경 완료는 외부 주문 시스템 연동 후 처리해야 합니다.",
        ),
    ),
)


DELIVERY_DELAY_SPEC = ServiceWorkflowSpec(
    category="배달",
    title="배달 지연 문의",
    graph_name="delivery_delay_inquiry",
    intent="delivery_delay_inquiry",
    collecting_state="collecting_delay_inquiry",
    confirming_state="confirming_delay_inquiry",
    ready_state="delay_inquiry_ready",
    fields=(
        FieldContract(
            "order_number",
            "주문번호",
            "지연 상태를 조회할 주문번호",
            "지연된 주문의 주문번호를 말씀해 주세요.",
            ("주문번호를 말씀드릴게요.", "주문내역에서 확인하겠습니다."),
        ),
        FieldContract(
            "delay_detail",
            "지연 상황",
            "표시된 예정 시간, 현재 경과 시간 등 사용자가 확인한 사실",
            "앱에 표시된 예정 시간과 현재 지연 상황을 말씀해 주세요.",
            ("예정 시간을 30분 넘겼어요.", "배달 준비 중에서 바뀌지 않아요."),
        ),
        FieldContract(
            "inquiry_goal",
            "확인할 내용",
            "현재 위치, 예상 도착 시간, 지연 사유 중 확인하려는 내용",
            "어떤 내용을 우선 확인해드릴까요?",
            ("예상 도착 시간을 알고 싶어요.", "현재 배달 위치를 확인해 주세요.", "지연 사유를 알고 싶어요."),
            (
                FieldOption("estimated_arrival", "예상 도착 시간"),
                FieldOption("delivery_location", "현재 배달 위치"),
                FieldOption("delay_reason", "지연 사유"),
            ),
        ),
        FieldContract(
            "delay_resolution",
            "지연 지속 시 처리",
            "추가 대기, 취소 가능 여부 확인, 상담원 연결 중 원하는 후속 행동",
            "지연이 계속될 경우 어떤 처리를 원하시나요?",
            ("조금 더 기다릴게요.", "취소 가능 여부를 확인해 주세요.", "상담원 연결을 원해요."),
            (
                FieldOption("wait", "추가 대기"),
                FieldOption("check_cancellation", "취소 가능 여부 확인"),
                FieldOption("agent_handoff", "상담원 연결"),
            ),
        ),
    ),
    confirmation_prefix="배달 지연 조회 요청을 정리했습니다.",
    ready_message=(
        "지연 문의에 필요한 정보가 확인되었습니다. 실제 위치·도착 예정 시간·지연 사유는 "
        "주문 및 배달 추적 시스템을 조회해야 하므로 현재 통화에서 임의로 안내하지 않습니다."
    ),
    cancelled_message="배달 지연 조회 요청을 취소했습니다. 주문 상태에는 변경이 없습니다.",
    closing_message="확인했습니다. 최신 배달 상태는 연결된 주문·배달 추적 시스템에서 이어서 확인해야 합니다.",
    ready_replies=("네, 조회를 진행해 주세요.", "수정할 내용이 있습니다.", "상담원 연결이 필요해요."),
    branch_field="delay_resolution",
    ready_messages_by_branch=(
        (
            "check_cancellation",
            "배달 지연 정보와 취소 가능 여부 확인 요청이 준비되었습니다. 실제 취소 가능 여부는 주문·배달 상태 조회 후 확정해야 합니다.",
        ),
        (
            "agent_handoff",
            "배달 지연 정보와 상담원 연결 요청이 준비되었습니다. 실제 연결 및 후속 처리는 고객지원 시스템 연동 후 진행해야 합니다.",
        ),
    ),
)


REFUND_REDELIVERY_SPEC = ServiceWorkflowSpec(
    category="배달",
    title="환불/재배달 문의",
    graph_name="delivery_refund_redelivery",
    intent="delivery_refund_redelivery",
    collecting_state="collecting_refund_redelivery",
    confirming_state="confirming_refund_redelivery",
    ready_state="refund_redelivery_request_ready",
    fields=(
        FieldContract(
            "order_number",
            "주문번호",
            "문제가 발생한 주문의 주문번호",
            "문제가 발생한 주문의 주문번호를 말씀해 주세요.",
            ("주문번호를 말씀드릴게요.", "주문내역에서 확인하겠습니다."),
        ),
        FieldContract(
            "issue_type",
            "문제 유형",
            "오배송, 누락, 파손·품질, 미수령 중 해당 문제",
            "어떤 문제가 발생했는지 유형을 말씀해 주세요.",
            ("다른 메뉴가 왔어요.", "일부 메뉴가 누락됐어요.", "음식 상태에 문제가 있어요."),
            (
                FieldOption("wrong_item", "오배송"),
                FieldOption("missing_item", "상품 누락"),
                FieldOption("damaged_or_quality", "파손 또는 품질 문제"),
                FieldOption("not_received", "미수령"),
            ),
        ),
        FieldContract(
            "issue_detail",
            "문제 상세",
            "주문 내용과 실제 수령 상태의 차이를 확인할 수 있는 구체적 설명",
            "주문 내용과 실제 받은 상태가 어떻게 다른지 구체적으로 말씀해 주세요.",
            ("주문한 메뉴 대신 다른 메뉴가 왔어요.", "음료 한 개가 빠졌어요."),
        ),
        FieldContract(
            "evidence_status",
            "확인 자료",
            "사진 또는 포장·영수증 등 확인 자료를 제공할 수 있는지 여부",
            "문제 상태를 확인할 사진이나 포장 자료가 있나요?",
            ("사진이 있습니다.", "포장과 영수증이 있습니다.", "확인 자료는 없습니다."),
            (
                FieldOption("available", "확인 자료 있음"),
                FieldOption("unavailable", "확인 자료 없음"),
            ),
        ),
        FieldContract(
            "resolution_preference",
            "희망 처리",
            "환불, 재배달, 상담원 검토 중 사용자가 원하는 처리",
            "환불과 재배달 중 어떤 처리를 원하시나요?",
            ("환불을 원합니다.", "재배달을 부탁드려요.", "상담원 검토를 원해요."),
            (
                FieldOption("refund", "환불"),
                FieldOption("redelivery", "재배달"),
                FieldOption("agent_review", "상담원 검토"),
            ),
        ),
    ),
    confirmation_prefix="환불·재배달 검토 요청을 정리했습니다.",
    ready_message=(
        "문제 내용과 희망 처리가 확인되어 검토 요청을 전달할 준비가 되었습니다. "
        "환불·재배달 승인이나 완료는 주문·결제 시스템의 확인 전에는 확정하지 않습니다."
    ),
    cancelled_message="환불·재배달 검토 요청을 취소했습니다. 실제 주문이나 결제 상태에는 변경이 없습니다.",
    closing_message="확인했습니다. 실제 승인과 처리는 연결된 주문·결제 시스템에서 이어서 진행해야 합니다.",
    ready_replies=("네, 검토를 진행해 주세요.", "수정할 내용이 있습니다.", "처리를 취소할게요."),
    branch_field="resolution_preference",
    ready_messages_by_branch=(
        ("refund", "환불 검토에 필요한 정보와 사용자 확인이 완료되었습니다. 실제 환불 승인·결제 취소는 주문 및 결제 시스템 검증 후 처리해야 합니다."),
        ("redelivery", "재배달 검토에 필요한 정보와 사용자 확인이 완료되었습니다. 실제 재배달 가능 여부와 접수 결과는 매장·주문 시스템 확인 후 확정해야 합니다."),
        ("agent_review", "상담원 검토에 필요한 정보와 사용자 확인이 완료되었습니다. 실제 상담 이관은 고객지원 시스템 연동 후 진행해야 합니다."),
    ),
)


DELIVERY_ORDER_CHANGE_CONTRACT = build_service_workflow_contract(ORDER_CHANGE_SPEC)
DELIVERY_DELAY_CONTRACT = build_service_workflow_contract(DELIVERY_DELAY_SPEC)
DELIVERY_REFUND_REDELIVERY_CONTRACT = build_service_workflow_contract(REFUND_REDELIVERY_SPEC)

DELIVERY_CONTRACTS = (
    DELIVERY_ORDER_CHANGE_CONTRACT,
    DELIVERY_DELAY_CONTRACT,
    DELIVERY_REFUND_REDELIVERY_CONTRACT,
)
