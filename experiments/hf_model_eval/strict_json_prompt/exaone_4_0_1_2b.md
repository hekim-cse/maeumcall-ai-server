# EXAONE-4.0-1.2B Strict JSON Prompt Test

## Model
- LGAI-EXAONE/EXAONE-4.0-1.2B

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
3차 테스트에서는 짧고 강한 Strict JSON Prompt를 사용하여 EXAONE-4.0-1.2B가 JSON 객체 하나를 안정적으로 생성할 수 있는지 확인했다.

---

## Test Condition

| 항목 | 값 |
|---|---|
| Prompt | Strict JSON Prompt |
| max_new_tokens | 100 |
| do_sample | False |
| repetition_penalty | 1.15 |

---

## Generated Output

```text
```json
{
  "ai_message": "네, 내일 오후에 예약해 드리겠습니다. 몇 시에 가능하시나요?",
  "recommended_replies": [
    "몇 시예요?",
    "아니오, 다른 시간이 되면 okay해요.",
    "다른 시간이 안 될 것 같아요."
  ],
  "conversation_state": "asking_department",
  "should_
```

---

## Latency

```text
3.59s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 1/5 | markdown 코드블록이 포함되었고 JSON이 should_end_call 필드에서 중간에 잘림 |
| 한국어 자연스러움 | 2/5 | “okay해요”처럼 영어가 섞인 표현이 생성됨 |
| 전화 응대 말투 | 2/5 | 예약 가능 여부를 임의로 확정하고 예약해주겠다고 표현함 |
| 추천 답변 품질 | 1/5 | 추천 답변이 사용자 입장으로 자연스럽지 않음 |
| 대화 상태 판단 | 3/5 | conversation_state는 생성되었으나 should_end_call이 잘려 확인 불가 |
| 로컬 실행 속도 | 5/5 | 3.59초로 매우 빠름 |

---

## Interpretation

EXAONE-4.0-1.2B는 3차 테스트에서도 가장 빠른 응답 속도를 보였다.

```text
1차 응답 시간: 3.86초
2차 응답 시간: 3.72초
3차 응답 시간: 3.59초
```

그러나 출력 품질은 안정적이지 않았다.  
JSON이 끝까지 완성되지 않았고, markdown 코드블록이 포함되었으며, `"okay해요"`처럼 영어가 섞인 표현이 생성되었다.

또한 `"예약해 드리겠습니다"`라는 표현은 현재 입력에 없는 예약 가능 여부를 확정하는 말이므로, 통제된 테스트 기준에서는 적절하지 않다.

---

## Decision

```text
- Keep as speed baseline
- Not stable enough for direct JSON generation
- Needs server-side post-processing
```

---

## Notes

- 속도는 가장 우수하다.
- 그러나 JSON 생성 안정성이 낮다.
- 한국어 전화 응대 품질도 EXAONE 단독으로는 불안정하다.
- 최종 서비스에서는 EXAONE을 사용하더라도 JSON 직접 생성보다는 서버 후처리 구조가 필요하다.