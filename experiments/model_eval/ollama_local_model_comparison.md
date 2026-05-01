# Ollama Local Model Comparison for Maeum Call

## Test Purpose
마음콜 AI 통화 시뮬레이션에 적합한 로컬 오픈소스 LLM 후보를 비교하기 위해 Ollama 기반 모델을 테스트했다.

## Test Condition
- Runtime: Ollama
- Device: Apple M4 Pro
- Endpoint: `/api/chat`
- Stream: false
- Temperature: 0
- Num Predict: 180
- Seed: 42
- Scenario: 병원 예약 전화

## Test Models
- qwen3:4b
- qwen3:8b
- mistral:latest
- phi3:latest

## Latency Result

| Model | Total Response Time | Eval Time | Load Time | Note |
|---|---:|---:|---:|---|
| qwen3:4b | 41.66s avg | - | - | 응답 불안정 |
| qwen3:8b | 16.57s avg | - | - | 품질 기준 모델 |
| mistral:latest | 14.96s | 3.67s | 10.62s | JSON 중간 잘림 |
| phi3:latest | 12.42s | 2.12s | 9.80s | JSON 중간 잘림 |

## Quality Result

| Model | JSON Stability | Korean Naturalness | Scenario Understanding | Decision |
|---|---:|---:|---:|---|
| qwen3:4b | 1/5 | 2/5 | 3/5 | Drop |
| qwen3:8b | 4/5 | 5/5 | 5/5 | Keep as baseline |
| mistral:latest | 1/5 | 2/5 | 1/5 | Drop |
| phi3:latest | 1/5 | 1/5 | 1/5 | Drop |

## Model Notes

### qwen3:4b
- 더 작은 모델임에도 qwen3:8b보다 응답 시간이 길게 측정되었다.
- JSON key가 깨지는 문제가 발생했다.
- 불필요한 영어 설명이 응답에 포함되었다.
- 실시간 통화 모델 후보에서 제외한다.

### qwen3:8b
- JSON 형식과 한국어 병원 예약 응답 품질은 가장 안정적이었다.
- 다만 평균 응답 시간이 16.57초로 실시간 통화 시뮬레이션에는 다소 느리다.
- 품질 기준 모델로 유지한다.

### mistral:latest
- 응답 속도는 qwen3:8b보다 약간 빠르지만, JSON이 중간에 잘렸다.
- 사용자가 예약 가능 여부를 물었는데 모델이 임의로 예약 완료 처리했다.
- 한국어 전화 말투가 부자연스럽고, “당신은” 같은 어색한 표현이 포함되었다.
- 실시간 사용 후보에서 제외한다.

### phi3:latest
- 모델 로딩 이후 실제 생성 시간은 비교적 짧았으나, 한국어 품질이 낮았다.
- `ai_message`가 비어 있고, 추천 답변도 부자연스럽게 생성되었다.
- JSON이 중간에 잘려 구조화 응답으로 사용하기 어렵다.
- 실시간 사용 후보에서 제외한다.

## Conclusion
Ollama 기반 로컬 모델 비교 결과, qwen3:8b가 가장 안정적인 한국어 응답 품질을 보였지만 실시간 통화 시뮬레이션에 적용하기에는 응답 시간이 길었다.

mistral과 phi3는 로딩 이후 생성 시간은 비교적 짧았지만, 한국어 자연스러움과 JSON 출력 안정성이 낮아 마음콜 서비스에 바로 적용하기 어렵다고 판단했다.

따라서 Ollama는 로컬 모델 비교 및 프로토타입 검증 도구로 활용하고, 실제 서비스 적용 모델은 한국어 특화 오픈소스 모델 또는 Hugging Face 기반 튜닝 모델을 추가 검토한다.

## Next Step
- EXAONE 계열 모델 테스트
- HyperCLOVA X SEED 계열 모델 테스트
- Hugging Face Transformers 기반 직접 로딩 실험
- LoRA / QLoRA 튜닝 데이터셋 구축
- 응답 속도 개선을 위한 streaming 적용 검토