# Implementation Log

이 문서는 병원 예약 시나리오 구현 과정을 요약한다.

상세 개발 기록은 Notion에서 관리하고, GitHub에는 구현 차수별 핵심 결과만 정리한다.

---

## 1차 구현 - LangGraph 상태 흐름 적용

병원 예약 시나리오에 LangGraph 기반 상태 흐름을 적용하였다.

핵심 내용:

- 병원 예약 상태 정의
- greeting, asking_department, asking_date, asking_time, confirming_info 등 기본 상태 구성
- 사용자 입력에서 진료과, 날짜, 시간 추출
- 상태에 따라 다음 질문 생성

---

## 2차 구현 - Kanana 1.5 Provider 연결 및 응답 보정

Kanana 1.5 Hugging Face 모델을 서버 응답 생성 흐름에 연결하였다.

핵심 내용:

- Hugging Face provider 연결
- ai_message 생성
- 상태별 prompt 구성
- 모델 응답 후처리
- 잘못된 응답을 fallback으로 보정

---

## 3차 구현 - History 기반 LLM 검증 및 Retry 흐름 추가

LLM 응답 안정성을 높이기 위해 history 기반 검증과 retry 흐름을 추가하였다.

핵심 내용:

- 최근 대화 history를 prompt에 반영
- last_ai_message 기반 반복 응답 방지
- 상태별 응답 validator 적용
- LLM 1차 응답 실패 시 retry
- retry 실패 시 fallback 응답 사용

---

## 4차 구현 - 예약 가능 여부 시뮬레이션 흐름 추가

병원 예약에서 실제 예약 가능 여부를 시뮬레이션하는 흐름을 추가하였다.

핵심 내용:

- checking_availability 상태 추가
- 예약 가능/불가능 상태 분리
- reservation_available 흐름 추가
- reservation_unavailable 흐름 추가
- available_time, alternative_times 관리

---

## 5차 구현 - user_action 기반 상태 전이 리팩토링

상태 전이를 사용자 발화 원문이 아니라 user_action 기반으로 처리하도록 구조를 개선하였다.

핵심 내용:

- hospital_reservation_action_parser.py 추가
- 사용자 발화를 user_action으로 변환
- parse_user_action 노드 추가
- decide_next_state_node()가 user_action 기준으로 동작하도록 수정
- 대안 시간 선택 시 selected_time 저장

---

## 6차 구현 - 상태 검증 분리 및 대안 시간 방어 강화

LLM 응답 검증과 시간 검증 로직을 분리하였다.

핵심 내용:

- hospital_reservation_validator.py 분리
- reservation_time_utils.py 분리
- 상태별 응답 검증 함수 정리
- 대안 목록 외 시간 선택 방어
- selected_time 우선 사용 규칙 정리

---

## 7차 구현 - action parser 테스트 추가 및 구조 안정화

action parser를 단위 테스트로 검증하였다.

핵심 내용:

- tests/test_hospital_reservation_action_parser.py 추가
- 기본 action parser 테스트 18개 추가
- 실제 사용자 표현 기반 예외 케이스 추가
- reservation_available 상태에서 확정/다른 시간 요청 오분류 수정
- action parser 테스트 27개 통과

---

## 8차 구현 - action parser 구조 정리 및 통합 테스트 확장

action parser 구조를 정리하고 graph flow 통합 테스트를 추가하였다.

핵심 내용:

- action parser 키워드 상수 분리
- 상태별 parser 함수 분리
- tests/test_hospital_reservation_graph_flow.py 추가
- 정상 예약 흐름 통합 테스트
- 예약 불가 후 대안 시간 선택 통합 테스트
- 대안 목록 외 시간 선택 방어 통합 테스트
- 확인 단계의 시간/날짜/진료과 변경 흐름 테스트
- unknown 응답 상태 유지 테스트
- 전체 테스트 37개 통과

---

## 정책 개선 - 예약 불가 상태의 날짜 변경 전이 처리

예약 불가 상태에서 사용자가 다른 날짜를 요청하는 흐름을 개선하였다.

핵심 내용:

- reservation_unavailable 상태에서 날짜 변경 의도 감지
- 다른 날짜 요청 시 asking_date로 바로 전이
- 다른 시간 요청은 기존처럼 suggest_alternative 유지
- action parser 테스트 28개 통과
- graph flow 통합 테스트 10개 통과
- 전체 테스트 38개 통과

---

## 다음 작업

다음 작업 후보는 다음과 같다.

- reservation_unavailable → asking_date → 새 날짜 입력 흐름 테스트
- 날짜 변경 시 기존 시간 정보 유지 여부 정책 정리
- 날짜 변경 후 예약 가능 여부 재조회 흐름 검증
- Flutter 연동용 /chat API 저장 규칙 정리
- Flutter에서 conversationState, scenarioState, history 저장 구조 구현


---

## 정책 개선 - 날짜 변경 시 예약 조회 상태 초기화

예약 불가 상태에서 사용자가 다른 날짜를 요청하는 경우, 이전 예약 조회 결과가 새 날짜 흐름에 남지 않도록 초기화 처리를 추가하였다.

핵심 내용:

- clear_reservation_lookup_fields() 추가
- change_date 전이 시 예약 조회 관련 상태 초기화
- reservation_unavailable → asking_date 전이 시 이전 대안 시간 제거
- selected_time, reservation_confirmed, simulation_result 초기화
- 날짜 변경 초기화 graph flow 테스트 추가

검증 결과:

- action parser 단위 테스트: 28 passed
- graph flow 통합 테스트: 11 passed
- 전체 병원 예약 테스트: 39 passed


---

## 정책 개선 - 날짜 변경 시 시간 조건 초기화

날짜 변경 흐름에서 기존 시간 조건이 새 날짜에 그대로 남지 않도록 time 초기화 처리를 추가하였다.

핵심 내용:

- change_date 전이 시 기존 time 값 초기화
- confirming_info → change_date → asking_date 흐름에서 time 초기화
- reservation_unavailable → change_date → asking_date 흐름에서 time 초기화
- suggest_alternative → change_date → asking_date 흐름에서 time 초기화
- 날짜 변경 후 새 날짜 입력 시 asking_time으로 이동하는 테스트 추가
- 날짜 변경이 아닌 흐름에서는 기존 time 값을 유지하도록 테스트 기대값 정리

검증 결과:

- action parser 단위 테스트: 28 passed
- graph flow 통합 테스트: 13 passed
- 전체 병원 예약 테스트: 41 passed


---

## 리팩토링 - 정형 상태 응답 생성 안정화

정형 문장으로 충분한 상태에서는 LLM 호출 없이 template/fallback 응답을 우선 사용하도록 개선하였다.

핵심 내용:

- should_use_template_first() 추가
- checking_availability 상태에서 template-first 응답 사용
- closing 상태에서 template-first 응답 사용
- END 상태에서 template-first 응답 사용
- 정형 상태에서 complete_hf_messages가 호출되지 않는지 테스트 추가
- END 상태에서는 should_end_call을 True로 반환하도록 유지

기대 효과:

- 응답 속도 개선
- 불필요한 Kanana 호출 감소
- 빈 응답 및 부적절한 응답 가능성 감소
- retry/fallback 빈도 감소
- Flutter 실시간 통화 UX 안정성 개선

검증 결과:

- action parser 단위 테스트: 28 passed
- graph flow 통합 테스트: 16 passed
- 전체 병원 예약 테스트: 44 passed
