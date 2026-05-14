# EXAONE-4.0-1.2B ai_message Only Test

## Model

- LGAI-EXAONE/EXAONE-4.0-1.2B

## Runtime

- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario

- 병원 예약 전화

## Purpose

4차 테스트에서는 LLM에게 완성 JSON 전체를 생성하게 하지 않고, 병원 접수 직원의 자연어 응답인 `ai_message`만 생성하도록 테스트했다.

EXAONE-4.0-1.2B는 이전 테스트에서 응답 속도가 가장 빨랐기 때문에 속도 baseline 후보로 재평가했다.

---

## Test Condition

| 항목 | 값 |
|---|---|
| Prompt | ai_message only prompt |
| max_new_tokens | 60 |
| do_sample | False |
| repetition_penalty | 1.1 |

---

## Generated Output

```text
"네, 가능합니다! 어떤 진료과를 원하시나요?"
```

---

## Latency

```text
0.77s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| 한 문장 출력 | 5/5 | 짧고 명확한 한 문장으로 출력됨 |
| 병원 접수 말투 | 3/5 | 의미는 적절하지만 느낌표와 표현이 다소 가볍게 느껴짐 |
| 다음 정보 요청 | 5/5 | 필요한 정보인 진료과를 물어봄 |
| 예약 확정 방지 | 2/5 | “가능합니다”라고 예약 가능 여부를 확정함 |
| 전화 공포증 배려 | 3/5 | 짧고 명확하지만 Kanana보다 부드러움은 약함 |
| 응답 속도 | 5/5 | 0.77초로 가장 빠름 |

---

## Interpretation

EXAONE-4.0-1.2B는 4차 테스트에서 가장 빠른 응답 속도를 보였다.

이전 테스트에서는 완성 JSON을 생성하는 과정에서 쉼표 누락, 영어 혼합, JSON 중간 잘림 등의 문제가 있었지만, `ai_message`만 생성하도록 역할을 제한하자 출력 안정성이 개선되었다.

다만 출력에 따옴표가 포함되었고, `"가능합니다!"`처럼 예약 가능 여부를 확정하는 표현이 포함되었다. 또한 병원 접수 직원 말투로는 Kanana보다 다소 가볍게 느껴질 수 있다.

---

## Decision

```text
- Keep as speed baseline
- Very fast response
- Needs tone refinement
- Needs stronger prompt to avoid confirming availability
```

---

## Notes

- 응답 속도는 현재까지 가장 우수하다.
- `ai_message`만 생성하도록 하면 출력 안정성은 크게 개선된다.
- 다만 한국어 병원 접수 말투는 Kanana보다 약하다.
- 최종 후보보다는 속도 baseline 또는 fallback 후보로 유지한다.

---

# Retest: Availability Confirmation Restriction

## Purpose

기존 4차 ai_message 전용 테스트에서 EXAONE-4.0-1.2B는 매우 빠른 응답 속도를 보였지만, `"네, 가능합니다!"`처럼 실제 예약 가능 여부를 확정하는 표현이 포함되었다.

이번 재테스트에서는 병원의 실제 예약 가능 여부가 아직 조회되지 않았다는 조건을 추가하고, `"가능합니다"`, `"예약 가능합니다"`, `"예약해드리겠습니다"` 같은 확정 표현을 금지했다.

---

## Updated Prompt Direction

```text
- 병원의 실제 예약 가능 여부는 아직 조회되지 않았다.
- 예약 가능 여부를 확정하지 않는다.
- "가능합니다", "예약 가능합니다", "예약해드리겠습니다" 표현을 사용하지 않는다.
- "확인해드리겠습니다" 중심으로 응답한다.
- 원하시는 진료과를 부드럽게 물어본다.
```

---

## Generated Output

```text
"확인해드리겠습니다. 어떤 진료과를 원하시는지 말씀해주시겠어요?"
```

---

## Latency

```text
1.22s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| 예약 확정 방지 | 5/5 | 예약 가능 여부를 확정하지 않음 |
| 병원 접수 말투 | 4/5 | 의미는 자연스럽지만 Kanana보다 조금 덜 부드러움 |
| 다음 정보 요청 | 5/5 | 필요한 정보인 진료과를 정확히 요청함 |
| 전화 공포증 배려 | 4/5 | 짧고 명확하지만 Kanana보다 정서적 완충은 약함 |
| 응답 속도 | 5/5 | 1.22초로 매우 빠름 |
| 출력 안정성 | 4/5 | 자연어 응답만 출력했으나 앞뒤 따옴표가 포함됨 |

---

## Interpretation

재테스트 결과, EXAONE-4.0-1.2B는 개선된 프롬프트에서 예약 가능 여부를 확정하지 않고 진료과를 묻는 응답을 생성했다.

응답 시간은 1.22초로 매우 빠르며, 속도 baseline 또는 fallback 후보로 가치가 높다.

다만 출력에 따옴표가 포함되었기 때문에 실제 서비스 적용 시 간단한 후처리가 필요하다.

```python
ai_message = ai_message.strip().strip('"')
```

또한 병원 접수 직원 말투의 자연스러움과 부드러움은 Kanana보다 조금 낮다.

---

## Decision

```text
- Keep as speed baseline
- Good fallback candidate
- Needs simple quote post-processing
```