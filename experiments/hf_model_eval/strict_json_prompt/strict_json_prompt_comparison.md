# Hugging Face 3차 Strict JSON Prompt 비교

## 1. 목적

1차 Baseline Prompt와 2차 Improved Prompt에서는 일부 모델이 JSON 이후 추가 문장을 출력하거나, assistant 블록을 반복하거나, recommended_replies를 사용자 입장이 아닌 병원 직원 말투로 생성하는 문제가 있었다.

따라서 3차 테스트에서는 프롬프트를 더 짧고 강하게 줄여, 모델이 JSON 객체 하나만 안정적으로 생성할 수 있는지 확인한다.

## 2. 테스트 대상

| 순위 | 모델 | 3차 테스트 이유 |
|---:|---|---|
| 1 | LGAI-EXAONE/EXAONE-4.0-1.2B | 1차, 2차 모두 가장 빠른 응답 속도를 보여 strict JSON 제어 가능성 확인 |
| 2 | naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B | 한국어 품질과 속도는 좋지만 반복 출력 문제 검증 필요 |
| 3 | kakaocorp/kanana-1.5-2.1b-instruct-2505 | 한국어 전화 응대 말투는 좋지만 JSON 완성 안정성 검증 필요 |

Gemma-ko-2B는 2차 Improved Prompt에서 JSON 구조 생성에 실패했기 때문에 3차 테스트 대상에서 제외했다.

---

## 3. 테스트 조건

| 항목 | 값 |
|---|---|
| 실행 도구 | Hugging Face Transformers |
| 디바이스 | Apple M4 Pro |
| 프롬프트 | Strict JSON Prompt |
| max_new_tokens | 100 |
| do_sample | False |
| repetition_penalty | 1.15 |
| 테스트 시나리오 | 병원 예약 전화 |

---

## 4. Strict JSON Prompt

```text
너는 병원 예약 전화 시뮬레이션 AI이다.

역할:
- ai_message는 병원 접수 직원이 사용자에게 말하는 문장이다.
- recommended_replies는 사용자가 병원 접수 직원에게 답할 수 있는 환자 입장의 문장이다.

상황:
사용자가 말했다: "저기... 내일 오후에 진료 예약 가능할까요?"

규칙:
- 반드시 JSON 객체 하나만 출력한다.
- markdown 코드블록을 쓰지 않는다.
- assistant, user 같은 역할 이름을 출력하지 않는다.
- 설명 문장을 붙이지 않는다.
- JSON 뒤에 추가 문장을 붙이지 않는다.
- ai_message는 병원 접수 직원 말투로 1문장만 작성한다.
- ai_message에서 예약 가능 여부를 확정하지 않는다.
- ai_message는 다음에 필요한 정보를 부드럽게 물어본다.
- recommended_replies는 사용자가 실제로 말할 수 있는 짧은 문장 3개로 작성한다.
- recommended_replies는 병원 직원 말투로 작성하지 않는다.
- should_end_call은 false로 작성한다.

출력 형식:
{
  "ai_message": "문장",
  "recommended_replies": ["문장1", "문장2", "문장3"],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

---

## 5. 모델별 결과 요약

| 모델 | 응답 시간 | JSON 안정성 | 한국어 자연스러움 | 추천 답변 품질 | 판단 |
|---|---:|---|---|---|---|
| EXAONE-4.0-1.2B | 3.59초 | 낮음 | 낮음~보통 | 낮음 | 속도 baseline |
| HyperCLOVA X SEED 1.5B | 2.79초 | 낮음~보통 | 좋음 | 보통 | 보류 |
| Kanana 1.5 2.1B Instruct | 4.04초 | 낮음 | 좋음 | 확인 불가 | 보류 |

---

## 6. 모델별 세부 판단

### ① EXAONE-4.0-1.2B

```text
결과:
- 응답 시간은 3.59초로 매우 빠르게 측정되었다.
- markdown 코드블록이 포함되었다.
- JSON이 should_end_call 필드에서 중간에 잘렸다.
- "okay해요"처럼 영어가 섞인 표현이 생성되었다.
- "예약해 드리겠습니다"처럼 예약 가능 여부를 임의로 확정하는 문장이 생성되었다.
- recommended_replies가 사용자/환자 입장으로 자연스럽지 않았다.

판단:
- 속도 측면에서는 가장 강한 후보이다.
- 그러나 JSON 완성 안정성과 한국어 자연스러움이 부족하다.
- 최종 모델 후보라기보다는 속도 baseline으로 유지한다.
```

---

### ② HyperCLOVA X SEED 1.5B

```text
결과:
- 응답 시간은 2.79초로 가장 빠르게 측정되었다.
- 첫 번째 JSON은 생성되었지만 markdown 코드블록이 포함되었다.
- conversation_state와 should_end_call 필드가 누락되었다.
- JSON 이후 다시 같은 형식의 응답을 반복 생성했다.
- 병원 예약이 많이 몰려 자리가 부족하다는 응답은 실제 상황에서는 자연스러울 수 있으나, 현재 프롬프트에는 예약 현황 정보가 없었기 때문에 모델이 상황을 임의로 확장한 것으로 볼 수 있다.
- recommended_replies 일부가 사용자 입장으로 자연스럽지만, 일부는 병원 직원 질문처럼 보인다.

판단:
- 한국어 문장 자체는 자연스럽고 실제 전화 상황처럼 확장하는 능력이 있다.
- 그러나 통제된 평가 기준에서는 제공되지 않은 상황 정보를 임의로 추가하는 경향이 있다.
- 반복 출력과 필드 누락 문제가 있어 단독 JSON 생성 모델로 사용하기는 어렵다.
- 상태 기반 시나리오 제어와 후처리를 함께 사용할 필요가 있다.
```

---

### ③ Kanana 1.5 2.1B Instruct

```text
결과:
- 응답 시간은 4.04초로 측정되었다.
- ai_message는 병원 접수 직원 말투에 가깝고 자연스러웠다.
- 필요한 정보인 진료과와 시간대를 묻는 방향은 적절했다.
- 그러나 ai_message가 너무 길어졌고, recommended_replies가 중간에 깨졌다.
- JSON이 끝까지 완성되지 않아 conversation_state와 should_end_call을 확인할 수 없었다.

판단:
- 한국어 전화 응대 말투는 가장 자연스러운 편이다.
- 그러나 구조화 출력 안정성이 낮고 JSON 완성에 실패했다.
- 자연어 응답 생성 후보로는 가치가 있지만, JSON 직접 생성 모델로는 불안정하다.
```

---

## 7. 3차 테스트 결론

```text
3차 Strict JSON Prompt 테스트 결과, 프롬프트를 짧게 줄이고 JSON 객체 하나만 출력하도록 강하게 지시해도 모든 모델에서 JSON 안정성 문제가 발생했다.

EXAONE은 가장 빠른 속도를 유지했지만 JSON이 중간에 잘리고 영어 혼합 표현이 발생했다.

HyperCLOVA X SEED 1.5B는 가장 빠르고 한국어 문장도 자연스러웠지만, markdown 코드블록 출력, 필드 누락, 반복 출력 문제가 있었다. 다만 실제 병원 예약 상황처럼 자연스럽게 상황을 확장하는 능력은 확인되었다.

Kanana 1.5 2.1B는 병원 접수 직원 말투와 대화 흐름은 가장 자연스러웠지만, 응답이 길어지며 JSON이 완성되지 않았다.

따라서 현재까지의 결론은 LLM이 완성된 JSON 전체를 직접 생성하게 하는 방식은 안정성이 낮다는 것이다.
```

---

## 8. 구조적 판단

```text
마음콜 서비스에서는 LLM이 ai_message, recommended_replies, conversation_state, should_end_call을 모두 포함한 완성 JSON을 직접 생성하게 하기보다, 역할을 분리하는 방식이 더 안정적이다.

추천 구조:
1. LLM은 병원 접수 직원의 자연어 응답 후보를 생성한다.
2. conversation_state는 LangGraph 또는 서버 상태 머신에서 결정한다.
3. should_end_call은 서버 로직에서 결정한다.
4. recommended_replies는 별도 규칙 기반 템플릿, 별도 추천 모델, 또는 상태별 후보 문장으로 생성한다.
5. FastAPI 서버에서 최종 JSON을 조립한다.
```

---

## 9. 현재 최종 후보 판단

| 모델 | 최종 역할 |
|---|---|
| EXAONE-4.0-1.2B | 속도 baseline, 후처리 전제 후보 |
| Kanana 1.5 2.1B Instruct | 자연스러운 전화 응대 말투 후보 |
| HyperCLOVA X SEED 1.5B | 자연스러운 한국어 확장 후보, 상태 제어 필요 |
| Gemma-ko-2B | 2차 기준 JSON 구조 생성 실패로 제외 |

---

## 10. 다음 진행

```text
1. 완성 JSON 직접 생성 방식에서 서버 조립 방식으로 구조 변경 검토
2. LLM은 ai_message만 생성하도록 역할 축소
3. recommended_replies는 상태별 템플릿 또는 별도 추천 로직으로 분리
4. conversation_state와 should_end_call은 LangGraph/서버 로직에서 결정
5. EXAONE, Kanana, HyperCLOVA를 ai_message 생성 전용으로 재평가
```