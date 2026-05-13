# Qwen3 4B - Hospital Reservation Test

## Model
- qwen3:4b

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
  "ai_message": "네, 내일 오후 예약이 가능합니다. 원하시는 진료과가 있으실까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문이라 내과가 가능할까요?",
    "외과 진료를 예약하고 싶습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

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
| 1 | 36.76s |
| 2 | 59.37s |
| 3 | 28.86s |

### Average
- Average response time: 41.66s

### Notes
- 동일 endpoint(`/api/chat`)와 동일 생성 옵션을 사용해 측정했다.
- qwen3:4b는 평균 응답 시간이 41.66초로 측정되어 실시간 통화 시뮬레이션에 적용하기 어렵다.
- 일반적으로 4B 모델은 8B보다 빠를 것으로 예상되지만, 이번 실험에서는 qwen3:8b보다 느리게 측정되었다.
- 원인으로는 thinking token 생성, 응답 길이 차이, 모델 로딩/교체 영향, chat template 처리 차이 등이 있을 수 있다.
- 응답 JSON 내부에 `<think>` 또는 긴 설명이 포함되었는지 추가 확인이 필요하다.