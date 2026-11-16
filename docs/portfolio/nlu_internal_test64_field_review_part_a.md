# 내부 test 64건 전체 필드 검토 초안 A: IT01–IT32

> **AI 작성·사용자 1인 전체 필드 검수 완료, 모델 미실행.** 사용자는 [문장·상태·업무 방향](nlu_internal_test64_draft_part_a.md)과 아래 행동 코드·값·공란을 채택했다. IT05·IT17·IT27 교체 문장과 대응 필드도 별도로 채택했다. 데이터 계약·노출 검증과 평가 입력 동결은 아직 남아 있다. 모든 이름, 주문번호, 모델명은 가상이다.

## 읽는 방법

- 각 표의 `fields`에는 해당 업무의 **전체 키**가 있다. `null`은 이번 발화에서 새 값을 말하지 않았다는 뜻이다. `["…"]`는 사용자가 채택한 정규화 값의 `accepted_values` 한 가지다. 다른 표현은 임의로 추가하지 않는다.
- `current_fields`는 모델 입력의 이전 수집값이다. 고객센터·배달의 `greeting`은 해당 업무 전체 키가 `null`, 후속 상태는 행에 적힌 키 외 모두 `null`이다. 교수님 분석기의 모든 상태는 `{}`다. 직전 질문 문장은 모델 입력에 포함되지 않는다.
- 모든 행의 `change_field=null`, `offered_alternative_times=[]`다. `unknown` 행은 시나리오 intent를 유지하되, 이번 발화의 모든 업무 필드를 `null`로 제안한다. 기존 `current_fields`를 없애거나 덮어쓴다는 뜻은 아니다.
- 아래 `greeting` 행의 `current_fields=전부 null`, 후속 교수님 행의 `current_fields={}`라는 축약 표기가 실행 데이터를 만들 때도 그대로 보존되어야 한다.

## 고객센터: A/S 접수

`intent=service_request`; 전체 필드: `product_type`, `model_name`, `symptom`, `occurred_at`, `safety_status`, `service_channel`, `preferred_schedule`.

| ID | 상태 / current_fields | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT01 | `greeting` / 전부 null | `provide_details` | `product_type=["전기오븐"]; model_name=null; symptom=["예열을 시작하면 내부 팬이 멈추고 E7 오류가 뜸"]; occurred_at=null; safety_status=null; service_channel=null; preferred_schedule=null` | 고장·접수 요청. `예열을 시작하면`은 재현 조건이지 최초 발생 시점이 아니다. 점검 접수는 특정 방문/택배 방식이 아니다. |
| IT02 | `greeting` / 전부 null | `unknown` | `product_type=null; model_name=null; symptom=null; occurred_at=null; safety_status=null; service_channel=null; preferred_schedule=null` | 자동 세척 사용법 문의만 있다. 제품명 `오븐`을 업무 안 고장 필드로 전용하지 않는다. |
| IT03 | `collecting_service_request` / `product_type=의류건조기`, 나머지 null | `provide_details` | `product_type=null; model_name=["DR-520"]; symptom=["건조가 끝나도 문 잠금이 풀리지 않고 E3이 표시됨"]; occurred_at=null; safety_status=null; service_channel=null; preferred_schedule=null` | 모델명·새 고장 증상. 이전 제품군을 다시 출력하지 않는다. 문 잠금만으로 안전 이상을 확정하지 않는다. |
| IT04 | `collecting_service_request` / `product_type=공기청정기`, 나머지 null | `unknown` | `product_type=null; model_name=null; symptom=null; occurred_at=null; safety_status=null; service_channel=null; preferred_schedule=null` | 취침 모드 예약 방법은 현재 고장 접수 범위 밖. 기존 제품군은 입력 맥락에만 남긴다. |

## 고객센터: 요금/약정 상담

`intent=plan_contract_consultation`; 전체 필드: `inquiry_type`, `current_service`, `consultation_goal`, `consent_scope`.

| ID | 상태 / current_fields | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT05 | `greeting` / 전부 null | `provide_details` | `inquiry_type=["discount"]; current_service=null; consultation_goal=["새 가족 결합에 적용 가능한 할인 조건 확인"]; consent_scope=null` | 새 가족 결합의 할인 적용 조건 상담이다. 실제 계정 조회에 대한 명시적 동의는 없다. |
| IT06 | `greeting` / 전부 null | `unknown` | `inquiry_type=null; current_service=null; consultation_goal=null; consent_scope=null` | 신규 eSIM 회선 개통 절차 문의. |
| IT07 | `collecting_plan_contract` / `inquiry_type=plan_change`, `current_service=5G 기본 요금제`, 나머지 null | `provide_details` | `inquiry_type=null; current_service=null; consultation_goal=["매달 데이터가 절반 넘게 남아 월 요금을 낮출 수 있는 요금제 검토"]; consent_scope=null` | 변경 상담의 우선순위를 새로 제공한다. 새 요금제 이름이나 동의 범위는 말하지 않았다. |
| IT08 | `collecting_plan_contract` / `inquiry_type=billing`, `current_service=휴대전화`, 나머지 null | `unknown` | `inquiry_type=null; current_service=null; consultation_goal=null; consent_scope=null` | 액정 수리 예약은 요금/약정 상담 범위 밖이다. |

## 고객센터: 인터넷/통화 문제 문의

`intent=network_call_issue`; 전체 필드: `service_type`, `symptom`, `occurred_at`, `scope`, `troubleshooting_done`, `next_action`.

| ID | 상태 / current_fields | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT09 | `greeting` / 전부 null | `provide_details` | `service_type=["wired_internet"]; symptom=["영상회의 중 몇 분마다 연결이 끊기고 모뎀 인터넷 표시등이 빨간색으로 바뀜"]; occurred_at=null; scope=null; troubleshooting_done=null; next_action=["remote_check"]` | 유선 장애와 원격 점검 희망. `집에서`만으로 특정 장소에만 발생한다고 단정하지 않는다. |
| IT10 | `greeting` / 전부 null | `unknown` | `service_type=null; symptom=null; occurred_at=null; scope=null; troubleshooting_done=null; next_action=null` | WPS 연결 순서는 장애 점검이 아닌 사용법이다. |
| IT11 | `collecting_network_issue` / `service_type=voice_call`, `symptom=통화 음성이 끊김`, 나머지 null | `provide_details` | `service_type=null; symptom=null; occurred_at=["2026년 11월 11일 밤부터"]; scope=["specific_location"]; troubleshooting_done=null; next_action=null` | 발생 시점과 `집 안에서만`이라는 장소 제한을 새로 제공한다. `밖에서는 잘 됨`은 해당 제한의 근거다. |
| IT12 | `collecting_network_issue` / `service_type=wifi`, `symptom=접속 불가`, 나머지 null | `unknown` | `service_type=null; symptom=null; occurred_at=null; scope=null; troubleshooting_done=null; next_action=null` | 로밍 요금은 현재 장애 상담 범위 밖이다. |

## 교수님: 결석 사유 전달

`intent=absence_notice`; 전체 필드: `class_name`, `absence_date`, `absence_reason`, `user_name`. 모든 행의 `current_fields={}`.

| ID | 상태 | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT13 | `greeting` | `provide_absence_info` | `class_name=["자료구조 수업"]; absence_date=["2026년 11월 10일"]; absence_reason=["수업에 가던 열차 운행 중단"]; user_name=["최유진"]` | 결석 사실, 수업, 날짜, 사유와 이름이 명시됐다. |
| IT14 | `greeting` | `unknown` | `class_name=null; absence_date=null; absence_reason=null; user_name=null` | 다음 학기 분반 운영 문의. `자료구조`를 결석 대상 수업으로 옮기지 않는다. |
| IT15 | `collecting_absence_info` | `provide_absence_info` | `class_name=["알고리즘 실습"]; absence_date=["2026년 11월 12일"]; absence_reason=["독감 증상"]; user_name=["박지훈"]` | 현재 발화 자체가 결석을 통지한다. 독감 확진이라고 확장하지 않는다. |
| IT16 | `collecting_absence_info` | `unknown` | `class_name=null; absence_date=null; absence_reason=null; user_name=null` | 실습 코드 위치만 묻는다. 이전 결석 맥락만으로 이번 발화를 결석 통지로 채점하지 않는다. |

## 교수님: 과제 문의

`intent=assignment_inquiry`; 전체 필드: `course_name`, `assignment_topic`, `question`, `user_name`. 모든 행의 `current_fields={}`.

| ID | 상태 | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT17 | `greeting` | `provide_assignment_info` | `course_name=["자료구조"]; assignment_topic=["트리 순회 과제"]; question=["재귀 함수 대신 반복문 사용 가능 여부"]; user_name=null` | 과목명과 과제 주제, 구현 방식 질문을 각각 명시한다. |
| IT18 | `greeting` | `unknown` | `course_name=null; assignment_topic=null; question=null; user_name=null` | 보강 수업 시작 시간 문의이며 과제 관련 정보가 아니다. |
| IT19 | `collecting_assignment_info` | `provide_assignment_info` | `course_name=null; assignment_topic=["운영체제 프로세스 스케줄링 보고서"]; question=["비교할 알고리즘을 두 가지만 골라도 되는지"]; user_name=null` | 사용자가 `운영체제 프로세스 스케줄링 보고서` 전체를 과제 주제로 두고 과목명은 공란으로 채택했다. 비교 범위 질문은 명시됐다. |
| IT20 | `collecting_assignment_info` | `unknown` | `course_name=null; assignment_topic=null; question=null; user_name=null` | 조교 상담 시간 공지 위치 문의다. `컴퓨터네트워크 수업`을 과제 과목 필드로 옮기지 않는다. |

## 교수님: 면담 예약

`intent=appointment_booking`; 전체 필드: `appointment_purpose`, `date`, `time`, `user_name`. 모든 행의 `current_fields={}`.

| ID | 상태 | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT21 | `greeting` | `provide_appointment_info` | `appointment_purpose=["연구 윤리 심사 신청서 준비 방향 상담"]; date=["2027년 1월 20일"]; time=["오전 10시"]; user_name=null` | 면담 목적과 희망 일정이 명시됐다. |
| IT22 | `greeting` | `unknown` | `appointment_purpose=null; date=null; time=null; user_name=null` | 라이선스 신청 문의이며 면담 약속을 요청하지 않는다. |
| IT23 | `collecting_appointment_info` | `provide_appointment_info` | `appointment_purpose=["산학 프로젝트의 데이터 수집 계획 상담"]; date=["2027년 1월 21일"]; time=["오후 3시"]; user_name=["서지우"]` | 새 이름·목적·희망 일정과 면담 요청이 모두 있다. |
| IT24 | `collecting_appointment_info` | `unknown` | `appointment_purpose=null; date=null; time=null; user_name=null` | 논문 양식 메뉴 문의다. 이전 면담 상태와 분리한다. |

## 배달: 배달 지연 문의

`intent=delivery_delay_inquiry`; 전체 필드: `order_number`, `delay_detail`, `inquiry_goal`, `delay_resolution`.

| ID | 상태 / current_fields | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT25 | `greeting` / 전부 null | `provide_details` | `order_number=["L-204"]; delay_detail=["배달 예상 시간이 두 번 연장됨"]; inquiry_goal=["delivery_location"]; delay_resolution=null` | 진행 중인 주문의 지연과 현재 위치 문의. |
| IT26 | `greeting` / 전부 null | `unknown` | `order_number=null; delay_detail=null; inquiry_goal=null; delay_resolution=null` | 지난 주문의 매출전표 다운로드 방법이다. |
| IT27 | `collecting_delay_inquiry` / `order_number=P-376`, `delay_detail=오후 7시 20분 예정 시각에서 20분 경과`, 나머지 null | `provide_details` | `order_number=null; delay_detail=null; inquiry_goal=null; delay_resolution=["agent_handoff"]` | 지연 지속 시 상담원 연결을 원하는 후속 조치다. 연결 완료로 해석하지 않고 기존 주문번호·지연 사실을 재추출하지 않는다. |
| IT28 | `collecting_delay_inquiry` / `order_number=S-921`, `delay_detail=예정 시간 경과`, 나머지 null | `unknown` | `order_number=null; delay_detail=null; inquiry_goal=null; delay_resolution=null` | 후기 사진 첨부 한도는 현재 지연 문의 범위 밖이다. |

## 배달: 주문 변경

`intent=delivery_order_change`; 전체 필드: `order_number`, `change_type`, `requested_change`, `unavailable_preference`.

| ID | 상태 / current_fields | user_action | 전체 fields (`null` 포함) | 판단 근거·검토점 |
| --- | --- | --- | --- | --- |
| IT29 | `greeting` / 전부 null | `provide_details` | `order_number=["M-604"]; change_type=["menu_option"]; requested_change=["김치볶음밥의 계란 추가 옵션 제거"]; unavailable_preference=null` | 진행 중인 주문의 옵션 제거를 요청한다. |
| IT30 | `greeting` / 전부 null | `unknown` | `order_number=null; change_type=null; requested_change=null; unavailable_preference=null` | 향후 주문의 기본 설정 문의다. |
| IT31 | `collecting_order_change` / `order_number=B-319`, `change_type=delivery_address`, 나머지 null | `provide_details` | `order_number=null; change_type=null; requested_change=["수령 장소를 같은 건물 2층 안내데스크로 변경"]; unavailable_preference=null` | 이번 턴에 구체적 수령 장소를 추가한다. 이미 수집한 변경 항목을 반복하지 않는다. 사용자는 건물 안 수령 장소 변경을 기존 `delivery_address` 맥락에 포함하는 초안을 채택했다. |
| IT32 | `collecting_order_change` / `order_number=C-627`, `change_type=menu_option`, 나머지 null | `unknown` | `order_number=null; change_type=null; requested_change=null; unavailable_preference=null` | 원산지 표시 위치 문의는 현재 주문 옵션 변경이 아니다. |

## 채택된 해석과 남은 검증

1. **IT05·IT17·IT27**은 기존 탐색 사례와의 유사성 또는 계약 충돌을 해결하기 위해 문장을 교체했고, 사용자가 최종 문장과 대응 필드를 채택했다. IT27은 앞서 제안했던 위치 문의가 아니라 `agent_handoff` 후속 조치다.
2. **IT19**는 `운영체제 프로세스 스케줄링 보고서`를 과제 주제로 두고 과목명을 공란으로 둔 초안을, **IT31**은 건물 안 수령 장소 변경을 기존 `delivery_address` 맥락에 두는 초안을 사용자가 채택했다.
3. 전체 행동·비공란 값·공란은 사용자 1인 검수를 마쳤다. 평가 자료로 동결하기 전 계약 유효성·원문 중복·의미 유사성·입력 해시를 다시 검증해야 한다.
