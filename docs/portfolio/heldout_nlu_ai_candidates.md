# 구조화 NLU 새 평가 사례 AI 초안 후보 36건

**상태: `ai_assisted_unreviewed`.** 이 문서는 작성 보조 자료다. 공식 corpus,
`human_authored` 사례, 정답 확정 기록 또는 모델 정확도 근거가 아니다. 사람은
발화의 의미·정답·현재 상태·이전 필드·난이도 태그를 직접 확인하고 필요하면
다시 써야 한다. 문장을 약간 바꿔 기존 개발 사례의 패러프레이즈로 만들면
독립 테스트 사례가 아니므로 제외한다. 작성 기준과 36건 배분은
[`heldout_nlu_review.md`](heldout_nlu_review.md)를 따른다.

표의 `제안 값`은 이번 턴에 새로 말한 값만 적었다. 나머지 필드는 `null` 제안이지만
사람이 계약과 발화를 확인해야 한다. `unknown` 제안은 특정 상세 업무의 상태에서
그 업무의 정보를 제공하지 않는 발화라는 뜻이다. 다른 업무에서는 정상 발화일 수
있다. 예약 후속 4건은 특히 `current_fields`와 상태를 사람이 새로 설정해야 한다.

| ID | 업무·유형 | AI 제안 발화 | 행동·새 필드 초안 |
| --- | --- | --- | --- |
| C01 | 고객센터:a/s 접수 · 정보 제공 | 무선 이어폰 오른쪽이 충전되지 않아요. 택배로 접수하고 싶습니다. | `provide_details`; `product_type=무선 이어폰`, `symptom=오른쪽 충전 안 됨`, `service_channel=parcel` |
| C02 | 고객센터:a/s 접수 · 어려운 발화 | 인터넷 요금 할인 약정이 끝났는지 확인하고 싶어요. | `unknown`; 새 필드 없음 |
| C03 | 고객센터:요금/약정 상담 · 정보 제공 | 지난달 휴대전화 청구액이 평소보다 많이 나와서 내역을 상담받고 싶어요. | `provide_details`; `inquiry_type=billing`, `consultation_goal=지난달 청구액 확인` |
| C04 | 고객센터:요금/약정 상담 · 어려운 발화 | 노트북 키보드가 몇 글자만 눌려요. 수리 신청은 어디서 하나요? | `unknown`; 새 필드 없음 |
| C05 | 고객센터:인터넷/통화 문제 문의 · 정보 제공 | 집 와이파이가 어제부터 여러 기기에서 끊깁니다. 원격으로 확인해 주실 수 있나요? | `provide_details`; `service_type=wifi`, `symptom=끊김`, `occurred_at=어제부터`, `scope=multiple_devices`, `next_action=remote_check` |
| C06 | 고객센터:인터넷/통화 문제 문의 · 어려운 발화 | 이번 달 요금 납부일을 변경할 수 있나요? | `unknown`; 새 필드 없음 |
| C07 | 교수님:결석 사유 전달 · 정보 제공 | 교수님, 통계학 수업을 듣는 박민서입니다. 다음 주 월요일 가족 행사로 결석할 예정입니다. | `provide_absence_info`; `class_name=통계학`, `absence_date=다음 주 월요일`, `absence_reason=가족 행사`, `user_name=박민서` |
| C08 | 교수님:결석 사유 전달 · 어려운 발화 | 교수님, 다음 주에 연구실 면담 가능한 요일이 있을까요? | `unknown`; 새 필드 없음 |
| C09 | 교수님:과제 문의 · 정보 제공 | 교수님, 데이터베이스 수업의 정규화 과제는 PDF로 제출해도 되나요? | `provide_assignment_info`; `course_name=데이터베이스`, `assignment_topic=정규화 과제`, `question=PDF 제출 가능 여부` |
| C10 | 교수님:과제 문의 · 어려운 발화 | 교수님, 병원 진료 때문에 내일 수업에 못 갑니다. | `unknown`; 새 필드 없음 |
| C11 | 교수님:면담 예약 · 정보 제공 | 교수님, 논문 주제로 다음 주 수요일 오전 10시에 면담할 수 있을까요? | `provide_appointment_info`; `appointment_purpose=논문 주제`, `date=다음 주 수요일`, `time=오전 10시` |
| C12 | 교수님:면담 예약 · 어려운 발화 | 이번 과제의 참고 문헌은 몇 편이 필요한가요? | `unknown`; 새 필드 없음 |
| C13 | 배달:배달 지연 문의 · 정보 제공 | 주문번호 A104가 예정 시간보다 늦는데 지연 이유를 확인해 주세요. | `provide_details`; `order_number=A104`, `delay_detail=예정 시간보다 늦음`, `inquiry_goal=delay_reason` |
| C14 | 배달:배달 지연 문의 · 어려운 발화 | 주문번호 B205의 음료를 콜라에서 사이다로 바꾸고 싶어요. | `unknown`; 새 필드 없음 |
| C15 | 배달:주문 변경 · 정보 제공 | 주문번호 C306의 음료를 콜라 대신 사이다로 바꿔 주세요. | `provide_details`; `order_number=C306`, `change_type=menu_option`, `requested_change=콜라에서 사이다로 변경` |
| C16 | 배달:주문 변경 · 어려운 발화 | 배달된 음식에 국물이 새어 나왔는데 환불 절차가 어떻게 되나요? | `unknown`; 새 필드 없음 |
| C17 | 배달:환불/재배달 문의 · 정보 제공 | 주문번호 D407에서 음료가 빠졌어요. 음료만 다시 보내 주세요. | `provide_details`; `order_number=D407`, `issue_type=missing_item`, `issue_detail=음료 누락`, `resolution_preference=redelivery` |
| C18 | 배달:환불/재배달 문의 · 어려운 발화 | 주문번호 E508이 언제 도착하는지 확인해 주세요. | `unknown`; 새 필드 없음 |
| C19 | 시청:대형폐기물 배출 · 정보 제공 | 부산 해운대구에서 책상 두 개를 버리려는데 수수료가 얼마인가요? | `provide_details`; `region=부산 해운대구`, `item_name=책상`, `quantity=2개`, `request_topic=fee` |
| C20 | 시청:대형폐기물 배출 · 어려운 발화 | 음식물 쓰레기 봉투는 어느 편의점에서 살 수 있나요? | `unknown`; 새 필드 없음 |
| C21 | 시청:여권 발급 문의 · 정보 제공 | 미성년 자녀의 여권을 처음 만들 때 필요한 서류가 무엇인가요? | `provide_details`; `application_type=first_issue`, `applicant_type=minor`, `inquiry_topic=documents` |
| C22 | 시청:여권 발급 문의 · 어려운 발화 | 가족관계증명서를 무인발급기로 뽑을 수 있나요? | `unknown`; 새 필드 없음 |
| C23 | 시청:주민등록 등본 문의 · 정보 제공 | 정부24에서 제 주민등록등본을 발급하면 수수료가 있나요? | `provide_details`; `document_type=register_copy`, `applicant_relation=self`, `issuance_channel=government24`, `inquiry_topic=fee` |
| C24 | 시청:주민등록 등본 문의 · 어려운 발화 | 여권 재발급은 구청에 직접 가야 하나요? | `unknown`; 새 필드 없음 |
| C25 | 예약:미용실 예약 · 정보 제공 | 이번 주 금요일 오전 11시에 염색 예약할 수 있나요? | `continue_collecting`; `date=이번 주 금요일`, `time=오전 11시`, `service_type=염색` |
| C26 | 예약:미용실 예약 · 어려운 발화 | 머리 손질 방법만 알려 주세요. 예약은 아직 하지 않을게요. | `unknown` 제안; 새 필드 없음. 예약 의사 여부 검수 필요 |
| C27 | 예약:미용실 예약 · 후속 정보 | 예약자는 최유나이고, 이서진 디자이너로 부탁드려요. | `continue_collecting`; `user_name=최유나`, `designer=이서진`. 이전 날짜·시간·시술 문맥 필요 |
| C28 | 예약:병원 예약 · 정보 제공 | 다음 주 화요일 9시에 정형외과 예약하고 싶어요. | `continue_collecting`; `date=다음 주 화요일`, `time=9시`, `department=정형외과` |
| C29 | 예약:병원 예약 · 어려운 발화 | 병원까지 가는 버스 노선만 알려 주세요. | `unknown`; 새 필드 없음 |
| C30 | 예약:병원 예약 · 후속 정보 | 예약자 이름은 김하린입니다. | `continue_collecting`; `user_name=김하린`. 이전 진료과·날짜·시간 문맥 필요 |
| C31 | 예약:스터디룸 예약 · 정보 제공 | 토요일 오후 1시부터 세 명이 쓸 방을 예약하고 싶어요. | `continue_collecting`; `date=토요일`, `start_time=오후 1시`, `party_size=3명` |
| C32 | 예약:스터디룸 예약 · 어려운 발화 | 회의실 프로젝터가 고장 났는데 수리 요청할 수 있나요? | `unknown`; 새 필드 없음 |
| C33 | 예약:스터디룸 예약 · 후속 정보 | 예약자 윤서준입니다. 방은 세 시간 동안 사용할 예정이에요. | `continue_collecting`; `duration=3시간`, `user_name=윤서준`. 이전 날짜·인원·시작 시각 문맥 필요 |
| C34 | 예약:식당 예약 · 정보 제공 | 다음 달 첫째 토요일에 네 명이 저녁 식사하려고 합니다. 예약 가능한가요? | `continue_collecting`; `date=다음 달 첫째 토요일`, `party_size=4명`. `저녁`을 정확한 시각으로 만들지 않는지 검수 |
| C35 | 예약:식당 예약 · 어려운 발화 | 오늘 주문한 음식의 배달 예상 시간이 궁금해요. | `unknown`; 새 필드 없음 |
| C36 | 예약:식당 예약 · 후속 정보 | 이름은 정다은이고 오후 7시로 부탁드려요. | `continue_collecting`; `user_name=정다은`, `time=오후 7시`. 이전 날짜·인원 문맥 필요 |

검수할 때는 항목별로 **아이디어 채택 후 새로 작성 / 수정 / 제외**, 새 발화와
최종 정답, 현재 상태와 이전 필드, 판단 근거를 기록한다. 아이디어를 채택해도
AI 문장과 정답을 그대로 `human_authored`로 옮길 수 없다. 특히 C26의 예약 의사,
C09의 과제 주제와 질문, C15의 `change_type`, C34의 시간 값은 계약과 의미
판단을 확인해야 한다. 이 초안의 제안 값을 그대로 정답으로 간주하지 않는다.

2026-10-10 정적 사전 점검에서는 제안된 행동·필드를 해당 업무의 라이브 출력
계약에 대입해 36/36 통과했다. 기존 development 36건과 AI-origin V8 이력의
문장과 NFC 정규화한 **정확 원문 일치**는 0건이었다. 이 검사는 문장 의미,
패러프레이즈 유사성, 정답 타당성, 사람 검수를 확인하지 않는다. 예약 후속
4건의 이전 상태값도 아직 사람이 확정하지 않았다.
