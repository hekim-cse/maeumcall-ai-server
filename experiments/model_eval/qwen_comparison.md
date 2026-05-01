# Qwen Model Comparison for Maeum Call

## Test Purpose
마음콜 AI 통화 시뮬레이션에서 사용할 오픈소스 LLM 후보를 비교하기 위해 Ollama 기반으로 Qwen3 4B와 Qwen3 8B를 테스트했다.

## Test Condition
- Runtime: Ollama
- Device: Apple M4 Pro
- Endpoint: `/api/chat`
- Stream: false
- Think: false
- Temperature: 0
- Num Predict: 180
- Seed: 42
- Scenario: 병원 예약 전화

## Latency Result

| Model | Trial 1 | Trial 2 | Trial 3 | Average |
|---|---:|---:|---:|---:|
| qwen3:4b | 36.76s | 59.37s | 28.86s | 41.66s |
| qwen3:8b | 19.38s | 19.48s | 10.85s | 16.57s |

## Quality Result

| Model | JSON Stability | Korean Naturalness | Phone Scenario Fit | Decision |
|---|---:|---:|---:|---|
| qwen3:4b | 1/5 | 2/5 | 3/5 | Drop |
| qwen3:8b | 4/5 | 5/5 | 5/5 | Keep |

## Interpretation
qwen3:4b는 더 작은 모델임에도 불구하고 qwen3:8b보다 응답 시간이 길었고, JSON key가 깨지는 문제가 발생했다. 또한 응답 뒤에 불필요한 영어 설명이 붙어 FastAPI 응답으로 바로 사용하기 어려웠다.

qwen3:8b는 평균 응답 시간이 16.57초로 실시간 통화 시뮬레이션에는 다소 느리지만, JSON 형식과 한국어 병원 예약 응답 품질이 안정적이었다. 따라서 qwen3:8b는 품질 기준 모델로 유지하고, qwen3:4b는 실시간 사용 후보에서 제외한다.

## Next Step
- EXAONE 4.0 1.2B 테스트
- HyperCLOVA X SEED Instruct 테스트
- 더 짧은 프롬프트와 streaming 옵션으로 qwen3:8b 속도 최적화 실험