# CF01–CF32 행동·전체 필드 검수 초안

**현재 상태: AI 작성 행동·전체 필드·공란·기대 상태 초안을 사용자가 탐색용으로 채택했다. 모델에 실행하지 않았다.** [발화 문장·안전 방향](nlu_safety_confirmation_fresh_review.md)도 별도로 채택됐다. 모든 사례는 A/S 접수의 `greeting`에서 시작하며 이전 필드는 모두 공란이다. `intent=service_request`, `change_field=null`이다. 표에 없는 일곱 업무 필드는 모두 `null`이다. 비공란 값은 한 가지 허용 정규화 값으로 제안한다.

`user_action`이 `unknown`인 사례에는 업무 필드 값을 넣지 않는다. `provide_details`는 현재 A/S 대상에 대한 실제 정보를 말한 경우에만 제안한다. 안전 방향과 그래프 기대 상태는 별도다. 현재 제품의 실제 위험이면 즉시 보호 상태가 목표이고, 위험 여부가 불확실하면 확인 상태가 목표다.

| ID | `user_action` 초안 | 비공란 필드 초안 | 기대 그래프 상태 초안 |
| --- | --- | --- | --- |
| CF01 | `provide_details` | `product_type=휴대용 선풍기`; `symptom=충전 포트 안쪽에서 작은 불꽃이 여러 번 튐`; `safety_status=safety_issue` | `safety_action_required` |
| CF02 | `provide_details` | `product_type=노트북`; `symptom=하판 가운데가 솟아오르고 트랙패드가 잘 눌리지 않음`; `safety_status=safety_issue` | `safety_action_required` |
| CF03 | `provide_details` | `product_type=에어프라이어`; `symptom=사용 중 플라스틱이 타는 듯한 냄새가 계속 남`; `safety_status=safety_issue` | `safety_action_required` |
| CF04 | `provide_details` | `product_type=전동 공구 배터리`; `symptom=액체가 새고 손끝이 찌릿함`; `safety_status=safety_issue` | `safety_action_required` |
| CF05 | `provide_details` | `product_type=커피 머신`; `symptom=전원 연결 시 어댑터 쪽에서 희미한 연무가 올라옴`; `safety_status=safety_issue` | `safety_action_required` |
| CF06 | `provide_details` | `product_type=전동 킥보드`; `symptom=충전 중 배터리 부분이 손을 대기 어려울 만큼 뜨거워짐`; `safety_status=safety_issue` | `safety_action_required` |
| CF07 | `provide_details` | `product_type=건조기`; `symptom=전원 케이블 연결부가 검게 그을리고 플라스틱이 조금 녹음`; `safety_status=safety_issue` | `safety_action_required` |
| CF08 | `provide_details` | `product_type=모니터`; `symptom=어댑터에서 타닥거리는 소리와 고무 타는 냄새가 남`; `safety_status=safety_issue` | `safety_action_required` |
| CF09 | `provide_details` | `product_type=게임기`; `symptom=전원선 피복이 갈라져 내부 금속선이 보임`; `safety_status=safety_issue` | `safety_action_required` |
| CF10 | `provide_details` | `product_type=휴대용 히터`; `symptom=사용 중 본체 틈에서 연기가 피어오름`; `safety_status=safety_issue` | `safety_action_required` |
| CF11 | `provide_details` | `product_type=전동 칫솔`; `symptom=충전 중 손잡이 아래가 잡기 힘들 만큼 뜨거워짐`; `safety_status=safety_issue` | `safety_action_required` |
| CF12 | `provide_details` | `product_type=보조배터리`; `symptom=한쪽 면이 볼록하게 변형돼 케이스가 닫히지 않음`; `safety_status=safety_issue` | `safety_action_required` |
| CF13 | `provide_details` | `product_type=가습기`; `symptom=뒤쪽에서 흰 것이 잠깐 나옴` | `confirming_safety_status` |
| CF14 | `provide_details` | `product_type=무선 청소기`; `symptom=배터리 덮개가 들뜬 것처럼 보임` | `confirming_safety_status` |
| CF15 | `provide_details` | `product_type=휴대폰`; `symptom=충전 시 평소보다 따뜻하게 느껴짐` | `confirming_safety_status` |
| CF16 | `provide_details` | `product_type=전기장판` | `confirming_safety_status` |
| CF17 | `provide_details` | `product_type=노트북`; `symptom=충전 포트에서 작은 빛을 봄` | `confirming_safety_status` |
| CF18 | `provide_details` | `product_type=선풍기` | `confirming_safety_status` |
| CF19 | `provide_details` | `product_type=전자레인지`; `symptom=문 옆에 검은 자국이 생김` | `confirming_safety_status` |
| CF20 | `provide_details` | `product_type=태블릿`; `symptom=충전선 겉면이 벗겨진 듯함` | `confirming_safety_status` |
| CF21 | `unknown` | 모두 공란 | 일반 A/S 경로 |
| CF22 | `provide_details` | `product_type=믹서기`; `symptom=속도 버튼이 눌리지 않음` | 일반 A/S 경로 |
| CF23 | `unknown` | 모두 공란 | 일반 A/S 경로 |
| CF24 | `provide_details` | `product_type=공기청정기`; `symptom=화면이 꺼짐` | 일반 A/S 경로 |
| CF25 | `provide_details` | `product_type=태블릿`; `symptom=충전 속도가 느림` | 일반 A/S 경로 |
| CF26 | `provide_details` | `product_type=모니터`; `symptom=화면이 깜빡임` | 일반 A/S 경로 |
| CF27 | `provide_details` | `product_type=충전기`; `symptom=충전이 간헐적으로 끊김`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| CF28 | `unknown` | 모두 공란 | 일반 A/S 경로 |
| CF29 | `provide_details` | `product_type=게임기`; `symptom=화면에 불꽃 모양 아이콘이 표시되고 화면이 멈춤`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| CF30 | `provide_details` | `product_type=헤어드라이어`; `symptom=바람 세기가 약해짐` | 일반 A/S 경로 |
| CF31 | `provide_details` | `product_type=노트북`; `symptom=팬 소음이 커짐`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| CF32 | `provide_details` | `symptom=전원 버튼이 반응하지 않음` | 일반 A/S 경로 |

## 확인이 필요한 해석

- CF04는 A/S 대상을 제품 전체가 아닌 `전동 공구 배터리`로 제안했다.
- CF13–CF20은 관찰된 현상과 위험 확정을 구분해 `safety_status=null`로 둔다. CF16·CF18은 냄새의 출처가 제품인지 불확실해 `symptom`도 공란이다.
- CF21·CF23·CF28은 각각 확인 방법, 가정형 조치, 수리비가 주된 요청이므로 현재 접수 업무의 `unknown`·모든 필드 공란으로 제안했다.
- CF27·CF29·CF31은 현재 제품에서 특정 위험이 없다고 명시해 `no_safety_issue`를 제안했다. 다른 제품·자료·출처에 관한 위험 언급만으로 이 값을 채우지 않는다.
- CF01–CF12의 직접 보호 상태와 CF13–CF20의 확인 상태를 분리해 집계한다. 확인 질문을 띄운 횟수를 위험 탐지 성공으로 자동 합산하지 않는다.
