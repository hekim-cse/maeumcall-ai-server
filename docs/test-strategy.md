# Test Strategy

이 문서는 병원 예약 시나리오의 테스트 전략을 정리한다.

---

## 테스트 목적

병원 예약 시나리오는 LLM 응답 생성과 LangGraph 상태 전이가 함께 동작한다.

하지만 LLM 응답은 매번 달라질 수 있으므로, 테스트에서는 다음 영역을 분리해서 검증한다.

- action parser 단위 테스트
- LangGraph 상태 전이 통합 테스트
- 대안 시간 검증
- 예약 확정 여부 검증
- 통화 종료 여부 검증

---

## action parser 단위 테스트

테스트 파일:

- tests/test_hospital_reservation_action_parser.py

검증 대상:

- 사용자 발화가 올바른 user_action으로 분류되는지 확인
- 사용자가 말한 시간이 selected_time으로 추출되는지 확인
- 실제 사용자 표현 기반 예외 케이스 검증

현재 테스트 결과:

- 31 passed

주요 검증 케이스:

- confirming_info 상태에서 확인/시간 변경/날짜 변경/진료과 변경
- reservation_available 상태에서 확정/다른 시간 요청 구분
- reservation_unavailable 상태에서 다른 시간 요청/다른 날짜 요청 구분
- suggest_alternative 상태에서 대안 시간 선택/다른 날짜 요청/다른 시간 요청 구분
- closing 상태에서 통화 종료 처리

---

## graph flow 통합 테스트

테스트 파일:

- tests/test_hospital_reservation_graph_flow.py

검증 대상:

- 병원 예약 전체 상태 흐름
- 정상 예약 완료 흐름
- 예약 불가 후 대안 시간 선택 흐름
- 대안 목록 외 시간 선택 방어 흐름
- 예약 정보 확인 단계에서 날짜/시간/진료과 변경 흐름
- unknown 응답 시 상태 유지

현재 테스트 결과:

- 22 passed

---

## LLM mock 처리

통합 테스트에서는 LLM 응답이 매번 달라지는 문제를 막기 위해 complete_hf_messages()를 mock 처리한다.

목적:

- LLM 생성 결과가 아닌 graph 상태 전이 자체 검증
- 테스트 결과 재현성 확보
- fallback 응답 기반 안정적인 테스트 수행

---

## 전체 테스트 실행

action parser와 graph flow 테스트를 함께 실행한다.

명령어:

    python -m pytest tests/test_hospital_reservation_action_parser.py tests/test_hospital_reservation_graph_flow.py -v

현재 결과:

- 50 passed

---

## 경고 처리

테스트 실행 중 다음 경고가 발생할 수 있다.

- NotOpenSSLWarning
- LangChainPendingDeprecationWarning

현재 경고는 기능 실패와 관련 없는 환경 및 라이브러리 경고이다.

테스트 실패 여부는 passed / failed 결과를 기준으로 판단한다.


---

## 날짜 변경 초기화 테스트

예약 불가 상태에서 사용자가 다른 날짜를 요청하면 기존 예약 조회 결과가 새 날짜 흐름에 남지 않아야 한다.

검증 대상:

- reservation_unavailable 상태에서 change_date 감지
- asking_date 상태로 전이
- availability_status 초기화
- availability_reason 초기화
- available_time 초기화
- alternative_times 빈 배열 처리
- availability_message_hint 초기화
- selected_time 초기화
- reservation_confirmed 초기화
- simulation_result 초기화

이 테스트는 이전 날짜의 예약 불가 결과가 새 날짜 예약 흐름에 섞이는 문제를 방지하기 위한 것이다.


---

## 날짜 변경 시 시간 조건 초기화 테스트

날짜 변경 흐름에서는 기존 시간 조건이 새 날짜에 그대로 적용되지 않아야 한다.

검증 대상:

- confirming_info 상태에서 change_date 감지
- reservation_unavailable 상태에서 change_date 감지
- asking_date 상태로 전이
- 기존 time 값 초기화
- 새 날짜 입력 후 asking_time 상태로 전이
- 날짜 변경이 아닌 흐름에서는 기존 time 값 유지

이 테스트는 날짜가 바뀌었는데 이전 시간 조건이 그대로 남아 잘못된 예약 확인으로 이어지는 문제를 방지하기 위한 것이다.


---

## Template-first 응답 테스트

일부 상태는 LLM 호출 없이 정형 응답으로 충분하므로 template/fallback 응답을 우선 사용한다.

대상 상태:

- checking_availability
- closing
- END

검증 대상:

- checking_availability 상태에서 LLM을 호출하지 않는지 확인
- closing 상태에서 LLM을 호출하지 않는지 확인
- END 상태에서 LLM을 호출하지 않는지 확인
- 각 상태에서 fallback 기반 응답이 정상 반환되는지 확인
- END 상태에서 should_end_call이 True로 반환되는지 확인

이 테스트는 정형 응답으로 충분한 상태에서 불필요한 LLM 호출을 줄이고, 응답 속도와 안정성을 높이기 위한 것이다.


---

## 예약 완료 상태 Template-first 테스트

reservation_confirmed 상태는 예약 완료 안내 문장으로 충분하므로 LLM 호출 없이 template/fallback 응답을 사용한다.

검증 대상:

- reservation_confirmed 상태에서 LLM을 호출하지 않는지 확인
- 예약 완료 상태에서 fallback 기반 응답이 정상 반환되는지 확인
- selected_time이 존재하면 selected_time을 우선 사용하는지 확인
- available_time이 존재하면 available_time 기반으로 예약 완료 문장이 생성되는지 확인
- 예약 완료 응답에 진료과와 예약 시간이 포함되는지 확인

이 테스트는 예약 완료 상태에서 LLM이 잘못된 시간이나 중복된 예약 완료 표현을 생성하는 문제를 방지하기 위한 것이다.


---

## 예약 가능 상태 Template-first 테스트

reservation_available 상태는 예약 가능 안내 문장으로 충분하므로 LLM 호출 없이 template/fallback 응답을 사용한다.

검증 대상:

- reservation_available 상태에서 LLM을 호출하지 않는지 확인
- available_time이 예약 가능 안내 문장에 포함되는지 확인
- department가 예약 가능 안내 문장에 포함되는지 확인
- 예약 가능 표현이 정상 포함되는지 확인
- template-first 응답을 사용하더라도 recommended_replies가 유지되는지 확인

이 테스트는 예약 가능 상태에서 LLM이 없는 시간을 생성하거나 예약 가능 시간을 잘못 안내하는 문제를 방지하기 위한 것이다.


---

## Template 응답 생성 함수 분리 테스트

template-first 응답 생성과 LLM 실패 fallback 응답 생성을 역할상 분리하였다.

검증 대상:

- build_template_ai_message() 함수가 서버 상태값을 기반으로 응답을 생성하는지 확인
- reservation_available 상태에서 date 값이 응답에 포함되는지 확인
- available_time 값이 응답에 포함되는지 확인
- department 값이 응답에 포함되는지 확인
- 예약 가능 표현이 정상 포함되는지 확인

이 테스트는 template-first 응답이 단순 fallback 실패 처리와 구분되어, 서버 상태값 기반 정형 응답으로 동작하는지 확인하기 위한 것이다.


---

## Template 상태별 응답 로직 테스트

template-first 대상 상태는 fallback 응답을 단순 재사용하지 않고 build_template_ai_message() 내부에서 상태별 template 응답을 직접 생성한다.

검증 대상:

- checking_availability template 응답 생성
- reservation_available template 응답 생성
- reservation_confirmed template 응답 생성
- closing template 응답 생성
- END template 응답 생성
- 각 template 응답이 서버 상태값 또는 상태 목적에 맞는 문장을 반환하는지 확인

이 테스트는 template-first 응답 생성 로직이 LLM 실패 대응 fallback과 구조적으로 분리되어 동작하는지 확인하기 위한 것이다.


---

## 시간 질문 상태 Template-first 테스트

asking_time 상태는 시간을 묻는 정형 질문으로 충분하므로 LLM 호출 없이 template 응답을 사용한다.

검증 대상:

- asking_time 상태에서 LLM을 호출하지 않는지 확인
- 시간 또는 시간대 질문 표현이 포함되는지 확인
- 연락처를 묻지 않는지 확인
- 성함을 묻지 않는지 확인
- should_end_call이 False로 유지되는지 확인
- build_template_ai_message()가 asking_time 상태에서 시간 질문을 생성하는지 확인

이 테스트는 시간 질문 상태에서 LLM이 연락처, 성함 등 불필요한 정보를 함께 묻는 문제를 방지하기 위한 것이다.


---

## 진료과 질문 상태 Template-first 테스트

asking_department 상태는 진료과를 묻는 정형 질문으로 충분하므로 LLM 호출 없이 template 응답을 사용한다.

검증 대상:

- asking_department 상태에서 LLM을 호출하지 않는지 확인
- 진료과 질문 표현이 포함되는지 확인
- 연락처를 묻지 않는지 확인
- 성함을 묻지 않는지 확인
- should_end_call이 False로 유지되는지 확인
- 사용자가 이미 날짜와 시간을 말한 경우 해당 정보를 반영한 진료과 질문을 생성하는지 확인
- build_template_ai_message()가 asking_department 상태에서 진료과 질문을 생성하는지 확인

이 테스트는 진료과 질문 상태에서 LLM이 연락처, 성함 등 MVP 범위를 벗어난 정보를 함께 묻는 문제를 방지하기 위한 것이다.


---

## 예약 확인 추천 답변 MVP 범위 테스트

현재 MVP에서는 성함과 연락처를 수집하지 않고, 진료과/날짜/시간 기반 예약 시뮬레이션 흐름을 유지한다.

따라서 confirming_info 상태의 recommended_replies에는 성함 또는 연락처 관련 문구가 포함되면 안 된다.

검증 대상:

- confirming_info 상태에서 recommended_replies가 정상 반환되는지 확인
- 추천 답변에 연락처 문구가 포함되지 않는지 확인
- 추천 답변에 성함 문구가 포함되지 않는지 확인
- 기본 확인 답변인 “네, 맞습니다.”가 포함되는지 확인
- 시간 변경 관련 답변이 포함되는지 확인
- 날짜 또는 진료과 변경 관련 답변이 포함되는지 확인

이 테스트는 프론트의 추천 답변 버튼이 현재 MVP 범위를 벗어난 개인정보 수집 흐름으로 이어지지 않도록 방지하기 위한 것이다.


---

## 예약 정보 확인 상태 Template-first 테스트

confirming_info 상태는 예약 정보를 확인하는 정형 문장으로 충분하므로 LLM 호출 없이 template 응답을 사용한다.

검증 대상:

- confirming_info 상태에서 LLM을 호출하지 않는지 확인
- 예약 정보 확인 문장에 date 값이 포함되는지 확인
- 예약 정보 확인 문장에 time 값이 포함되는지 확인
- 예약 정보 확인 문장에 department 값이 포함되는지 확인
- 예약 정보 확인 표현이 정상 포함되는지 확인
- should_end_call이 False로 유지되는지 확인
- build_template_ai_message()가 confirming_info 상태에서 서버 상태값 기반 예약 확인 문장을 생성하는지 확인

이 테스트는 예약 정보 확인 상태에서 LLM이 잘못된 날짜, 시간, 진료과를 생성하는 문제를 방지하기 위한 것이다.
