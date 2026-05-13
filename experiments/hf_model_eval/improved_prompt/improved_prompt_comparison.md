# Hugging Face 2차 Improved Prompt 비교

## 1. 목적

1차 Baseline Prompt에서는 모든 모델을 동일 조건으로 비교했다.

그러나 일부 모델에서 다음 문제가 발생했다.

```text
- 좋은 예시를 그대로 따라 쓰는 문제
- JSON 이후 assistant 블록을 반복 생성하는 문제
- 사용자 발화와 출력 형식 일부를 다시 출력하는 문제
- recommended_replies를 사용자 입장이 아니라 병원 직원 입장으로 생성하는 문제
```

따라서 2차 테스트에서는 역할을 더 명확하게 분리한 Improved Prompt를 사용하여 실제 서비스 적용 가능성을 확인한다.

---

## 2. 2차 평가 대상

| 순위 | 모델 | 2차 평가 이유 |
|---:|---|---|
| 1 | LGAI-EXAONE/EXAONE-4.0-1.2B | 1차 테스트에서 가장 빠르고 JSON 안정성이 좋았음 |
| 2 | kakaocorp/kanana-1.5-2.1b-instruct-2505 | 속도와 한국어 전화 말투가 모두 좋았음 |
| 3 | naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B | 한국어 품질과 속도는 좋지만 반복 출력 검증 필요 |
| 4 | beomi/gemma-ko-2b | 첫 JSON 품질은 좋지만 프롬프트 반복 출력 검증 필요 |

---

## 3. 테스트 조건

| 항목 | 값 |
|---|---|
| 실행 도구 | Hugging Face Transformers |
| 디바이스 | Apple M4 Pro |
| 프롬프트 | Improved Prompt |
| max_new_tokens | 120 |
| do_sample | False |
| repetition_penalty | 1.1 |
| 테스트 시나리오 | 병원 예약 전화 |

---

## 4. Improved Prompt

```text
너는 전화 공포증 완화를 위한 통화 시뮬레이션 AI이다.

현재 상황:
- 사용자는 병원에 전화를 걸어 진료 예약을 연습하고 있다.
- 사용자는 전화 상황에 익숙하지 않거나 긴장할 수 있다.
- 너는 실제 한국 병원 접수 직원 역할로 응답한다.
- 너의 응답은 사용자가 실제 병원에 전화했을 때 들을 수 있는 자연스럽고 공손한 접수 직원 말투여야 한다.
- 동시에 사용자가 다음 말을 쉽게 이어갈 수 있도록, recommended_replies를 함께 제공한다.

역할 구분:
- ai_message:
  - 병원 접수 직원이 사용자에게 직접 말하는 문장이다.
  - 사용자의 요청을 확인하고, 예약을 진행하기 위해 필요한 다음 정보를 부드럽게 묻는다.
  - 사용자를 압박하지 않는다.
  - 아직 정보가 부족하면 예약 가능 여부나 예약 완료를 임의로 확정하지 않는다.

- recommended_replies:
  - 병원 접수 직원의 응대에 대해 사용자가 다음에 말해볼 수 있는 문장이다.
  - 반드시 사용자/환자 입장에서 작성한다.
  - 병원 직원이 말하는 안내 문장으로 작성하지 않는다.
  - 전화 공포증이 있는 사용자가 그대로 따라 말해도 어색하지 않은 짧고 자연스러운 문장이어야 한다.
  - 서로 다른 선택지를 3개 제공한다.

- conversation_state:
  - 현재 대화가 어느 단계인지 나타낸다.
  - 예: asking_department, asking_time, confirming_info, closing

- should_end_call:
  - 통화를 종료해도 되는지 나타낸다.
  - 아직 예약이 완료되지 않았으므로 false로 둔다.

규칙:
- 반드시 JSON 형식으로만 답한다.
- JSON 외의 설명, markdown, 코드블록, assistant 문구를 출력하지 않는다.
- ai_message는 병원 접수 직원 말투로 1문장만 작성한다.
- recommended_replies는 사용자가 실제 전화에서 말할 수 있는 서로 다른 문장 3개를 작성한다.
- recommended_replies는 병원 직원 말투로 작성하지 않는다.
- 사용자의 말을 그대로 반복하지 않는다.
- 예약 가능 여부를 임의로 확정하지 않는다.
- 예약 완료처럼 말하지 않는다.
- 사용자를 압박하지 않고, 필요한 다음 정보를 부드럽게 물어본다.

사용자 발화:
"저기... 내일 오후에 진료 예약 가능할까요?"

출력 JSON 형식:
{
  "ai_message": "...",
  "recommended_replies": ["...", "...", "..."],
  "conversation_state": "...",
  "should_end_call": false
}
```

---

## 5. 모델별 결과 요약

| 모델 | 응답 시간 | JSON 안정성 | 한국어 자연스러움 | 추천 답변 품질 | 판단 |
|---|---:|---|---|---|---|
| EXAONE-4.0-1.2B | 3.72초 | 낮음 | 낮음~보통 | 낮음 | 속도 baseline으로 유지 |
| Kanana 1.5 2.1B Instruct | 예정 | 예정 | 예정 | 예정 | 예정 |
| HyperCLOVA X SEED 1.5B | 예정 | 예정 | 예정 | 예정 | 예정 |
| Gemma-ko-2B | 예정 | 예정 | 예정 | 예정 | 예정 |

---

## 6. 모델별 세부 판단

### ① EXAONE-4.0-1.2B

#### 모델

```text
LGAI-EXAONE/EXAONE-4.0-1.2B
```

#### Generated Output

```text
```json
{
  "ai_message": "네, 가능합니다. 오늘 오후 2시 이후로 예약이 가능해요. 어떤 시간이 preferable하시나요?",
  "recommended_replies": ["시간을 알려주세요.", "다른 시간도 괜찮을까요?", "지금 말씀하신 대로 예약해 드릴게요."]
  "conversation_state": "asking_time",
  "should_end_call": false
}
```
```

#### Latency

```text
3.72s
```

#### 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 2/5 | 코드블록이 포함되었고 recommended_replies 뒤 쉼표가 누락되어 엄밀한 JSON 파싱이 어려움 |
| 한국어 자연스러움 | 2/5 | “preferable하시나요?”처럼 영어가 섞여 한국 병원 접수 말투로는 부자연스러움 |
| 전화 응대 말투 | 2/5 | 예약 가능 여부를 임의로 확정했고, 병원 접수 말투가 다소 어색함 |
| 추천 답변 품질 | 2/5 | 일부 추천 답변이 사용자/환자 입장이 아니라 병원 직원 말투에 가까움 |
| 대화 상태 판단 | 4/5 | asking_time과 should_end_call=false는 적절함 |
| 로컬 실행 속도 | 5/5 | 3.72초로 매우 빠름 |

#### 해석

EXAONE-4.0-1.2B는 2차 Improved Prompt에서도 응답 속도는 매우 우수했다.

```text
1차 응답 시간: 3.86초
2차 응답 시간: 3.72초
```

다만 출력 품질은 1차보다 불안정해졌다.  
특히 JSON에 코드블록이 포함되었고, 쉼표가 누락되어 엄밀한 JSON 형식으로 파싱하기 어렵다.

또한 `"preferable하시나요?"`처럼 영어가 섞인 표현이 나왔고, recommended_replies에서도 `"지금 말씀하신 대로 예약해 드릴게요."`처럼 병원 직원 말투에 가까운 문장이 생성되었다.

따라서 EXAONE은 속도 측면에서는 강력하지만, 실제 서비스 적용을 위해서는 강한 JSON 후처리 또는 추가 프롬프트 개선이 필요하다.

#### 판단

```text
- Keep for speed baseline
- Needs strict JSON control
- Needs prompt or post-processing improvement
```

---

## 7. 현재 결론

```text
EXAONE-4.0-1.2B는 2차 테스트에서도 3.72초로 가장 빠른 속도를 보였다.
하지만 JSON 안정성, 한국어 자연스러움, 추천 답변 역할 구분 측면에서는 불안정한 결과가 나왔다.

따라서 EXAONE은 최종 후보에서 제외하지는 않지만, 현재 상태에서는 “속도 baseline”으로 유지한다.
다음 모델인 Kanana 1.5 2.1B Instruct 결과와 비교하여 최종 후보 여부를 판단한다.
```

---

### ② Kanana 1.5 2.1B Instruct

#### 모델

```text
kakaocorp/kanana-1.5-2.1b-instruct-2505
```

#### 1차 재측정 결과

```text
{
  "ai_message": "내일 오후에 진료 예약을 원하시는군요. 몇 가지 추가 정보가 필요합니다. 진료를 원하시는 과(예: 내과, 피부과 등)와 예약하실 시간대를 알려주시면 바로 확인해드리겠습니다.",
  "recommended_replies": [
    "네, 내과로 예약하고 싶어요. 내일 오후 3시 정도 괜찮을까요?",
    "진료 과목은 어디로 원하시나요? 그리고 가능한 시간대도 말씀해주시면
```

#### 1차 Latency

```text
5.82s
```

#### 2차 재측정 조건

```text
max_new_tokens=160
do_sample=False
repetition_penalty=1.1
```

#### 2차 재측정 결과

```text
{
  "ai_message": "내일 오후에 진료 예약을 원하시는군요. 몇 가지 추가 정보가 필요합니다. 진료를 원하시는 과(예: 내과, 피부과 등)와 예약하실 시간대를 알려주시면 바로 확인해드리겠습니다.",
  "recommended_replies": [
    "네, 내과로 예약하고 싶어요. 내일 오후 3시 정도 괜찮을까요?",
    "진료 과목은 어디로 원하시나요? 그리고 가능한 시간대도 말씀해주시면 빠르게 예약 도와드릴 수 있습니다.",
    "혹시 원하시는 진료 과목이나 시간대가 있으신가요? 말씀해주시면 바로 예약 가능 여
```

#### 2차 Latency

```text
7.57s
```

#### 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 1/5 | max_new_tokens를 160으로 늘렸지만 JSON이 끝까지 완성되지 않음 |
| 한국어 자연스러움 | 4/5 | ai_message의 한국어 문장은 자연스럽고 접수 직원 말투에 가까움 |
| 전화 응대 말투 | 4/5 | 사용자의 요청을 확인하고 추가 정보를 묻는 흐름은 좋음 |
| 추천 답변 품질 | 2/5 | 첫 번째 답변은 사용자 입장이나, 나머지는 병원 직원 말투에 가까움 |
| 대화 상태 판단 | - | JSON이 잘려 conversation_state와 should_end_call 확인 불가 |
| 로컬 실행 속도 | 3/5 | 7.57초로 속도는 보통 수준이나 JSON 미완성 문제가 큼 |

#### 해석

Kanana 1.5 2.1B Instruct는 한국어 전화 응대 말투가 자연스럽고, 병원 접수 직원으로서 사용자의 요청을 확인한 뒤 필요한 정보를 묻는 흐름은 좋았다.

그러나 Improved Prompt에서는 응답을 길게 생성하는 경향이 강했고, `max_new_tokens=160`으로 늘렸음에도 JSON이 끝까지 완성되지 않았다.

또한 recommended_replies 중 일부가 사용자/환자 입장이 아니라 병원 직원 말투로 생성되어, 역할 분리가 완전히 안정적이지 않았다.

#### 판단

```text
- Retry/보류
- 한국어 응대 품질은 좋음
- JSON 완성 안정성이 낮음
- 현재 Improved Prompt 기준으로는 최종 후보 판단 보류
```

---

### ③ HyperCLOVA X SEED 1.5B

#### 모델

```text
naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B
```

#### Generated Output

```text
```json
{
  "ai_message": "내일 오후에 진료 예약이 가능합니다. 몇 시로 예약해드릴까요?",
  "recommended_replies": [
    "오전으로 예약할까요?",
    "오후 2시로 예약할까요?",
    "오후 4시로 예약할까요?"
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```assistant
내일 오후에 진료 예약이 가능합니다. 몇 시로 예약해드릴까요?```assistant
내일 오후에 진료 예약이 가능합니다. 몇 시로 예약해드릴까요?

1. 오전으로 예약할까요?
2. 오후 2시로 예약할까요?
```

#### Latency

```text
5.29s
```

#### 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 2/5 | 첫 번째 JSON은 생성했지만 코드블록과 assistant 반복 출력이 포함됨 |
| 한국어 자연스러움 | 3/5 | 문장 자체는 자연스럽지만 예약 가능 여부를 임의로 확정함 |
| 전화 응대 말투 | 3/5 | 병원 접수 직원 말투는 가능하나, 필요한 정보를 먼저 묻는 흐름이 약함 |
| 추천 답변 품질 | 2/5 | 추천 답변이 사용자/환자 입장보다 병원 직원 질문에 가까움 |
| 대화 상태 판단 | 3/5 | should_end_call=false는 적절하지만 conversation_state는 asking_time에 더 가까움 |
| 로컬 실행 속도 | 4/5 | 5.29초로 비교적 빠른 편임 |

#### 해석

HyperCLOVA X SEED 1.5B는 2차 Improved Prompt에서도 비교적 빠른 응답 속도를 보였다.  
첫 번째 JSON 구조도 생성했으며, 한국어 문장 자체는 자연스러운 편이었다.

그러나 JSON 외의 markdown 코드블록이 포함되었고, 첫 번째 JSON 이후 `assistant` 문구와 응답 문장이 반복 출력되었다.  
또한 프롬프트에서 예약 가능 여부를 임의로 확정하지 말라고 했음에도 `"내일 오후에 진료 예약이 가능합니다."`라고 확정적으로 응답했다.

recommended_replies 역시 사용자/환자 입장이 아니라 병원 직원이 묻는 질문처럼 생성되어, 역할 분리 지시를 완전히 따르지 못했다.

#### 판단

```text
- 보류
- 응답 속도와 한국어 품질은 괜찮음
- JSON 이후 반복 출력 문제가 지속됨
- recommended_replies 역할 구분이 불안정함
- 후처리 또는 더 강한 출력 제어가 필요함
```

---

### ④ Gemma-ko-2B

#### 모델

```text
beomi/gemma-ko-2b
```

#### Generated Output

```text
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약 가능합니다."
"아니오."
"예약
```

#### Latency

```text
6.72s
```

#### 평가

| 항목 | 점수 | 메모 |
|---|---:|---|
| JSON 형식 안정성 | 0/5 | JSON 형식을 전혀 따르지 못함 |
| 한국어 자연스러움 | 1/5 | 단순 문장 반복으로 자연스러운 응답이라고 보기 어려움 |
| 전화 응대 말투 | 1/5 | 병원 접수 직원 역할을 수행하지 못함 |
| 추천 답변 품질 | 0/5 | recommended_replies 구조가 생성되지 않음 |
| 대화 상태 판단 | 0/5 | conversation_state와 should_end_call이 생성되지 않음 |
| 로컬 실행 속도 | 3/5 | 6.72초로 속도는 보통이나 출력 품질이 낮음 |

#### 해석

Gemma-ko-2B는 1차 Baseline Prompt에서는 첫 번째 JSON 응답 품질이 좋았지만, 2차 Improved Prompt에서는 JSON 구조를 전혀 따르지 못했다.

출력은 `"예약 가능합니다."`, `"아니오."` 형태의 짧은 문장이 반복되었고, ai_message, recommended_replies, conversation_state, should_end_call 필드가 생성되지 않았다.

따라서 현재 Improved Prompt 기준에서는 마음콜 통화 시뮬레이션 응답 모델로 사용하기 어렵다.

#### 판단

```text
- Drop
- 2차 Improved Prompt 기준 출력 안정성 낮음
- JSON 구조 생성 실패
- 반복 출력 문제 발생
```