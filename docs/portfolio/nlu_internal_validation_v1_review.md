# 내부 표본 validation 32건: AI 작성·미검수 초안

> 상태: **AI 작성, 모델 미실행, 사람 검수 전**. 이 문서와 JSON은 공식 정확도 근거가 아니다. 이 32건은 후보 선택용 validation 후보이며 최종 test 64건과 분리한다.

## 검수 기준

- 각 업무에 업무 안 정보 제공 1건과 범위 밖 `unknown` 1건을 제안했다. 모든 사례는 `greeting` 상태이므로 후속 상태 성능을 대표하지 않는다.
- 모든 문장과 정답은 AI 초안이다. 사용자에게 문장 자연스러움, 업무 범위, 행동, 비공란 값과 **나머지 모든 필드의 공란**을 각각 확인받아야 한다. `draft`를 임의로 `adjudicated`로 바꾸지 않는다.
- `accepted_values`는 정규화 허용 문자열 제안이다. 의미가 맞더라도 실제 서버의 정규화 규칙과 맞지 않으면 검수 때 고친다.
- 기존 `evals/structured_nlu/data` JSON·JSONL의 `user_message` 등 발화 396개와 NFC 정규화 정확 일치를 확인했고 일치 문장은 없었다. 이것은 알려진 자료의 정확 일치 검사일 뿐, 모든 노출 이력이나 유사 문장의 독립성을 증명하지 않는다.
- 아래의 `fields`는 **모든 필드**를 표시하며, `null`은 해당 턴에서 새 값이 없다는 초안이다.

## 사례별 문장·전체 정답 초안

### 고객센터:a/s 접수

**ai-internal-val-v01-01** · 업무 안 · 상태 `greeting`

> 로봇청소기가 충전대에 올라가도 접촉이 끊겨 충전이 중단됩니다. 점검 접수를 하고 싶습니다.

- `intent=service_request`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"model_name": null, "occurred_at": null, "preferred_schedule": null, "product_type": ["로봇청소기"], "safety_status": null, "service_channel": null, "symptom": ["충전대 접촉이 끊겨 충전이 중단됨"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-02** · 범위 밖 · 상태 `greeting`

> 수리비를 결제한 뒤 현금영수증을 발급받는 방법을 알려주실 수 있나요?

- `intent=service_request`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"model_name": null, "occurred_at": null, "preferred_schedule": null, "product_type": null, "safety_status": null, "service_channel": null, "symptom": null}`
- `tags`: `hard_negative`

### 고객센터:요금/약정 상담

**ai-internal-val-v01-03** · 업무 안 · 상태 `greeting`

> 제 휴대전화 약정이 언제 끝나는지 확인하고 싶습니다.

- `intent=plan_contract_consultation`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"consent_scope": null, "consultation_goal": ["휴대전화 약정 종료일 확인"], "current_service": null, "inquiry_type": ["contract_expiry"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-04** · 범위 밖 · 상태 `greeting`

> 새 휴대전화 회선을 개통할 때 필요한 본인 확인 서류는 무엇인가요?

- `intent=plan_contract_consultation`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"consent_scope": null, "consultation_goal": null, "current_service": null, "inquiry_type": null}`
- `tags`: `hard_negative`

### 고객센터:인터넷/통화 문제 문의

**ai-internal-val-v01-05** · 업무 안 · 상태 `greeting`

> 지하철에서 모바일 데이터가 연결 상태로 뜨지만 지도 앱과 웹페이지가 모두 열리지 않습니다.

- `intent=network_call_issue`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"next_action": null, "occurred_at": null, "scope": ["specific_location"], "service_type": ["mobile_data"], "symptom": ["모바일 데이터 연결 표시가 있지만 지도 앱과 웹페이지가 열리지 않음"], "troubleshooting_done": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-06** · 범위 밖 · 상태 `greeting`

> 휴대전화에 저장된 사진을 컴퓨터로 옮기는 방법이 궁금합니다.

- `intent=network_call_issue`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"next_action": null, "occurred_at": null, "scope": null, "service_type": null, "symptom": null, "troubleshooting_done": null}`
- `tags`: `hard_negative`

### 교수님:결석 사유 전달

**ai-internal-val-v01-07** · 업무 안 · 상태 `greeting`

> 다음 주 화요일 세미나 수업은 가족 행사 때문에 참석하기 어렵습니다.

- `intent=absence_notice`, `user_action=provide_absence_info`, `change_field=None`
- 전체 `fields`: `{"absence_date": ["다음 주 화요일"], "absence_reason": ["가족 행사"], "class_name": ["세미나 수업"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-08** · 범위 밖 · 상태 `greeting`

> 지난 학기 수업 녹화 영상을 다시 다운로드할 수 있나요?

- `intent=absence_notice`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"absence_date": null, "absence_reason": null, "class_name": null, "user_name": null}`
- `tags`: `hard_negative`

### 교수님:과제 문의

**ai-internal-val-v01-09** · 업무 안 · 상태 `greeting`

> 이번 발표 과제에 정해진 표지 양식이 있는지 궁금합니다.

- `intent=assignment_inquiry`, `user_action=provide_assignment_info`, `change_field=None`
- 전체 `fields`: `{"assignment_topic": ["이번 발표 과제"], "course_name": null, "question": ["표지 양식 지정 여부"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-10** · 범위 밖 · 상태 `greeting`

> 교내 장학금 신청서를 어디에 제출해야 하나요?

- `intent=assignment_inquiry`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"assignment_topic": null, "course_name": null, "question": null, "user_name": null}`
- `tags`: `hard_negative`

### 교수님:면담 예약

**ai-internal-val-v01-11** · 업무 안 · 상태 `greeting`

> 졸업 작품에서 사용할 센서 선택을 상담하고 싶습니다. 목요일 오후 4시에 뵐 수 있을까요?

- `intent=appointment_booking`, `user_action=provide_appointment_info`, `change_field=None`
- 전체 `fields`: `{"appointment_purpose": ["졸업 작품에 사용할 센서 선택 상담"], "date": ["목요일"], "time": ["오후 4시"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-12** · 범위 밖 · 상태 `greeting`

> 교수님께 추천서를 부탁드리려면 어떤 자료를 먼저 보내야 하나요?

- `intent=appointment_booking`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"appointment_purpose": null, "date": null, "time": null, "user_name": null}`
- `tags`: `hard_negative`

### 배달:배달 지연 문의

**ai-internal-val-v01-13** · 업무 안 · 상태 `greeting`

> 배달 기사님 위치가 30분째 같은 곳으로 표시됩니다. 도착 예정 시각을 알 수 있을까요?

- `intent=delivery_delay_inquiry`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"delay_detail": ["배달 기사님 위치가 30분째 같은 곳으로 표시됨"], "delay_resolution": null, "inquiry_goal": ["estimated_arrival"], "order_number": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-14** · 범위 밖 · 상태 `greeting`

> 배달앱에서 받은 선물 쿠폰을 등록하는 방법을 알려주세요.

- `intent=delivery_delay_inquiry`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"delay_detail": null, "delay_resolution": null, "inquiry_goal": null, "order_number": null}`
- `tags`: `hard_negative`

### 배달:주문 변경

**ai-internal-val-v01-15** · 업무 안 · 상태 `greeting`

> 주문번호 C-517의 떡볶이 맵기를 순한맛으로 바꿔 주실 수 있나요?

- `intent=delivery_order_change`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"change_type": ["menu_option"], "order_number": ["C-517"], "requested_change": ["떡볶이 맵기를 순한맛으로 변경"], "unavailable_preference": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-16** · 범위 밖 · 상태 `greeting`

> 주문할 때 적립한 포인트는 언제 사용할 수 있나요?

- `intent=delivery_order_change`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"change_type": null, "order_number": null, "requested_change": null, "unavailable_preference": null}`
- `tags`: `hard_negative`

### 배달:환불/재배달 문의

**ai-internal-val-v01-17** · 업무 안 · 상태 `greeting`

> 받은 음료의 컵 뚜껑이 열려 내용물이 흘렀습니다. 같은 음료를 다시 보내주실 수 있나요?

- `intent=delivery_refund_redelivery`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"evidence_status": null, "issue_detail": ["음료 컵 뚜껑이 열려 내용물이 흘렀음"], "issue_type": ["damaged_or_quality"], "order_number": null, "resolution_preference": ["redelivery"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-18** · 범위 밖 · 상태 `greeting`

> 음식 알레르기가 있어 주문 전 재료를 확인하고 싶어요. 원재료 목록을 받을 수 있을까요?

- `intent=delivery_refund_redelivery`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"evidence_status": null, "issue_detail": null, "issue_type": null, "order_number": null, "resolution_preference": null}`
- `tags`: `hard_negative`

### 시청:대형폐기물 배출

**ai-internal-val-v01-19** · 업무 안 · 상태 `greeting`

> 접수한 책상 한 개를 배출 장소에 언제 내놓아야 하는지 알고 싶습니다.

- `intent=bulky_waste_guidance`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"item_name": ["책상"], "quantity": ["한 개"], "region": null, "request_topic": ["place_and_schedule"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-20** · 범위 밖 · 상태 `greeting`

> 헌 옷 수거함이 가까운 곳에 있는지 알려주세요.

- `intent=bulky_waste_guidance`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"item_name": null, "quantity": null, "region": null, "request_topic": null}`
- `tags`: `hard_negative`

### 시청:여권 발급 문의

**ai-internal-val-v01-21** · 업무 안 · 상태 `greeting`

> 처음 여권을 신청합니다. 구청에 내야 하는 수수료가 얼마인가요?

- `intent=passport_guidance`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"applicant_type": null, "application_channel": null, "application_type": ["first_issue"], "inquiry_topic": ["fee"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-22** · 범위 밖 · 상태 `greeting`

> 일본에서 렌터카를 이용하려고 합니다. 국제운전면허증은 어떻게 신청하나요?

- `intent=passport_guidance`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"applicant_type": null, "application_channel": null, "application_type": null, "inquiry_topic": null}`
- `tags`: `hard_negative`

### 시청:주민등록 등본 문의

**ai-internal-val-v01-23** · 업무 안 · 상태 `greeting`

> 제 주민등록초본을 무인발급기에서 뽑으려는데 수수료가 있나요?

- `intent=resident_certificate_guidance`, `user_action=provide_details`, `change_field=None`
- 전체 `fields`: `{"applicant_relation": ["self"], "document_type": ["individual_extract"], "inquiry_topic": ["fee"], "issuance_channel": ["kiosk"]}`
- `tags`: `multi_field`

**ai-internal-val-v01-24** · 범위 밖 · 상태 `greeting`

> 혼인관계증명서를 인터넷으로 발급받는 방법이 궁금합니다.

- `intent=resident_certificate_guidance`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"applicant_relation": null, "document_type": null, "inquiry_topic": null, "issuance_channel": null}`
- `tags`: `hard_negative`

### 예약:미용실 예약

**ai-internal-val-v01-25** · 업무 안 · 상태 `greeting`

> 이번 주말 가족 행사 전에 머리를 다듬고 싶습니다. 토요일 오후 3시에 일반 커트 예약 부탁드립니다.

- `intent=reservation`, `user_action=continue_collecting`, `change_field=None`
- 전체 `fields`: `{"date": ["토요일"], "designer": null, "selected_time": null, "service_type": ["일반 커트"], "time": ["오후 3시"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-26** · 범위 밖 · 상태 `greeting`

> 제 얼굴형에 어울리는 헤어스타일을 추천해 주실 수 있나요?

- `intent=reservation`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"date": null, "designer": null, "selected_time": null, "service_type": null, "time": null, "user_name": null}`
- `tags`: `hard_negative`

### 예약:병원 예약

**ai-internal-val-v01-27** · 업무 안 · 상태 `greeting`

> 허리를 삐끗해 진료를 받으려는데 다음 주 월요일 오후 정형외과 예약 자리가 있나요?

- `intent=reservation`, `user_action=continue_collecting`, `change_field=None`
- 전체 `fields`: `{"date": ["다음 주 월요일"], "department": ["정형외과"], "selected_time": null, "time": ["오후"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-28** · 범위 밖 · 상태 `greeting`

> 지난번 진료의 처방전을 다시 발급받으려면 어떻게 해야 하나요?

- `intent=None`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"date": null, "department": null, "selected_time": null, "time": null, "user_name": null}`
- `tags`: `hard_negative`

### 예약:스터디룸 예약

**ai-internal-val-v01-29** · 업무 안 · 상태 `greeting`

> 친구와 면접 연습을 하려고요. 일요일 오후 1시에 시작해 세 시간 쓸 수 있는 두 명용 방으로 잡아주세요.

- `intent=reservation`, `user_action=continue_collecting`, `change_field=None`
- 전체 `fields`: `{"date": ["일요일"], "duration": ["세 시간"], "party_size": ["두 명"], "selected_time": null, "start_time": ["오후 1시"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-30** · 범위 밖 · 상태 `greeting`

> 스터디룸 안에서 프린터 용지를 살 수 있나요?

- `intent=reservation`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"date": null, "duration": null, "party_size": null, "selected_time": null, "start_time": null, "user_name": null}`
- `tags`: `hard_negative`

### 예약:식당 예약

**ai-internal-val-v01-31** · 업무 안 · 상태 `greeting`

> 일요일 낮 12시에 네 명이 식사할 자리를 예약하고 싶습니다.

- `intent=reservation`, `user_action=continue_collecting`, `change_field=None`
- 전체 `fields`: `{"date": ["일요일"], "party_size": ["네 명"], "selected_time": null, "time": ["낮 12시"], "user_name": null}`
- `tags`: `multi_field`

**ai-internal-val-v01-32** · 범위 밖 · 상태 `greeting`

> 매장에서 주문한 음식을 집으로 배달받을 수 있나요?

- `intent=reservation`, `user_action=unknown`, `change_field=None`
- 전체 `fields`: `{"date": null, "party_size": null, "selected_time": null, "time": null, "user_name": null}`
- `tags`: `hard_negative`

## 모델 실행 전 사용자 결정

우선 확인이 필요한 경계는 `ai-internal-val-v01-03`의 본인 약정 조회와 `consent_scope` 공란, `ai-internal-val-v01-13`의 위치 정체를 지연 정보로 볼지, `ai-internal-val-v01-17`의 재배달 **요청** 해석, `ai-internal-val-v01-19`의 배출 시기 문의 코드다.

32건의 문장·업무 범위와 각 건의 행동·전체 필드·공란·허용값을 검수한다. 수정할 ID와 항목을 기록하고, 최종 채택한 데이터 원문 해시를 사례별 결정 원장과 연결한다. 아직 사용자 결정 기록이 없으므로 이 초안을 평가에 투입하지 않는다.
