# Kanana 1.5 2.1B Instruct ai_message Only Test

## Model

- kakaocorp/kanana-1.5-2.1b-instruct-2505

## Runtime

- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario

- 병원 예약 전화

## Purpose

4차 테스트에서는 LLM에게 완성 JSON 전체를 생성하게 하지 않고, 병원 접수 직원의 자연어 응답인 `ai_message`만 생성하도록 테스트했다.

Kanana 1.5 2.1B Instruct는 이전 테스트에서 한국어 전화 응대 말투가 가장 자연스러웠기 때문에 메인 후보로 재평가했다.

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
네, 내일 오후에는 진료 예약이 가능합니다. 원하시는 진료과도 알려주시면 더 정확히 안내해 드릴 수 있습니다.
```

---

## Latency

```text
1.73s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| 한 문장 출력 | 4/5 | 한 문장에 가깝게 출력되었으나 내용이 조금 긴 편임 |
| 병원 접수 말투 | 4/5 | 자연스럽고 공손한 접수 직원 말투에 가까움 |
| 다음 정보 요청 | 5/5 | 필요한 정보인 진료과를 자연스럽게 요청함 |
| 예약 확정 방지 | 2/5 | “진료 예약이 가능합니다”라고 가능 여부를 확정함 |
| 전화 공포증 배려 | 4/5 | 압박감이 적고 부드러운 표현을 사용함 |
| 응답 속도 | 5/5 | 1.73초로 매우 빠름 |

---

## Interpretation

Kanana 1.5 2.1B Instruct는 `ai_message`만 생성하도록 역할을 제한했을 때 이전 테스트보다 훨씬 안정적인 결과를 보였다.

완성 JSON을 직접 생성하게 했던 테스트에서는 JSON 중간 잘림이나 `recommended_replies` 역할 혼동 문제가 있었지만, 자연어 응답만 생성하도록 하자 병원 접수 직원 말투를 안정적으로 생성했다.

특히 사용자가 아직 말하지 않은 진료과 정보를 부드럽게 요청하는 흐름이 좋았다.

다만 `"내일 오후에는 진료 예약이 가능합니다"`라는 표현은 실제 예약 가능 여부를 조회하지 않은 상태에서 가능하다고 확정하는 표현이다. 따라서 다음 프롬프트에서는 확정 표현을 금지하고 `"확인해드리겠습니다"` 중심으로 답하도록 조정해야 한다.

---

## Decision

```text
- Main ai_message candidate
- Best Korean phone response quality
- Needs stronger prompt to avoid confirming availability
```

---

## Notes

- 한국어 전화 응대 말투는 가장 자연스러운 편이다.
- `ai_message`만 생성하게 하면 출력 안정성이 크게 개선된다.
- 최종 서비스에서는 Kanana가 `ai_message`를 생성하고, FastAPI가 추천 답변과 상태값을 조립하는 구조가 적합하다.

---

# Retest: Availability Confirmation Restriction

## Purpose

기존 4차 ai_message 전용 테스트에서 Kanana 1.5 2.1B Instruct는 자연스러운 병원 접수 직원 말투를 생성했지만, `"내일 오후에는 진료 예약이 가능합니다"`처럼 실제 예약 가능 여부를 확정하는 표현이 포함되었다.

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
네, 내일 오후에 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 바로 확인해드리겠습니다.
```

---

## Latency

```text
1.80s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| 예약 확정 방지 | 5/5 | 예약 가능 여부를 확정하지 않고 확인 흐름으로 응답함 |
| 병원 접수 말투 | 5/5 | 자연스럽고 공손한 접수 직원 말투에 가까움 |
| 다음 정보 요청 | 5/5 | 필요한 정보인 진료과를 자연스럽게 요청함 |
| 전화 공포증 배려 | 5/5 | 사용자의 요청을 먼저 받아주고 부드럽게 다음 정보를 요청함 |
| 응답 속도 | 5/5 | 1.80초로 충분히 빠름 |
| 출력 안정성 | 5/5 | JSON, markdown, 역할 이름 없이 자연어 응답만 출력함 |

---

## Interpretation

재테스트 결과, Kanana 1.5 2.1B Instruct는 개선된 프롬프트를 잘 따랐다.

기존 출력에서는 예약 가능 여부를 확정하는 표현이 포함되었지만, 이번에는 `"원하시는 진료과를 알려주시면 바로 확인해드리겠습니다"`라는 확인 중심 표현을 생성했다.

또한 사용자의 요청을 먼저 받아준 뒤 필요한 정보를 요청하는 흐름이 자연스럽고, 전화 공포증 사용자가 부담을 느끼지 않도록 부드럽게 응답했다.

---

## Decision

```text
- Main ai_message candidate
- Best Korean phone response quality
- Suitable for LangGraph + FastAPI response assembly structure
```