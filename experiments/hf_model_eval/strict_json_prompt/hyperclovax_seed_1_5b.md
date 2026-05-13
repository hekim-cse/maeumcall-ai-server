# HyperCLOVAX-SEED-Text-Instruct-1.5B Strict JSON Prompt Test

## Model
- naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
3차 테스트에서는 짧고 강한 Strict JSON Prompt를 사용하여 HyperCLOVA X SEED 1.5B가 JSON 객체 하나를 안정적으로 생성할 수 있는지 확인했다.

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
  "ai_message": "안녕하세요! 내일은 저희 병원에 예약이 많이 몰리는 날이라 자리가 부족해요. 혹시 다른 날짜를 고려해보실 수 있으신가요?",
  "recommended_replies": ["내일 외에 다른 시간대를 생각해볼게요.", "다른 요일은 어떠세요?", "주말이나 평일에 올 수 있나요?"]
}
```

```json
{
  "ai_message": "안녕하세요! 내일은 저희 병원에 예약이 많이
```

---

## Latency

```text
2.79s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 2/5 | 첫 JSON은 생성했지만 필드 누락, markdown 코드블록, 반복 출력이 발생함 |
| 한국어 자연스러움 | 4/5 | 문장 자체는 자연스럽고 실제 전화 상황처럼 들림 |
| 전화 응대 말투 | 4/5 | 병원 접수 직원 말투에 가까움 |
| 추천 답변 품질 | 3/5 | 일부는 사용자 입장으로 자연스럽지만 일부는 병원 직원 질문처럼 보임 |
| 대화 상태 판단 | 1/5 | conversation_state와 should_end_call 필드가 누락됨 |
| 로컬 실행 속도 | 5/5 | 2.79초로 가장 빠름 |

---

## Interpretation

HyperCLOVA X SEED 1.5B는 3차 테스트에서 가장 빠른 응답 속도를 보였다.

또한 `"예약이 많이 몰리는 날이라 자리가 부족하다"`는 응답은 실제 병원 예약 상황에서는 충분히 자연스러울 수 있다.  
다만 현재 프롬프트에는 병원의 예약 현황 정보가 제공되지 않았기 때문에, 통제된 평가 기준에서는 모델이 상황을 임의로 확장한 것으로 기록한다.

즉, 이 결과는 단순히 잘못된 응답이라기보다 다음과 같이 해석할 수 있다.

```text
- 실제 전화 대화 자연스러움: 긍정적
- 주어진 정보 기반 응답 안정성: 아쉬움
- 상태 기반 시나리오 제어 필요성: 높음
```

하지만 JSON 출력 측면에서는 문제가 남아 있다.  
`conversation_state`, `should_end_call` 필드가 누락되었고, 첫 JSON 이후 다시 JSON을 반복 생성했다.

---

## Decision

```text
- Keep as natural Korean candidate
- Needs state control and post-processing
- Not stable enough for direct JSON generation
```

---

## Notes

- 한국어 문장 자연스러움과 응답 속도는 우수하다.
- 실제 병원 전화 상황처럼 자연스럽게 상황을 확장하는 능력이 있다.
- 그러나 통제된 시나리오에서는 제공되지 않은 상황 정보를 추가할 수 있다.
- JSON 직접 생성 모델보다는 상태 기반 제어와 함께 사용하는 후보로 보는 것이 적절하다.