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

- 28 passed

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

- 18 passed

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

- 46 passed

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
