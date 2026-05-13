# Qwen3 8B - Hospital Reservation Test

## Model
- qwen3:8b

## Runtime
- Ollama

## Scenario
- 병원 예약 전화

## Prompt
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

## Raw Response

```json
{
  "ai_message": "네, 확인해 드리겠습니다. 원하시는 진료과가
 있으실까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```


## Evaluation

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 4/5 | JSON 구조는 안정적이었으나 응답 문자열에 줄바꿈이 발생할 가능성이 있어 후처리 필요 |
| 한국어 자연스러움 | 5/5 | 병원 예약 상황에 맞는 자연스러운 존댓말 응답 생성 |
| 전화 응대 말투 | 5/5 | 실제 병원 접수 직원처럼 공손하고 간결함 |
| 짧은 응답 제어 | 5/5 | 1~2문장 규칙을 잘 지킴 |
| 추천 답변 품질 | 5/5 | 사용자가 실제 통화에서 활용할 수 있는 답변 3개를 생성 |
| 로컬 실행 속도 | 3/5 | 평균 10.62초로 실시간 통화 시뮬레이션에는 다소 느릴 수 있음 |

## Decision
- Keep for quality comparison
- Needs speed optimization for real-time use

## Notes
- qwen3:8b는 응답 품질은 좋았지만 평균 응답 시간이 10초 이상으로 측정되었다.
- 실제 통화 시뮬레이션에서는 사용자가 응답을 기다리는 시간이 길게 느껴질 수 있다.
- 추후 qwen3:4b와 응답 품질 및 속도를 비교한 뒤, 실시간 사용 모델 후보를 결정한다.

## Latency Test

### Environment
- Device: Apple M4 Pro
- Runtime: Ollama
- Model: qwen3:8b
- GPU Acceleration: Metal
- Total Memory: 5.5 GiB

### Trial Results

| Trial | Response Time |
|---|---:|
| 1 | 8.31s |
| 2 | 7.48s |
| 3 | 16.06s |

### Average
- Average response time: 10.62s

### Runtime Log Summary
- Model weights on GPU: 4.5 GiB
- Model weights on CPU: 333.8 MiB
- KV cache on GPU: 576.0 MiB
- Compute graph on GPU: 100.0 MiB
- Total memory: 5.5 GiB
- Offloaded layers: 37/37

### Notes
- qwen3:8b successfully generated a valid JSON response for the hospital reservation scenario.
- The first and second trials completed in approximately 7–8 seconds.
- The third trial took 16.06 seconds, likely due to generation length variation or local runtime load.
- The average response time was 10.62 seconds.
- For real-time call simulation, response speed may need optimization through shorter prompts, response length limits, streaming, or a smaller model.

## Controlled Latency Test

### Test Condition
- Endpoint: `/api/chat`
- Stream: `false`
- Think: `false`
- Temperature: `0`
- Num Predict: `180`
- Seed: `42`

### Trial Results

| Trial | Response Time |
|---|---:|
| 1 | 19.38s |
| 2 | 19.48s |
| 3 | 10.85s |

### Average
- Average response time: 16.57s

### Notes
- 동일 endpoint(`/api/chat`)와 동일 생성 옵션을 사용해 재측정했다.
- qwen3:8b는 응답 품질은 안정적이었지만, 평균 응답 시간이 16.57초로 측정되었다.
- 실시간 통화 시뮬레이션에 바로 적용하기에는 다소 느릴 수 있다.
- 추후 프롬프트 길이 축소, `num_predict` 감소, streaming 적용, 더 작은 모델 사용 등을 검토할 필요가 있다.