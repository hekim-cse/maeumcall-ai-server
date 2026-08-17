from __future__ import annotations

from services.flow.service_workflow import (
    FieldContract,
    FieldOption,
    ServiceWorkflowSpec,
    build_service_workflow_contract,
)

PASSPORT_SPEC = ServiceWorkflowSpec(
    category="시청",
    title="여권 발급 문의",
    graph_name="cityhall_passport_guidance",
    intent="passport_guidance",
    collecting_state="collecting_passport_inquiry",
    confirming_state="confirming_passport_inquiry",
    ready_state="passport_guidance_ready",
    fields=(
        FieldContract(
            "application_type",
            "신청 유형",
            "최초 발급, 재발급, 긴급여권 중 문의할 신청 유형",
            "최초 발급, 재발급, 긴급여권 중 어떤 신청을 문의하시나요?",
            ("처음 발급받습니다.", "재발급을 문의합니다.", "긴급여권이 필요합니다."),
            (
                FieldOption("first_issue", "최초 발급"),
                FieldOption("reissue", "재발급"),
                FieldOption("emergency", "긴급여권"),
            ),
        ),
        FieldContract(
            "applicant_type",
            "신청인 구분",
            "성인 본인, 미성년자, 대리·법정대리인 중 신청인 조건",
            "신청 대상이 성인 본인인지, 미성년자인지 말씀해 주세요.",
            ("성인 본인입니다.", "미성년자 신청입니다.", "법정대리인이 신청합니다."),
            (
                FieldOption("adult_self", "성인 본인"),
                FieldOption("minor", "미성년자"),
                FieldOption("legal_representative", "법정대리인"),
            ),
        ),
        FieldContract(
            "inquiry_topic",
            "문의 항목",
            "구비서류, 수수료, 처리기간, 접수기관, 온라인 가능 여부 중 확인할 항목",
            "구비서류, 수수료, 처리기간, 접수기관 중 무엇을 확인하시겠습니까?",
            (
                "필요 서류가 궁금합니다.",
                "수수료와 처리기간이 궁금합니다.",
                "온라인 신청 가능 여부를 알고 싶어요.",
            ),
            (
                FieldOption("documents", "구비서류"),
                FieldOption("fee", "수수료"),
                FieldOption("processing_time", "처리기간"),
                FieldOption("office", "접수기관"),
                FieldOption("online_eligibility", "온라인 신청 가능 여부"),
            ),
        ),
        FieldContract(
            "application_channel",
            "희망 채널",
            "방문, 정부24 온라인, 재외공관 중 희망하는 신청 경로",
            "방문과 온라인 중 어느 신청 경로를 고려하고 계신가요?",
            (
                "시청에 방문할 예정입니다.",
                "정부24 온라인 신청을 원해요.",
                "재외공관을 이용할 예정입니다.",
            ),
            (
                FieldOption("in_person", "방문"),
                FieldOption("government24", "정부24 온라인"),
                FieldOption("overseas_mission", "재외공관"),
            ),
        ),
    ),
    confirmation_prefix="여권 발급 안내 조건을 정리했습니다.",
    ready_message=(
        "여권 문의 조건이 확인되었습니다. 구비서류·수수료·접수 가능 여부는 신청 유형과 "
        "신청 시점에 따라 달라질 수 있어 외교부 여권안내와 접수기관의 최신 기준을 조회한 뒤 안내해야 합니다."
    ),
    cancelled_message="여권 발급 안내 요청을 취소했습니다.",
    closing_message="확인했습니다. 실제 신청 전에는 외교부 여권안내와 방문할 접수기관의 최신 공지를 다시 확인해 주세요.",
    ready_replies=(
        "네, 최신 기준을 확인해 주세요.",
        "수정할 내용이 있습니다.",
        "문의는 여기까지 할게요.",
    ),
    branch_field="application_type",
    ready_messages_by_branch=(
        (
            "first_issue",
            "최초 여권 발급 안내에 필요한 조건이 확인되었습니다. 실제 구비서류·수수료·접수기관은 외교부와 해당 대행기관의 최신 기준을 조회한 뒤 안내해야 합니다.",
        ),
        (
            "reissue",
            "여권 재발급 안내에 필요한 조건이 확인되었습니다. 온라인 신청 가능 여부는 기존 발급 이력과 신청 사유 등 공식 자격 조건을 조회한 뒤 안내해야 합니다.",
        ),
        (
            "emergency",
            "긴급여권 안내에 필요한 조건이 확인되었습니다. 발급 대상·증빙서류·접수기관은 외교부의 최신 긴급여권 기준을 확인한 뒤 안내해야 합니다.",
        ),
    ),
)


RESIDENT_CERTIFICATE_SPEC = ServiceWorkflowSpec(
    category="시청",
    title="주민등록 등본 문의",
    graph_name="cityhall_resident_certificate_guidance",
    intent="resident_certificate_guidance",
    collecting_state="collecting_certificate_inquiry",
    confirming_state="confirming_certificate_inquiry",
    ready_state="certificate_guidance_ready",
    fields=(
        FieldContract(
            "document_type",
            "서류 종류",
            "주민등록표 등본 또는 초본 중 필요한 서류",
            "주민등록표 등본과 초본 중 어떤 서류가 필요하신가요?",
            ("등본이 필요합니다.", "초본이 필요합니다.", "두 서류의 차이가 궁금합니다."),
            (FieldOption("register_copy", "등본"), FieldOption("individual_extract", "초본")),
        ),
        FieldContract(
            "applicant_relation",
            "신청 관계",
            "본인, 같은 세대원, 대리인·이해관계인 중 신청자 관계",
            "본인 서류인지, 같은 세대원 또는 대리 신청인지 말씀해 주세요.",
            ("본인 서류입니다.", "같은 세대원 서류입니다.", "대리 신청입니다."),
            (
                FieldOption("self", "본인"),
                FieldOption("same_household", "같은 세대원"),
                FieldOption("representative", "대리인 또는 이해관계인"),
            ),
        ),
        FieldContract(
            "issuance_channel",
            "발급 채널",
            "정부24, 행정기관 방문, 무인민원발급기 중 희망 경로",
            "온라인, 방문, 무인민원발급기 중 어떤 방법을 원하시나요?",
            (
                "정부24에서 발급받고 싶어요.",
                "주민센터에 방문할게요.",
                "무인민원발급기를 이용할게요.",
            ),
            (
                FieldOption("government24", "정부24"),
                FieldOption("in_person", "행정기관 방문"),
                FieldOption("kiosk", "무인민원발급기"),
            ),
        ),
        FieldContract(
            "inquiry_topic",
            "문의 항목",
            "신청 자격, 준비물, 수수료, 출력·수령 방법 중 확인할 내용",
            "신청 자격, 준비물, 수수료, 수령 방법 중 무엇을 확인하시겠습니까?",
            ("준비물이 궁금합니다.", "수수료를 알고 싶어요.", "온라인 출력 방법이 궁금합니다."),
            (
                FieldOption("eligibility", "신청 자격"),
                FieldOption("documents", "준비물"),
                FieldOption("fee", "수수료"),
                FieldOption("delivery", "출력 또는 수령 방법"),
            ),
        ),
    ),
    confirmation_prefix="주민등록표 등·초본 안내 조건을 정리했습니다.",
    ready_message=(
        "등·초본 문의 조건이 확인되었습니다. 신청 관계와 발급 채널에 따라 자격·구비서류가 달라지므로 "
        "정부24 또는 관할 행정기관의 최신 기준을 조회한 뒤 안내해야 합니다."
    ),
    cancelled_message="주민등록표 등·초본 안내 요청을 취소했습니다.",
    closing_message="확인했습니다. 실제 발급 전에는 정부24 또는 관할 접수기관에서 신청 가능 여부를 최종 확인해 주세요.",
    ready_replies=(
        "네, 발급 기준을 확인해 주세요.",
        "수정할 내용이 있습니다.",
        "문의는 여기까지 할게요.",
    ),
    branch_field="issuance_channel",
    ready_messages_by_branch=(
        (
            "government24",
            "정부24 발급 안내에 필요한 조건이 확인되었습니다. 온라인 대리 신청 제한 등 신청 관계별 자격을 정부24 최신 기준으로 확인한 뒤 안내해야 합니다.",
        ),
        (
            "in_person",
            "방문 발급 안내에 필요한 조건이 확인되었습니다. 본인·대리인 관계에 맞는 신분증과 위임 서류를 관할 기관의 최신 기준으로 확인해야 합니다.",
        ),
        (
            "kiosk",
            "무인민원발급기 안내에 필요한 조건이 확인되었습니다. 설치 장소·운영시간·발급 가능 서류는 해당 기기의 최신 정보를 조회해야 합니다.",
        ),
    ),
)


BULKY_WASTE_SPEC = ServiceWorkflowSpec(
    category="시청",
    title="대형폐기물 배출",
    graph_name="cityhall_bulky_waste_guidance",
    intent="bulky_waste_guidance",
    collecting_state="collecting_bulky_waste",
    confirming_state="confirming_bulky_waste",
    ready_state="bulky_waste_guidance_ready",
    fields=(
        FieldContract(
            "region",
            "배출 지역",
            "수수료와 신고 채널을 결정할 시·군·구 및 읍·면·동",
            "대형폐기물을 배출할 시·군·구와 읍·면·동을 말씀해 주세요.",
            ("천안시 동남구입니다.", "천안시 서북구입니다."),
        ),
        FieldContract(
            "item_name",
            "배출 품목",
            "수수료 품목표와 대조할 구체적인 폐기물 이름과 크기",
            "배출할 품목의 이름과 대략적인 크기를 말씀해 주세요.",
            ("2인용 소파입니다.", "가로 120cm 책상입니다."),
        ),
        FieldContract(
            "quantity",
            "수량",
            "신고와 수수료 산정에 필요한 품목 수량",
            "배출할 수량은 몇 개인가요?",
            ("한 개입니다.", "두 개입니다."),
        ),
        FieldContract(
            "request_topic",
            "문의 항목",
            "신고 방법, 수수료, 배출 장소·일정, 수거 상태 중 확인할 내용",
            "신고 방법, 수수료, 배출 장소와 일정 중 무엇을 확인하시겠습니까?",
            (
                "온라인 신고 방법이 궁금합니다.",
                "수수료를 알고 싶어요.",
                "배출 장소와 일정을 알고 싶어요.",
            ),
            (
                FieldOption("application", "신고 방법"),
                FieldOption("fee", "수수료"),
                FieldOption("place_and_schedule", "배출 장소와 일정"),
                FieldOption("collection_status", "수거 상태"),
            ),
        ),
    ),
    confirmation_prefix="대형폐기물 안내 조건을 정리했습니다.",
    ready_message=(
        "배출 지역·품목·수량·문의 항목이 확인되었습니다. 실제 수수료와 배출 일정은 지자체별로 다르므로 "
        "해당 지역의 공식 신고 시스템과 최신 품목표를 조회한 뒤 안내해야 합니다."
    ),
    cancelled_message="대형폐기물 안내 요청을 취소했습니다. 실제 배출 신고는 생성되지 않았습니다.",
    closing_message="확인했습니다. 실제 배출 전에는 관할 지자체 신고 완료 여부와 필증 표시 방법을 다시 확인해 주세요.",
    ready_replies=(
        "네, 지역 기준을 조회해 주세요.",
        "수정할 내용이 있습니다.",
        "문의는 여기까지 할게요.",
    ),
    branch_field="request_topic",
    ready_messages_by_branch=(
        (
            "application",
            "대형폐기물 신고 방법 안내에 필요한 정보가 확인되었습니다. 관할 지자체의 공식 온라인·방문 신고 채널을 조회한 뒤 단계별로 안내해야 합니다.",
        ),
        (
            "fee",
            "대형폐기물 수수료 조회에 필요한 지역·품목·크기·수량이 확인되었습니다. 실제 금액은 관할 지자체 최신 품목표와 대조해야 합니다.",
        ),
        (
            "place_and_schedule",
            "대형폐기물 배출 장소·일정 안내에 필요한 정보가 확인되었습니다. 실제 배출 가능 위치와 수거일은 신고 시스템 또는 관할 부서에서 확인해야 합니다.",
        ),
        (
            "collection_status",
            "대형폐기물 수거 상태 문의에 필요한 정보가 확인되었습니다. 실제 상태는 접수번호가 연결된 지자체 수거 시스템에서 조회해야 합니다.",
        ),
    ),
)


CITYHALL_PASSPORT_CONTRACT = build_service_workflow_contract(PASSPORT_SPEC)
CITYHALL_RESIDENT_CERTIFICATE_CONTRACT = build_service_workflow_contract(RESIDENT_CERTIFICATE_SPEC)
CITYHALL_BULKY_WASTE_CONTRACT = build_service_workflow_contract(BULKY_WASTE_SPEC)

CITYHALL_CONTRACTS = (
    CITYHALL_PASSPORT_CONTRACT,
    CITYHALL_RESIDENT_CERTIFICATE_CONTRACT,
    CITYHALL_BULKY_WASTE_CONTRACT,
)
