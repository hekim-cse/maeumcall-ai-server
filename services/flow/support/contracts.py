from __future__ import annotations

from services.flow.service_workflow import (
    FieldContract,
    FieldOption,
    GuardContract,
    ServiceWorkflowSpec,
    build_service_workflow_contract,
)


NETWORK_CALL_SPEC = ServiceWorkflowSpec(
    category="고객센터",
    title="인터넷/통화 문제 문의",
    graph_name="support_network_call_issue",
    intent="network_call_issue",
    collecting_state="collecting_network_issue",
    confirming_state="confirming_network_issue",
    ready_state="network_diagnosis_ready",
    fields=(
        FieldContract(
            "service_type",
            "서비스 유형",
            "유선 인터넷, 와이파이, 이동통신 음성·데이터 중 장애 서비스",
            "문제가 발생한 서비스가 인터넷, 와이파이, 통화, 모바일 데이터 중 무엇인가요?",
            ("유선 인터넷 문제입니다.", "와이파이가 끊깁니다.", "통화 품질 문제입니다."),
            (
                FieldOption("wired_internet", "유선 인터넷"),
                FieldOption("wifi", "와이파이"),
                FieldOption("voice_call", "음성 통화"),
                FieldOption("mobile_data", "모바일 데이터"),
            ),
        ),
        FieldContract(
            "symptom",
            "증상",
            "끊김, 연결 불가, 속도 저하, 통화 품질 등 관찰한 현상",
            "발생한 증상을 구체적으로 말씀해 주세요.",
            ("연결이 반복해서 끊겨요.", "인터넷에 전혀 연결되지 않아요.", "통화 음성이 자주 끊겨요."),
        ),
        FieldContract(
            "occurred_at",
            "발생 시점",
            "최초 발생 시각과 지속·반복 여부",
            "문제가 언제 시작되었고 계속 발생하는지 말씀해 주세요.",
            ("오늘 오전부터 계속됩니다.", "일주일 전부터 간헐적으로 발생합니다."),
        ),
        FieldContract(
            "scope",
            "영향 범위",
            "한 기기, 여러 기기, 특정 장소, 모든 장소 중 장애 범위",
            "한 기기에서만 발생하나요, 여러 기기에서 동일하게 발생하나요?",
            ("한 기기에서만 발생해요.", "집의 모든 기기에서 발생해요.", "특정 장소에서만 발생해요."),
            (
                FieldOption("single_device", "한 기기"),
                FieldOption("multiple_devices", "여러 기기"),
                FieldOption("specific_location", "특정 장소"),
                FieldOption("all_locations", "모든 장소"),
            ),
        ),
        FieldContract(
            "troubleshooting_done",
            "이미 한 조치",
            "재부팅, 케이블 확인, 네트워크 재연결 등 이미 수행한 조치",
            "재부팅이나 케이블 확인 등 이미 시도한 조치가 있나요?",
            ("기기를 재부팅했습니다.", "케이블과 공유기를 확인했습니다.", "아직 시도한 조치는 없습니다."),
        ),
        FieldContract(
            "next_action",
            "희망 조치",
            "단계별 진단, 원격 점검, 상담원 연결, A/S 전환 중 다음 행동",
            "단계별 진단, 원격 점검, 상담원 연결 중 어떤 도움을 원하시나요?",
            ("단계별 진단을 진행할게요.", "원격 점검을 요청합니다.", "상담원 연결을 원해요."),
            (
                FieldOption("guided_diagnosis", "단계별 진단"),
                FieldOption("remote_check", "원격 점검"),
                FieldOption("agent_handoff", "상담원 연결"),
                FieldOption("service_request", "A/S 전환"),
            ),
        ),
    ),
    confirmation_prefix="통신 장애 진단 정보를 정리했습니다.",
    ready_message=(
        "증상·발생 시점·영향 범위·기존 조치가 확인되어 다음 진단을 선택할 준비가 되었습니다. "
        "회선 상태나 장애 원인은 실제 진단 시스템 조회 전에는 단정하지 않습니다."
    ),
    cancelled_message="통신 장애 진단 요청을 취소했습니다. 서비스 설정에는 변경이 없습니다.",
    closing_message="확인했습니다. 원격 점검이나 A/S가 필요하면 인증된 고객지원 시스템에서 이어서 진행해야 합니다.",
    ready_replies=("네, 다음 진단을 진행해 주세요.", "수정할 내용이 있습니다.", "상담원 연결을 원해요."),
    branch_field="next_action",
    ready_messages_by_branch=(
        ("guided_diagnosis", "단계별 진단에 필요한 증상과 기존 조치가 확인되었습니다. 다음 단계는 한 번에 하나씩 안내하고 각 결과를 확인한 뒤 진행해야 합니다."),
        ("remote_check", "원격 점검 요청에 필요한 정보가 확인되었습니다. 실제 회선·기기 상태는 본인 확인 후 진단 시스템에 연결해 조회해야 합니다."),
        ("agent_handoff", "상담원 이관에 필요한 장애 정보가 확인되었습니다. 실제 연결은 고객지원 시스템 연동 후 진행해야 합니다."),
        ("service_request", "A/S 전환 검토에 필요한 장애 정보가 확인되었습니다. 실제 접수는 기기·회선 확인과 사용자 최종 동의를 거쳐야 합니다."),
    ),
)


PLAN_CONTRACT_SPEC = ServiceWorkflowSpec(
    category="고객센터",
    title="요금/약정 상담",
    graph_name="support_plan_contract_consultation",
    intent="plan_contract_consultation",
    collecting_state="collecting_plan_contract",
    confirming_state="confirming_plan_contract",
    ready_state="plan_consultation_ready",
    fields=(
        FieldContract(
            "inquiry_type",
            "상담 유형",
            "청구 내역, 요금제 변경, 약정 만료, 할인 조건 중 상담 목적",
            "청구 내역, 요금제 변경, 약정 만료, 할인 중 어떤 상담을 원하시나요?",
            ("이번 달 청구 내역이 궁금합니다.", "요금제를 변경하고 싶어요.", "약정 만료일을 확인하고 싶어요."),
            (
                FieldOption("billing", "청구 내역"),
                FieldOption("plan_change", "요금제 변경"),
                FieldOption("contract_expiry", "약정 만료"),
                FieldOption("discount", "할인 조건"),
            ),
        ),
        FieldContract(
            "current_service",
            "현재 이용 정보",
            "현재 이용 중인 서비스와 알고 있는 요금제·약정 정보",
            "현재 이용 중인 서비스와 알고 계신 요금제 또는 약정 정보를 말씀해 주세요.",
            ("휴대폰 요금제를 이용 중입니다.", "인터넷 결합 상품을 이용 중입니다.", "현재 요금제 이름을 말씀드릴게요."),
        ),
        FieldContract(
            "consultation_goal",
            "상담 목표",
            "확인하거나 변경하려는 조건과 우선순위",
            "이번 상담에서 확인하거나 변경하려는 목표를 구체적으로 말씀해 주세요.",
            ("월 요금을 낮추고 싶어요.", "데이터 제공량을 늘리고 싶어요.", "위약금 여부를 확인하고 싶어요."),
        ),
        FieldContract(
            "consent_scope",
            "조회 동의 범위",
            "일반 상품 안내만 받을지 본인 확인 후 계정 정보를 조회할지",
            "일반 상품 안내만 원하시나요, 본인 확인 후 계정 조회까지 원하시나요?",
            ("일반 안내만 받을게요.", "본인 확인 후 제 정보를 조회해 주세요."),
            (
                FieldOption("general_guidance", "일반 상품 안내"),
                FieldOption("authenticated_lookup", "본인 확인 후 계정 조회"),
            ),
        ),
    ),
    confirmation_prefix="요금·약정 상담 조건을 정리했습니다.",
    ready_message=(
        "상담 목적과 현재 이용 정보가 확인되었습니다. 실제 청구액·약정·할인 자격은 "
        "본인 인증 후 고객 계정과 최신 상품 정책을 조회하기 전에는 확정하지 않습니다."
    ),
    cancelled_message="요금·약정 상담 요청을 취소했습니다. 계정이나 상품에는 변경이 없습니다.",
    closing_message="확인했습니다. 계정 조회나 상품 변경은 인증된 고객지원 시스템에서 별도 동의를 받아 진행해야 합니다.",
    ready_replies=("네, 상담을 진행해 주세요.", "수정할 내용이 있습니다.", "상담은 여기까지 할게요."),
    branch_field="inquiry_type",
    ready_messages_by_branch=(
        ("billing", "청구 내역 문의 조건이 확인되었습니다. 실제 청구 항목은 본인 인증 후 고객 계정과 청구 시스템을 조회해야 합니다."),
        ("plan_change", "요금제 변경 상담 조건이 확인되었습니다. 실제 변경 가능 상품·적용일·요금은 최신 상품 정책 조회와 사용자 최종 동의 후 확정해야 합니다."),
        ("contract_expiry", "약정 만료 문의 조건이 확인되었습니다. 실제 만료일과 위약금은 본인 인증 후 계약 시스템을 조회해야 합니다."),
        ("discount", "할인 상담 조건이 확인되었습니다. 실제 적용 자격과 중복 가능 여부는 최신 정책 및 고객 계약 조회 후 안내해야 합니다."),
    ),
)


SERVICE_REQUEST_SPEC = ServiceWorkflowSpec(
    category="고객센터",
    title="A/S 접수",
    graph_name="support_service_request",
    intent="service_request",
    collecting_state="collecting_service_request",
    confirming_state="confirming_service_request",
    ready_state="service_request_ready",
    fields=(
        FieldContract(
            "product_type",
            "제품 유형",
            "휴대폰, 인터넷 장비, 가전 등 A/S 대상 제품군",
            "A/S가 필요한 제품 유형을 말씀해 주세요.",
            ("휴대폰입니다.", "인터넷 공유기입니다.", "가전제품입니다."),
        ),
        FieldContract(
            "model_name",
            "모델명",
            "대상 제품을 식별할 수 있는 정확한 모델명",
            "제품의 모델명을 말씀해 주세요.",
            ("제품 라벨의 모델명을 말씀드릴게요.", "설정 화면에서 확인하겠습니다."),
        ),
        FieldContract(
            "symptom",
            "고장 증상",
            "재현 조건과 오류 표시를 포함한 관찰된 증상",
            "고장 증상과 재현되는 상황을 구체적으로 말씀해 주세요.",
            ("전원이 켜지지 않아요.", "사용 중 반복해서 꺼져요.", "오류 코드가 표시됩니다."),
        ),
        FieldContract(
            "occurred_at",
            "발생 시점",
            "증상이 처음 발생한 시점과 반복 여부",
            "증상이 언제 시작되었고 계속 재현되는지 말씀해 주세요.",
            ("오늘부터 계속 발생합니다.", "일주일 전부터 간헐적으로 발생합니다."),
        ),
        FieldContract(
            "safety_status",
            "안전 이상 여부",
            "발열, 연기, 냄새, 배터리 팽창 등 즉시 사용 중지가 필요한 징후",
            "발열, 연기, 타는 냄새, 배터리 팽창 같은 안전 이상이 있나요?",
            ("안전 이상은 없습니다.", "기기가 심하게 뜨거워집니다.", "배터리가 부풀었습니다."),
            (
                FieldOption("no_safety_issue", "안전 이상 없음"),
                FieldOption("safety_issue", "안전 이상 있음"),
            ),
        ),
        FieldContract(
            "service_channel",
            "희망 접수 방식",
            "방문, 택배, 출장, 상담원 검토 중 희망하는 서비스 방식",
            "방문, 택배, 출장 중 어떤 접수 방식을 원하시나요?",
            ("서비스센터 방문을 원해요.", "택배 접수를 원해요.", "출장 서비스를 원해요."),
            (
                FieldOption("visit", "서비스센터 방문"),
                FieldOption("parcel", "택배 접수"),
                FieldOption("onsite", "출장 서비스"),
                FieldOption("agent_review", "상담원 검토"),
            ),
        ),
        FieldContract(
            "preferred_schedule",
            "희망 일정",
            "방문·출장·수거를 희망하는 날짜와 시간대",
            "접수 가능한 경우 희망하는 날짜와 시간대를 말씀해 주세요.",
            ("이번 주 금요일 오후를 원해요.", "다음 주 월요일 오전이 좋아요."),
        ),
    ),
    confirmation_prefix="A/S 접수 요청 정보를 정리했습니다.",
    ready_message=(
        "제품·증상·안전 상태·희망 접수 방식이 확인되어 접수 요청을 전달할 준비가 되었습니다. "
        "실제 접수번호·예약 일정·비용은 서비스 시스템 확인 전에는 생성하거나 확정하지 않습니다."
    ),
    cancelled_message="A/S 접수 요청을 취소했습니다. 실제 서비스 접수는 생성되지 않았습니다.",
    closing_message="확인했습니다. 실제 접수는 본인 확인과 서비스 가능 일정 조회 후 최종 동의를 받아 진행해야 합니다.",
    ready_replies=("네, 실제 접수를 진행해 주세요.", "수정할 내용이 있습니다.", "접수를 취소할게요."),
    branch_field="service_channel",
    ready_messages_by_branch=(
        ("visit", "서비스센터 방문 접수에 필요한 정보와 희망 일정이 확인되었습니다. 실제 센터·가능 시간·접수번호는 서비스 시스템 조회 후 확정해야 합니다."),
        ("parcel", "택배 A/S 접수에 필요한 정보와 희망 일정이 확인되었습니다. 실제 수거 가능 지역·포장 기준·접수번호는 서비스 시스템 확인 후 안내해야 합니다."),
        ("onsite", "출장 A/S 접수에 필요한 정보와 희망 일정이 확인되었습니다. 실제 출장 가능 지역·시간·비용은 서비스 시스템 조회 후 확정해야 합니다."),
        ("agent_review", "A/S 상담원 검토에 필요한 제품·증상 정보가 확인되었습니다. 실제 이관과 접수는 고객지원 시스템 연동 후 진행해야 합니다."),
    ),
    guards=(
        GuardContract(
            field_key="safety_status",
            value="safety_issue",
            state="safety_action_required",
            message=(
                "안전 이상이 확인되었습니다. 기기 사용과 충전 또는 전원 연결을 즉시 중지하고, "
                "연기나 화재 위험이 있으면 안전한 거리로 이동한 뒤 긴급기관에 연락해 주세요. "
                "안전이 확보되기 전에는 일반 진단이나 접수 절차를 계속하지 않습니다."
            ),
            replies=("기기 사용을 중지했습니다.", "안전한 장소로 이동했습니다.", "통화를 마치겠습니다."),
        ),
    ),
)


SUPPORT_NETWORK_CALL_CONTRACT = build_service_workflow_contract(NETWORK_CALL_SPEC)
SUPPORT_PLAN_CONTRACT = build_service_workflow_contract(PLAN_CONTRACT_SPEC)
SUPPORT_SERVICE_REQUEST_CONTRACT = build_service_workflow_contract(SERVICE_REQUEST_SPEC)

SUPPORT_CONTRACTS = (
    SUPPORT_NETWORK_CALL_CONTRACT,
    SUPPORT_PLAN_CONTRACT,
    SUPPORT_SERVICE_REQUEST_CONTRACT,
)
