# Gemma-ko-2B Test

## Model
- beomi/gemma-ko-2b

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
마음콜 통화 시뮬레이션에서 사용할 수 있는 Gemma Korean fine-tuned 계열 모델 후보로 `beomi/gemma-ko-2b`를 테스트했다.

이번 테스트는 Ollama 모델 비교와 Hugging Face 모델 비교에서 공통으로 사용하는 Baseline Prompt를 기준으로 진행했다.

---

## Benchmark Prompt

```text
너는 전화 공포증 완화를 위한 통화 시뮬레이션 상대이다.
현재 상황은 병원 예약 전화이다.

규칙:
- 실제 병원 접수 직원처럼 자연스럽고 공손하게 응답한다.
- 사용자를 압박하지 않는다.
- 한 번에 하나의 질문만 한다.
- 1~2문장으로 짧게 답한다.
- 반드시 JSON 형식으로만 답한다.
- 번역체 표현을 쓰지 않는다.
- 한국 병원에서 실제로 들을 수 있는 자연스러운 존댓말을 사용한다.

좋은 예시:
{
  "ai_message": "네, 확인해드리겠습니다. 원하시는 진료과가 있으실까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}

사용자 발화:
"저기... 내일 오후에 진료 예약 가능할까요?"

출력 형식:
{
  "ai_message": "...",
  "recommended_replies": ["...", "...", "..."],
  "conversation_state": "...",
  "should_end_call": false
}
```

---

## Test Result

### Generated Output Only

```text
{
  "ai_message": "네, 확인해드리겠습니다. 원하시는 진료과가 있으실까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}

사용자 발화:
"저기... 내일 오후에 진료 예약 가능할까요?"

출력 형식:
{
  "ai_message": "...",
  "recommended_replies": ["...", "...", "..."],
  "conversation_state": "...",
```

### Latency
- 7.56s

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 3/5 | 첫 번째 JSON은 정상적으로 생성했지만 이후 프롬프트 일부를 다시 출력함 |
| 한국어 자연스러움 | 4/5 | 첫 번째 JSON 응답의 한국어는 자연스러운 편임 |
| 전화 응대 말투 | 4/5 | 병원 접수 직원처럼 공손하고 자연스럽게 응답함 |
| 짧은 응답 제어 | 3/5 | 첫 응답은 짧지만 이후 불필요한 추가 출력이 발생함 |
| 추천 답변 품질 | 5/5 | 사용자가 실제 전화에서 말할 수 있는 답변 3개를 자연스럽게 생성함 |
| 대화 상태 판단 | 5/5 | conversation_state와 should_end_call이 적절함 |
| 로컬 실행 속도 | 3/5 | 7.56초로 사용 가능성은 있으나 EXAONE, Kanana 1.5보다 느림 |

---

## Interpretation

`beomi/gemma-ko-2b`는 첫 번째 JSON 응답만 보면 마음콜 병원 예약 시나리오에 적합한 응답을 생성했다.

특히 다음 항목은 좋았다.

```text
- ai_message가 병원 접수 직원 말투에 가까움
- recommended_replies가 사용자/환자 입장으로 자연스럽게 생성됨
- conversation_state가 asking_department로 적절함
- should_end_call이 false로 적절함
```

다만 모델이 JSON 하나로 출력을 종료하지 못하고, 이후에 기존 프롬프트 일부를 다시 이어서 출력하는 문제가 발생했다.

```text
사용자 발화:
"저기... 내일 오후에 진료 예약 가능할까요?"

출력 형식:
{
  "ai_message": "...",
  ...
```

이는 현재 Baseline Prompt 안에 좋은 예시와 출력 형식이 함께 포함되어 있어, 모델이 프롬프트 패턴을 그대로 이어서 생성한 것으로 보인다.

따라서 이 결과는 실패라기보다, 공통 Baseline Prompt에서 Gemma 계열 모델이 보인 출력 제어 한계로 기록한다.

---

## Decision

- Keep for secondary comparison
- Needs improved prompt re-test

---

## Notes

- Gemma-ko-2B는 첫 번째 JSON 응답 품질이 좋았다.
- 추천 답변 품질은 현재까지 테스트한 모델 중에서도 좋은 편이다.
- 그러나 JSON 이후 프롬프트 일부를 다시 출력하는 문제가 있어, FastAPI 응답으로 바로 사용하기에는 후처리 또는 프롬프트 개선이 필요하다.
- 1차 Baseline Prompt 결과로는 참고 가치가 있으며, 2차 Improved Prompt에서 다시 평가할 필요가 있다.

---

## Next Step

```text
1. Improved Prompt로 Gemma-ko-2B 재측정
2. 첫 번째 JSON만 추출하는 후처리 가능성 검토
3. EXAONE, Kanana 계열과 2차 프롬프트 기준으로 재비교
4. 최종 후보 선정 시 속도와 출력 안정성을 함께 고려
```