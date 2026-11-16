# 내부 test IT33–IT64 행동·전체 필드 검토 초안 B

> **실모델 실행 전 사용자 1인 전체 필드 검수 기록.** [발화 원문과 상태](nlu_internal_test64_draft_part_b.md)의 IT33–IT64에 대응한다. 사용자가 아래 행동 코드, 비공란 값과 공란을 채택하고 [IT40·IT41 교체안](nlu_internal_test80_independence_revision_review.md)도 승인했다. 이후 `adjudicated` 데이터를 동결하고 [실모델 평가](nlu_internal_test80_verified_result.md)를 완료했다. 모든 이름·주문번호는 가상이다.

`fields`는 **이번 발화의 추출 값**이며 누적된 `current_fields`를 복사하지 않는다. 각 JSON 객체에 해당 시나리오의 **모든 필드**를 명시했다. 비공란 문자열은 사용자가 채택한 허용값 하나다. 추가 허용 표기는 확정하지 않았다. 표의 `change_field`는 전부 `null`이다. `offered_alternative_times`는 전부 빈 목록이다. 같은 후속 상태의 두 문장은 **독립 대화**다.

## 배달: 환불/재배달 문의

`scenario_key=배달:환불/재배달 문의`, `intent=delivery_refund_redelivery`. IT33·34는 `conversation_state=greeting`, `current_fields={"order_number":null,"issue_type":null,"issue_detail":null,"evidence_status":null,"resolution_preference":null}`. IT35·36은 `conversation_state=collecting_refund_redelivery`, `current_fields={"order_number":"주문번호 M-928","issue_type":"damaged_or_quality","issue_detail":"포장된 반찬 용기가 깨져 내용물이 샘","evidence_status":null,"resolution_preference":"refund"}`. 직전 질문은 입력되지 않는다.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT33 | `provide_details` | `{"order_number":"주문번호 M-928","issue_type":"damaged_or_quality","issue_detail":"받은 반찬 용기가 깨져 내용물이 새어 나옴","evidence_status":null,"resolution_preference":"refund"}` | 주문 식별·파손 내용·환불 요청이 발화에 있다. 사진은 언급하지 않는다. |
| IT34 | `unknown` | `{"order_number":null,"issue_type":null,"issue_detail":null,"evidence_status":null,"resolution_preference":null}` | 계절 디저트 판매 시점은 현재 주문 문제의 범위 밖이다. |
| IT35 | `provide_details` | `{"order_number":null,"issue_type":null,"issue_detail":null,"evidence_status":"available","resolution_preference":null}` | 사진을 찍어 두었다고 명시했다. 기존 주문·문제·처리 값을 이번 턴에 반복 추출하지 않는다. |
| IT36 | `unknown` | `{"order_number":null,"issue_type":null,"issue_detail":null,"evidence_status":null,"resolution_preference":null}` | 새 메뉴의 향후 배달 가능 여부는 현재 환불 상담과 무관하다. |

## 시청: 대형폐기물 배출

`scenario_key=시청:대형폐기물 배출`, `intent=bulky_waste_guidance`. IT37·38은 `conversation_state=greeting`, `current_fields={"region":null,"item_name":null,"quantity":null,"request_topic":null}`. IT39·40은 `conversation_state=collecting_bulky_waste`, `current_fields={"region":"세종시 나성동","item_name":"철제 침대 프레임","quantity":null,"request_topic":"place_and_schedule"}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT37 | `provide_details` | `{"region":"부산 연제구","item_name":"낡은 캣타워","quantity":null,"request_topic":"application"}` | 대형폐기물 온라인 신고 절차를 물었다. 수량은 없다. |
| IT38 | `unknown` | `{"region":null,"item_name":null,"quantity":null,"request_topic":null}` | 헌 전선 재활용품 배출은 대형폐기물 신고 범위 밖이다. |
| IT39 | `provide_details` | `{"region":null,"item_name":null,"quantity":"두 개","request_topic":null}` | 빠진 수량을 제공했다. 같은 날 수거 가능성 질문은 이미 수집된 `place_and_schedule`을 반복 기록하지 않으며 실제 수거일을 단정하지 않는다. |
| IT40 | `unknown` | `{"region":null,"item_name":null,"quantity":null,"request_topic":null}` | 텃밭 흙의 배출 방법은 현재 대형폐기물 신고 업무 밖이다. 실제 종량제 배출 가능 여부는 판단하지 않는다. |

## 시청: 여권 발급 문의

`scenario_key=시청:여권 발급 문의`, `intent=passport_guidance`. IT41·42는 `conversation_state=greeting`, `current_fields={"application_type":null,"applicant_type":null,"inquiry_topic":null,"application_channel":null}`. IT43·44는 `conversation_state=collecting_passport_inquiry`, `current_fields={"application_type":"reissue","applicant_type":"adult_self","inquiry_topic":null,"application_channel":"government24"}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT41 | `provide_details` | `{"application_type":"emergency","applicant_type":null,"inquiry_topic":"office","application_channel":null}` | 긴급여권의 접수기관을 묻는다. 신청인 구분과 실제 신청 경로는 발화만으로 정하지 않는다. |
| IT42 | `unknown` | `{"application_type":null,"applicant_type":null,"inquiry_topic":null,"application_channel":null}` | 영문 출생증명서 발급은 여권 발급과 다른 증명서 업무다. |
| IT43 | `provide_details` | `{"application_type":null,"applicant_type":null,"inquiry_topic":"online_eligibility","application_channel":null}` | 정부24 재발급 가능 조건을 묻는다. `reissue`와 `government24`는 이미 `current_fields`에 있어 이번 턴에는 반복 추출하지 않는다. 실제 자격을 판정하지 않는다. |
| IT44 | `unknown` | `{"application_type":null,"applicant_type":null,"inquiry_topic":null,"application_channel":null}` | 주민등록증 분실 신고는 여권 업무 밖이다. |

## 시청: 주민등록 등본 문의

`scenario_key=시청:주민등록 등본 문의`, `intent=resident_certificate_guidance`. IT45·46은 `conversation_state=greeting`, `current_fields={"document_type":null,"applicant_relation":null,"issuance_channel":null,"inquiry_topic":null}`. IT47·48은 `conversation_state=collecting_certificate_inquiry`, `current_fields={"document_type":"individual_extract","applicant_relation":"self","issuance_channel":null,"inquiry_topic":"fee"}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT45 | `provide_details` | `{"document_type":"register_copy","applicant_relation":"same_household","issuance_channel":null,"inquiry_topic":"documents"}` | 등본, 같은 세대 아버지, 준비물 문의가 명시됐다. 실제 발급 자격은 이 추출 라벨에서 판단하지 않는다. |
| IT46 | `unknown` | `{"document_type":null,"applicant_relation":null,"issuance_channel":null,"inquiry_topic":null}` | 지방세 과세증명서는 등·초본이 아니다. `온라인`도 이 업무의 발급 채널로 추출하지 않는다. |
| IT47 | `provide_details` | `{"document_type":null,"applicant_relation":null,"issuance_channel":"in_person","inquiry_topic":null}` | 동 주민센터 창구 방문 경로를 제공했다. 기존 초본·본인·수수료 값을 반복하지 않는다. |
| IT48 | `unknown` | `{"document_type":null,"applicant_relation":null,"issuance_channel":null,"inquiry_topic":null}` | 농지대장 열람은 등·초본 외 서류다. |

## 예약 네 업무 공통 입력 조건

예약 직접 분석기의 `current_fields={}`다. 문장 검토표에 적힌 직전 질문·과거 예약 정보는 모델 입력으로 제공되지 않는다. 따라서 아래 라벨은 **상태명과 현재 발화**에서만 추출한다. `greeting` 또는 수집 상태에서 업무 안 발화는 `continue_collecting`, 범위 밖 발화는 `unknown`으로 채택했다. `selected_time`은 대체 시간 선택 발화가 없어 전부 `null`이다. 예약 업무의 `change_field`도 전부 `null`이다.

### 미용실 예약

`scenario_key=예약:미용실 예약`, `intent=reservation`. IT49·50은 `conversation_state=greeting`, IT51·52는 `conversation_state=collecting_reservation_info`; 모두 `current_fields={}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT49 | `continue_collecting` | `{"date":"2027년 1월 9일","time":"오후 4시","service_type":"레이어드 펌","designer":null,"user_name":null,"selected_time":null}` | 날짜·시간·시술을 직접 제공했다. 가능 시간 질문은 예약 진행의 일부다. |
| IT50 | `unknown` | `{"date":null,"time":null,"service_type":null,"designer":null,"user_name":null,"selected_time":null}` | 집에서의 모발 관리 조언만 요청한다. |
| IT51 | `continue_collecting` | `{"date":null,"time":null,"service_type":null,"designer":"지현 선생님","user_name":null,"selected_time":null}` | 현재 발화에서 디자이너만 선택한다. 과거 날짜·시간·시술·예약자 정보는 보이지 않는다. |
| IT52 | `unknown` | `{"date":null,"time":null,"service_type":null,"designer":null,"user_name":null,"selected_time":null}` | 제품 브랜드 문의는 예약 조건이 아니다. |

### 병원 예약

`scenario_key=예약:병원 예약`. IT53·54는 `conversation_state=greeting`, IT55·56은 `conversation_state=asking_time`; 모두 `current_fields={}`. 병원 계약만 범위 밖 발화의 `intent=null`을 허용한다. 업무 안은 `intent=reservation`이다.

| ID | `intent` | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- | --- |
| IT53 | `reservation` | `continue_collecting` | `{"department":"내과","date":"2027년 1월 13일","time":"오전","user_name":null,"selected_time":null}` | 내과·날짜·오전 시간대의 진료 예약을 요청한다. 속쓰림은 현재 출력 필드가 없다. |
| IT54 | `null` | `unknown` | `{"department":null,"date":null,"time":null,"user_name":null,"selected_time":null}` | 약물 병용 판단만 묻고 예약을 요청하지 않는다. |
| IT55 | `reservation` | `continue_collecting` | `{"department":null,"date":null,"time":"오전 10시 반","user_name":null,"selected_time":null}` | 현재 발화는 희망 시간만 제공한다. 과거 내과·날짜를 추출하지 않는다. |
| IT56 | `null` | `unknown` | `{"department":null,"date":null,"time":null,"user_name":null,"selected_time":null}` | 혈액검사 전 금식 시간은 의료 준비 문의이며 예약 시간 제공이 아니다. |

### 스터디룸 예약

`scenario_key=예약:스터디룸 예약`, `intent=reservation`. IT57·58은 `conversation_state=greeting`, IT59·60은 `conversation_state=collecting_reservation_info`; 모두 `current_fields={}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT57 | `continue_collecting` | `{"date":"2027년 1월 15일","start_time":"오전 10시","duration":"한 시간 반","party_size":"네 명","user_name":null,"selected_time":null}` | 예약일·시작 시간·이용 시간·인원을 모두 제공했다. |
| IT58 | `unknown` | `{"date":null,"start_time":null,"duration":null,"party_size":null,"user_name":null,"selected_time":null}` | 출입카드 재발급 문의는 방 예약 조건이 아니다. |
| IT59 | `continue_collecting` | `{"date":null,"start_time":null,"duration":null,"party_size":"다섯 명","user_name":null,"selected_time":null}` | 현재 발화의 참석 인원만 제공한다. |
| IT60 | `unknown` | `{"date":null,"start_time":null,"duration":null,"party_size":null,"user_name":null,"selected_time":null}` | 외부 음료 반입 정책 문의는 예약 정보가 아니다. |

### 식당 예약

`scenario_key=예약:식당 예약`, `intent=reservation`. IT61·62는 `conversation_state=greeting`, IT63·64는 `conversation_state=collecting_reservation_info`; 모두 `current_fields={}`.

| ID | `user_action` | `fields` 전체 | 근거 |
| --- | --- | --- | --- |
| IT61 | `continue_collecting` | `{"date":"2027년 1월 24일","time":"저녁 6시쯤","party_size":"둘","user_name":null,"selected_time":null}` | 날짜·대략적인 저녁 시간·2인 좌석 예약 요청이다. `쯤`을 시간 값에 보존하는 초안이다. |
| IT62 | `unknown` | `{"date":null,"time":null,"party_size":null,"user_name":null,"selected_time":null}` | 포장 주문은 좌석 예약 범위 밖이다. |
| IT63 | `continue_collecting` | `{"date":null,"time":null,"party_size":"다섯 명","user_name":null,"selected_time":null}` | 어른 3명과 아이 2명의 합계를 발화가 직접 다섯 명이라고 밝혔다. |
| IT64 | `unknown` | `{"date":null,"time":null,"party_size":null,"user_name":null,"selected_time":null}` | 땅콩 사용 여부만 묻고 예약 조건을 제공하지 않는다. |

## 사용자 검수로 채택한 판단 지점

- **IT39:** `request_topic=place_and_schedule`은 이미 누적 문맥에 있다. 이번 발화의 같은 날 수거 가능성 질문을 새 추출 값으로 다시 기록하면 `provide_details`의 기존 필드 재추출 금지 계약에 어긋난다.
- **IT41:** 교체 문장은 긴급여권 접수기관 문의다. `application_type=emergency`, `inquiry_topic=office`를 채택했고, `applicant_type`과 `application_channel`은 공란으로 둔다.
- **IT43:** `온라인 신청 자격`은 `online_eligibility`로 제안했다. 이미 있는 재발급 유형·정부24 경로는 다시 내보내지 않는다.
- **IT51·55·59·63:** 후속 질문과 과거 예약 정보가 직접 분석기에 들어가지 않아 현재 발화만의 값으로 제안했다.
- **IT61:** `party_size=둘`과 `time=저녁 6시쯤`으로 원문의 수량·불확실성을 보존한 값을 채택했다. 추가 허용 표기는 현재 확정하지 않았다.

계약 근거: `evals/structured_nlu/contracts.py`, `services/flow/delivery/contracts.py`, `services/flow/cityhall/contracts.py`, `services/flow/service_workflow/structured_contract.py`, `services/flow/reservation/{hair_salon,hospital,study_room,restaurant}/llm_structured.py`. 기존 범위 밖 예약 라벨 방향은 `docs/portfolio/nlu_scope_fresh_v2_field_review.md`와 대조했다. 별도 구현·모델 실행·AWS 사용은 하지 않았다.
