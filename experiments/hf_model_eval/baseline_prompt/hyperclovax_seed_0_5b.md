# HyperCLOVAX-SEED-Text-Instruct-0.5B Test

## Model
- naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-0.5B

## Runtime
- Hugging Face Transformers
- Device: Apple M4 Pro
- Project: maeum-call-ai-server

## Scenario
- 병원 예약 전화

## Purpose
마음콜 통화 시뮬레이션에서 사용할 수 있는 한국어 경량 Instruct 모델 후보로 HyperCLOVAX-SEED-Text-Instruct-0.5B를 테스트했다.

모든 모델은 Ollama 모델 비교 때 사용한 동일한 병원 예약 프롬프트를 기준으로 평가한다.

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

## First Test Result

### Raw Output

```text
{
  "ai_message": "안녕하세요, 예약 가능 여부를 문의하셨군요.",
  "recommended_replies": [
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다.",
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다.",
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다."
  ],
  "conversation_state": "문의",
  "should_end_call": true
}

assistant
{
  "ai_message": "안녕하세요, 예약 가능 여부를 문의하셨군요.",
  "recommended_replies": [
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다.",
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다.",
    "예약 가능 여부를 확인하기 위해 예약 번호를 알려주시면 감사하겠습니다."
  ],
  "conversation_state": "문의",
  "
```

### Latency
- 17.92s

### First Test Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 2/5 | 첫 번째 JSON은 생성했지만 이후 응답이 반복되고 두 번째 JSON이 중간에 잘림 |
| 한국어 자연스러움 | 3/5 | 문장 자체는 한국어지만 실제 병원 접수 말투로는 다소 어색함 |
| 전화 응대 말투 | 2/5 | 사용자의 질문에 대해 필요한 정보를 자연스럽게 이어 묻지 못함 |
| 짧은 응답 제어 | 2/5 | JSON을 반복 생성하면서 출력이 길어짐 |
| 추천 답변 품질 | 1/5 | 추천 답변 3개가 모두 동일하고, 사용자 발화가 아니라 병원 측 발화에 가까움 |
| 대화 상태 판단 | 1/5 | 아직 통화를 종료할 상황이 아닌데 should_end_call을 true로 생성함 |
| 로컬 실행 속도 | 2/5 | 0.5B 모델임에도 17.92초가 소요되어 실시간 적용에는 아쉬움 |

### First Test Notes
- 한국어 응답과 JSON 형식 생성을 시도했으나, 추천 답변이 모두 중복되었다.
- recommended_replies가 사용자가 말할 문장이 아니라 병원 직원이 말할 문장에 가깝게 생성되었다.
- should_end_call이 true로 출력되어 대화 상태 판단이 부적절했다.
- JSON 이후 assistant 블록이 반복되며 출력이 중간에 잘렸다.

---

## Re-Test Condition

첫 테스트 이후 다음 사항을 수정하여 재측정했다.

```text
1. 입력 프롬프트를 제외하고 모델이 새로 생성한 부분만 출력하도록 코드 수정
2. Ollama 비교 때 사용한 Benchmark Prompt를 그대로 사용
3. max_new_tokens는 180으로 유지
4. do_sample=False로 결정적 생성 유지
```

---

## Re-Test Result

### Generated Output Only

```text
{
  "ai_message": "네, 확인해드리겠습니다. 내일 오후에 진료 예약 가능할까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```
```
assistant
{
  "ai_message": "내일 오후에 진료 예약 가능할까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

### Latency
- 20.39s

### Re-Test Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 3/5 | 첫 번째 JSON은 정상이나 이후 불필요한 assistant 블록이 추가 생성됨 |
| 한국어 자연스러움 | 3/5 | 추천 답변은 자연스럽지만 ai_message가 사용자의 질문을 반복하는 느낌이 있음 |
| 전화 응대 말투 | 3/5 | 병원 접수 직원 말투에 가까워졌지만 다음 정보를 묻는 흐름이 약함 |
| 짧은 응답 제어 | 3/5 | 첫 응답은 짧지만 이후 반복 출력이 발생함 |
| 추천 답변 품질 | 5/5 | 환자 입장에서 실제 말할 수 있는 답변 3개를 잘 생성함 |
| 대화 상태 판단 | 5/5 | conversation_state와 should_end_call이 적절함 |
| 로컬 실행 속도 | 1/5 | 20.39초로 실시간 통화 시뮬레이션에는 부적합함 |

---

## Interpretation

HyperCLOVAX-SEED-Text-Instruct-0.5B는 한국어 경량 Instruct 모델로서 JSON 형식과 추천 답변 생성을 어느 정도 수행했다.

재측정 결과, 추천 답변 품질과 대화 상태 판단은 첫 테스트보다 개선되었다.  
특히 recommended_replies는 사용자가 병원 전화에서 실제로 말할 수 있는 문장으로 생성되었다.

다만 다음 문제가 남아 있다.

```text
1. JSON 이후 불필요한 assistant 블록이 추가 생성됨
2. ai_message가 사용자의 질문을 반복하는 느낌이 있음
3. 병원 접수 직원이 다음 정보를 자연스럽게 묻는 흐름이 약함
4. 0.5B 모델임에도 latency가 20.39초로 측정됨
5. 실시간 통화 시뮬레이션에 바로 적용하기에는 응답 속도가 느림
```

---

## Decision

- Drop for real-time main model
- Keep as Korean lightweight baseline

---

## Notes

- HyperCLOVAX-SEED-Text-Instruct-0.5B는 한국어 추천 답변 생성 능력은 확인되었다.
- 그러나 JSON 출력 안정성, 반복 생성 문제, 응답 속도 측면에서 마음콜의 메인 AI 응답 모델로는 부적합하다.
- 향후 다른 후보 모델과 비교할 때 한국어 경량 Instruct baseline으로 기록한다.
- HyperCLOVAX-SEED-Text-Instruct-1.5B는 gated model 접근 승인 후 별도로 테스트한다.

---

## Next Step

```text
1. EXAONE-4.0-1.2B 테스트
2. HyperCLOVAX-SEED-Text-Instruct-1.5B 접근 승인 후 테스트
3. Gemma Korean fine-tuned 계열 테스트
4. Kanana Instruct 계열 테스트
5. 상위 후보 모델만 개선 프롬프트로 재평가
```