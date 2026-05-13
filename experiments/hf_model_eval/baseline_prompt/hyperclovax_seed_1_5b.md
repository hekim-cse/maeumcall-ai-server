# HyperCLOVAX-SEED-Text-Instruct-1.5B Test

## Model
- naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
마음콜 통화 시뮬레이션에서 사용할 수 있는 한국어 Instruct 모델 후보로 `HyperCLOVAX-SEED-Text-Instruct-1.5B`를 테스트했다.

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
  "ai_message": "내일 오후에 진료 예약 가능 여부는 저희 병원에서 확인해드리겠습니다.",
  "recommended_replies": [
    "내일 오후에 진료 예약 가능 여부를 알려주세요.",
    "예약 가능 여부를 확인 후 연락드리겠습니다.",
    "내일 오후에 진료 가능 시간을 알려주세요."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
assistant
{
  "ai_message": "내일 오후에 진료 예약 가능 여부는 저희 병원에서 확인해드리겠습니다.",
  "recommended_replies": [
    "내일 오후에 진료 예약 가능 여부를 알려주세요.",
    "예약 가능 여부를 확인 후 연락드리겠습니다.",
    "내일 오후에 진료 가능 시간을 알려주세요."
  ],
  "conversation_state":
```

### Latency
- 5.12s

---

## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 3/5 | 첫 번째 JSON은 정상이나 이후 assistant 블록이 반복 생성됨 |
| 한국어 자연스러움 | 4/5 | 전체 문장은 자연스러운 편임 |
| 전화 응대 말투 | 3/5 | 병원 응대 말투에 가깝지만 다음 정보를 묻는 흐름은 다소 약함 |
| 짧은 응답 제어 | 3/5 | 첫 응답은 짧지만 이후 반복 출력이 발생함 |
| 추천 답변 품질 | 3/5 | 일부 답변은 사용자 입장에 가깝지만, 병원 직원 말투로 보이는 문장도 포함됨 |
| 대화 상태 판단 | 5/5 | conversation_state와 should_end_call이 적절함 |
| 로컬 실행 속도 | 4/5 | 5.12초로 비교적 빠른 편이며, 실시간 후보로 검토 가능함 |

---

## Interpretation

`HyperCLOVAX-SEED-Text-Instruct-1.5B`는 0.5B 모델보다 훨씬 안정적인 결과를 보였다.

특히 다음 항목은 긍정적이다.

```text
- 응답 시간이 5.12초로 비교적 빠름
- 첫 번째 JSON 구조는 정상적으로 생성됨
- 한국어 문장이 자연스러운 편임
- conversation_state가 asking_department로 적절함
- should_end_call이 false로 적절함
```

다만 다음 문제가 남아 있다.

```text
1. 첫 번째 JSON 이후 assistant 블록이 반복 생성됨
2. recommended_replies 중 일부가 사용자/환자 입장이 아니라 병원 직원 말투에 가까움
3. ai_message가 다음 정보를 직접 묻기보다 예약 가능 여부를 확인해주겠다는 표현에 머무름
```

예를 들어 추천 답변 중 `"예약 가능 여부를 확인 후 연락드리겠습니다."`는 환자가 실제로 말하는 문장이라기보다 병원 직원 쪽 말투에 가깝다.

따라서 현재 Baseline Prompt 기준으로는 완전히 안정적인 메인 모델이라고 보기 어렵지만, 응답 속도와 한국어 품질이 괜찮기 때문에 2차 Improved Prompt 재평가 후보로 유지한다.

---

## Decision

- Keep for secondary comparison
- Needs improved prompt re-test

---

## Notes

- HyperCLOVA X SEED 1.5B는 0.5B 대비 응답 속도와 생성 품질이 크게 개선되었다.
- 첫 번째 JSON만 보면 FastAPI 응답으로 사용할 가능성이 있다.
- 그러나 반복 출력이 발생했기 때문에 후처리 또는 프롬프트 개선이 필요하다.
- recommended_replies가 반드시 사용자/환자 입장으로 생성되도록 개선 프롬프트에서 역할을 명확히 분리해야 한다.
- 현재까지 테스트한 Hugging Face 모델 중 상위 후보군에 포함한다.

---

## Next Step

```text
1. Improved Prompt로 HyperCLOVA X SEED 1.5B 재측정
2. EXAONE-4.0-1.2B, Kanana 1.5 2.1B와 2차 비교
3. 첫 번째 JSON만 추출하는 후처리 가능성 검토
4. 최종 후보 선정 시 응답 속도, JSON 안정성, 추천 답변 품질을 함께 고려
```