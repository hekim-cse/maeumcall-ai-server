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


---

## 예약 가능 상태 Template-first 응답 정책

reservation_available 상태는 LLM 호출 없이 template/fallback 응답을 우선 사용한다.

예약 가능 상태의 응답은 다음과 같이 서버 상태값을 기반으로 생성한다.

- date
- department
- available_time
- selected_time
- time

시간 값은 예약 가능 여부 조회 결과에서 반환된 available_time을 우선 사용한다.

우선순위:

- selected_time
- available_time
- time

예시:

- available_time: 오후 3시
- department: 내과
- date: 내일
- 응답: 확인 결과, 내일 오후 3시에 내과 진료 예약이 가능합니다. 이 시간으로 진행해드릴까요?

이 정책을 적용한 이유는 다음과 같다.

- 예약 가능 안내 문장은 정형 문장으로 충분하다.
- LLM이 없는 시간을 생성하는 위험을 줄인다.
- 서버의 예약 가능 여부 시뮬레이션 결과를 그대로 반영한다.
- available_time 기반 안내를 안정적으로 보장한다.
- template-first 응답을 사용하더라도 recommended_replies는 기존처럼 유지한다.


---

## Template 응답 생성과 Fallback 응답 생성 역할 분리

정형 상태에서 의도적으로 사용하는 template 응답과, LLM 실패 시 사용하는 fallback 응답의 역할을 분리하였다.

기존 구조:

- template-first 상태도 fallback_ai_message() 사용
- LLM 응답 실패 시에도 fallback_ai_message() 사용

개선 구조:

- template-first 상태: build_template_ai_message() 사용
- LLM 실패 또는 검증 실패: fallback_ai_message() 사용

각 함수의 역할은 다음과 같다.

- build_template_ai_message(): 서버 상태값을 기반으로 정형 상태 응답을 생성한다.
- fallback_ai_message(): LLM 응답이 비어 있거나 검증에 실패했을 때 최후 안전 응답을 생성한다.

이 구조를 적용한 이유는 다음과 같다.

- template-first 응답과 fallback 응답의 의미를 명확히 구분한다.
- 코드 가독성을 높인다.
- 로그에서 응답 출처를 더 명확하게 해석할 수 있다.
- 이후 template 응답만 별도 고도화하기 쉬운 구조를 만든다.


---

## Template-first 상태별 응답 생성 구조

template-first 대상 상태는 build_template_ai_message()에서 상태별 template 응답을 직접 생성한다.

현재 template-first 대상 상태는 다음과 같다.

- checking_availability
- reservation_available
- reservation_confirmed
- closing
- END

각 상태의 응답 생성 기준은 다음과 같다.

- checking_availability: 예약 가능 여부 확인 중임을 안내한다.
- reservation_available: available_time 기반 예약 가능 안내를 생성한다.
- reservation_confirmed: selected_time 또는 available_time 기반 예약 완료 안내를 생성한다.
- closing: 추가 문의가 없으면 통화를 마무리하겠다고 안내한다.
- END: 최종 종료 문장을 반환한다.

이 구조를 적용한 이유는 다음과 같다.

- template-first 응답을 LLM 실패 fallback과 분리한다.
- 정형 상태 응답을 서버 상태값 기반으로 안정적으로 생성한다.
- 예약 시간 hallucination 가능성을 줄인다.
- 상태별 응답 문장을 이후 독립적으로 개선할 수 있게 한다.


---

## 시간 질문 상태 Template-first 응답 정책

asking_time 상태는 LLM 호출 없이 template 응답을 우선 사용한다.

asking_time 상태의 역할은 사용자가 원하는 예약 시간 또는 시간대를 확인하는 것이다.

응답 예시:

- 네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?
- 네, 내일 예약으로 확인했습니다. 편하신 시간대가 있으실까요?
- 네, 내일에 진료를 원하시는군요. 원하시는 시간을 알려주시겠어요?

이 정책을 적용한 이유는 다음과 같다.

- 시간 질문은 정형 문장으로 충분하다.
- 한 번에 연락처나 성함을 같이 묻지 않도록 한다.
- LLM이 상태 범위를 벗어난 질문을 생성하는 위험을 줄인다.
- TTS에서 읽기 좋은 짧은 문장을 유지한다.
- 날짜/시간 수집 흐름을 단계별로 안정화한다.

현재 MVP에서는 성함과 연락처를 수집하지 않고, 진료과/날짜/시간 기반 예약 시뮬레이션 흐름을 유지한다.


---

## 진료과 질문 상태 Template-first 응답 정책

asking_department 상태는 LLM 호출 없이 template 응답을 우선 사용한다.

asking_department 상태의 역할은 사용자가 원하는 진료과를 확인하는 것이다.

응답 예시:

- 네, 확인해드리겠습니다. 원하시는 진료과를 말씀해주시겠어요?
- 네, 진료 예약을 원하시는군요. 진료받으실 과를 알려주시겠어요?
- 네, 확인 도와드리겠습니다. 원하시는 진료과가 있으실까요?

사용자가 이미 날짜와 시간을 말한 경우에는 해당 정보를 반영한다.

응답 예시:

- 네, 내일 오후 진료 예약을 원하시는군요. 원하시는 진료과를 말씀해주시겠어요?
- 네, 내일 오후 예약 문의로 확인했습니다. 진료받으실 과를 알려주시겠어요?

이 정책을 적용한 이유는 다음과 같다.

- 진료과 질문은 정형 문장으로 충분하다.
- 한 번에 연락처나 성함을 같이 묻지 않도록 한다.
- LLM이 MVP 범위를 벗어난 질문을 생성하는 위험을 줄인다.
- TTS에서 읽기 좋은 짧은 문장을 유지한다.
- 진료과/날짜/시간 수집 흐름을 단계별로 안정화한다.

현재 MVP에서는 성함과 연락처를 수집하지 않고, 진료과/날짜/시간 기반 예약 시뮬레이션 흐름을 유지한다.


---

## 예약 확인 추천 답변 MVP 범위 정책

현재 병원 예약 MVP에서는 성함과 연락처를 수집하지 않는다.

예약 시뮬레이션은 다음 정보만 기반으로 진행한다.

- 진료과
- 예약 날짜
- 예약 시간

따라서 confirming_info 상태의 추천 답변은 예약 조건 확인과 변경에 집중한다.

현재 confirming_info 추천 답변 예시는 다음과 같다.

- 네, 맞습니다.
- 시간을 다시 확인하고 싶습니다.
- 날짜를 다시 확인하고 싶습니다.

이 정책을 적용한 이유는 다음과 같다.

- 현재 MVP 범위를 진료과/날짜/시간 기반 예약 시뮬레이션으로 유지한다.
- 추천 답변 버튼에서 성함/연락처 입력 흐름으로 잘못 이어지는 문제를 방지한다.
- TTS 및 버튼 UI에서 사용자에게 불필요한 개인정보 입력 부담을 주지 않는다.
- 추후 실제 병원 접수 흐름 확장 시 asking_name, asking_phone 상태를 별도로 추가할 수 있게 한다.
