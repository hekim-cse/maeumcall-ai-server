# Kanana 1.5 2.1B Instruct Strict JSON Prompt Test

## Model
- kakaocorp/kanana-1.5-2.1b-instruct-2505

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
3차 테스트에서는 짧고 강한 Strict JSON Prompt를 사용하여 Kanana 1.5 2.1B Instruct가 JSON 객체 하나를 안정적으로 생성할 수 있는지 확인했다.

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
{
  "ai_message": "내일 오후에 진료 가능한 시간대를 알려드리기 위해, 어떤 진료과(예: 내과, 외과 등)나 특정 날짜가 있으신가요? 또는 원하시는 시간대가 있으신지도 말씀해주시면 더 정확히 안내해드릴 수 있습니다.",
  "recommended_replies": [
    "네, 특별한 진료과 없이 그냥 내일 오후에 아무 때나 �
```

---

## Latency

```text
4.04s
```

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 1/5 | JSON이 recommended_replies에서 중간에 잘려 완성되지 않음 |
| 한국어 자연스러움 | 4/5 | ai_message는 자연스럽고 병원 접수 직원 말투에 가까움 |
| 전화 응대 말투 | 4/5 | 필요한 정보를 묻는 방향은 좋음 |
| 추천 답변 품질 | - | recommended_replies가 중간에 잘려 평가 불가 |
| 대화 상태 판단 | - | conversation_state와 should_end_call이 생성되지 않아 평가 불가 |
| 로컬 실행 속도 | 4/5 | 4.04초로 비교적 빠른 편임 |

---

## Interpretation

Kanana 1.5 2.1B Instruct는 3차 테스트에서도 한국어 전화 응대 말투가 자연스러운 편이었다.

특히 사용자의 요청을 받은 뒤 진료과와 시간대를 물어보는 방향은 마음콜 시나리오에 적합하다.

다만 ai_message가 너무 길어졌고, recommended_replies가 중간에 깨지면서 JSON이 완성되지 않았다.  
따라서 구조화 출력 모델로 사용하기에는 안정성이 낮다.

---

## Decision

```text
- Keep as natural conversation candidate
- Not stable enough for direct JSON generation
- Needs shorter response control or server-side JSON assembly
```

---

## Notes

- 병원 접수 직원 말투와 대화 흐름은 가장 자연스러운 편이다.
- 그러나 JSON 완성 안정성이 낮다.
- 자연어 응답 생성 후보로는 가치가 있지만, 완성 JSON 직접 생성에는 부적합하다.