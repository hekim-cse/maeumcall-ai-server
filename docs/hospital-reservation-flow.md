# Hospital Reservation Flow

이 문서는 병원 예약 시나리오의 LangGraph 상태 흐름을 정리한다.

---

## 전체 상태 목록

병원 예약 시나리오는 다음 상태를 사용한다.

- greeting
- asking_purpose
- asking_department
- asking_date
- asking_time
- confirming_info
- checking_availability
- reservation_available
- reservation_unavailable
- suggest_alternative
- reservation_confirmed
- closing
- END

---

## 기본 흐름

정상 예약 가능 흐름은 다음과 같다.

1. greeting
2. asking_department
3. confirming_info
4. checking_availability
5. reservation_available
6. reservation_confirmed
7. closing
8. END

예시:

- 사용자: 내일 오후에 진료 예약 가능할까요?
- 서버: 원하시는 진료과를 알려주시겠어요?
- 사용자: 내과 진료를 예약하고 싶습니다.
- 서버: 내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?
- 사용자: 네, 맞습니다.
- 서버: 예약 가능 여부를 확인해보겠습니다.
- 사용자: 네, 기다리겠습니다.
- 서버: 내일 오후 3시에 예약 가능합니다.
- 사용자: 네, 그 시간으로 예약하고 싶습니다.
- 서버: 예약이 완료되었습니다.
- 사용자: 감사합니다.
- 서버: 통화를 마무리합니다.

---

## 예약 불가 흐름

요청한 시간대에 예약이 어려운 경우 다음 흐름을 사용한다.

1. checking_availability
2. reservation_unavailable
3. suggest_alternative
4. reservation_confirmed
5. closing
6. END

예시:

- 서버: 내일 오후에는 예약이 어렵습니다. 대신 오후 4시 또는 오후 5시는 가능합니다.
- 사용자: 다른 시간도 가능할까요?
- 서버: 오후 4시와 오후 5시 중에서 선택해주시겠어요?
- 사용자: 오후 4시로 하겠습니다.
- 서버: 내일 오후 4시 내과 진료 예약이 완료되었습니다.

---

## 날짜 변경 흐름

예약 불가 상태에서 사용자가 다른 날짜를 명시하면 asking_date로 바로 전이한다.

예시:

- 현재 상태: reservation_unavailable
- 사용자: 다른 날짜로 확인해주세요.
- user_action: change_date
- 다음 상태: asking_date

이 정책은 사용자가 날짜 변경을 원했는데도 기존 날짜의 대안 시간 선택을 반복하는 문제를 방지하기 위한 것이다.

---

## 대안 시간 방어 흐름

서버가 안내한 대안 시간 목록에 없는 시간을 사용자가 선택하면 예약을 확정하지 않는다.

예시:

- 대안 시간: 오후 4시, 오후 5시
- 사용자: 오후 7시로 하겠습니다.

처리 결과:

- selected_time: None
- conversation_state: suggest_alternative
- reservation_confirmed: None

---

## user_action 목록

현재 병원 예약 시나리오에서 사용하는 주요 user_action은 다음과 같다.

- confirm_reservation_info
- change_department
- change_date
- change_time
- lookup_availability
- confirm_available_time
- ask_other_time
- select_alternative_time
- go_closing
- end_call
- unknown

---

## parser와 graph의 역할

### action parser

사용자 발화를 분석하여 다음 값을 반환한다.

- user_action
- selected_time

### graph

parser 결과를 기준으로 상태 전이를 수행한다.

graph의 역할은 다음과 같다.

- 현재 상태 확인
- user_action에 따른 다음 상태 결정
- 예약 가능 여부 처리
- 대안 시간 검증
- 예약 확정 여부 결정
- 통화 종료 여부 결정


---

## 날짜 변경 시 예약 조회 결과 초기화

예약 불가 상태에서 사용자가 다른 날짜를 요청하면 기존 예약 조회 결과를 초기화한다.

예시 흐름:

- 현재 상태: reservation_unavailable
- 기존 대안 시간: 오후 4시, 오후 5시
- 사용자 입력: 다른 날짜로 확인해주세요.
- 다음 상태: asking_date

이때 다음 값은 초기화된다.

- availability_status
- availability_reason
- available_time
- alternative_times
- availability_message_hint
- selected_time
- reservation_confirmed
- simulation_result

이 정책은 이전 날짜의 예약 불가 결과가 새 날짜 예약 흐름에 남는 문제를 방지하기 위한 것이다.


---

## 날짜 변경 시 시간 조건 초기화

사용자가 예약 날짜를 변경하는 경우 기존 시간 조건도 함께 초기화한다.

예시 흐름:

- 현재 상태: confirming_info 또는 reservation_unavailable
- 기존 날짜: 내일
- 기존 시간: 오후
- 사용자 입력: 날짜를 다시 정하고 싶어요.
- 다음 상태: asking_date
- time: None

이후 사용자가 새 날짜를 입력하면 기존 시간이 없는 상태이므로 asking_time으로 전이한다.

예시 흐름:

- 현재 상태: asking_date
- 사용자 입력: 모레로 확인해주세요.
- 다음 상태: asking_time

이 정책은 날짜가 바뀌었는데 이전 시간 조건이 새 날짜에 그대로 적용되는 문제를 방지하기 위한 것이다.

단, 날짜 변경이 아닌 다음 흐름에서는 기존 time 값을 유지한다.

- 초기 예약 발화에서 시간 정보가 추출된 경우
- 잘못된 대안 시간을 선택한 경우
- 진료과만 변경한 경우


---

## 정형 상태 Template-first 응답 정책

일부 상태는 LLM이 문장을 새로 생성하지 않아도 정형 응답으로 충분하다.

현재 template-first 대상 상태는 다음과 같다.

- checking_availability
- closing
- END

각 상태의 역할은 다음과 같다.

- checking_availability: 예약 가능 여부를 확인 중임을 안내한다.
- closing: 추가 문의가 없으면 통화를 마무리하겠다고 안내한다.
- END: 최종 종료 문장을 반환하고 should_end_call을 True로 설정한다.

이 정책을 적용한 이유는 다음과 같다.

- 정형 문장 상태에서 불필요한 LLM 호출을 줄인다.
- 빈 응답 또는 부적절한 LLM 응답 가능성을 줄인다.
- retry/fallback 발생 빈도를 줄인다.
- 실제 Flutter 통화 UX에서 응답 속도를 개선한다.


---

## 예약 완료 상태 Template-first 응답 정책

reservation_confirmed 상태는 LLM 호출 없이 template/fallback 응답을 우선 사용한다.

예약 완료 상태의 응답은 다음과 같이 서버 상태값을 기반으로 생성한다.

- date
- department
- selected_time
- available_time
- time

시간 값은 selected_time을 우선 사용한다.

우선순위:

- selected_time
- available_time
- time

예시:

- selected_time: 오후 4시
- department: 내과
- date: 내일
- 응답: 네, 내일 오후 4시 내과 진료 예약이 완료되었습니다.

이 정책을 적용한 이유는 다음과 같다.

- 예약 완료 문장은 정형 문장으로 충분하다.
- LLM이 잘못된 시간을 생성하는 위험을 줄인다.
- LLM이 예약 완료 표현을 중복 생성하는 위험을 줄인다.
- selected_time 우선 사용 정책을 안정적으로 보장한다.
- 예약 완료 상태의 응답 속도와 안정성을 높인다.
