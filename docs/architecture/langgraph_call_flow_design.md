# LangGraph 기반 통화 흐름 상태 설계

> 상태: 구현 전 의사결정 기록(ADR). 현재 구현은 이 설계를 바탕으로 예약·교수님 상세 그래프와 25개 선언형 공통 그래프로 확장되었다. 최신 구조는 [`services/flow/README.md`](../../services/flow/README.md)를 기준으로 한다.

## 1. 목적

마음콜 통화 시뮬레이션에서는 사용자가 실제 전화 상황에 익숙해질 수 있도록, 병원 예약과 같은 시나리오를 단계적으로 연습할 수 있어야 한다.

기존 Hugging Face 모델 비교에서는 LLM이 다음 값을 모두 포함한 완성 JSON을 직접 생성하도록 테스트했다.

```json
{
  "ai_message": "...",
  "recommended_replies": ["...", "...", "..."],
  "conversation_state": "...",
  "should_end_call": false
}
```

그러나 1차, 2차, 3차 테스트 결과 다음 문제가 반복적으로 발생했다.

```text
- JSON 중간 잘림
- 필드 누락
- markdown 코드블록 출력
- assistant 블록 반복 출력
- recommended_replies 역할 혼동
- conversation_state 판단 불안정
- should_end_call 판단 불안정
```

반면 4차 ai_message 전용 테스트에서는 LLM에게 병원 접수 직원의 자연어 응답만 생성하게 했을 때 출력 안정성과 응답 속도가 크게 개선되었다.

따라서 마음콜은 다음 구조로 전환한다.

```text
LLM은 ai_message만 생성한다.
conversation_state는 LangGraph 또는 서버 상태 머신이 결정한다.
recommended_replies는 상태별 템플릿 또는 추천 로직이 생성한다.
should_end_call은 서버 로직이 결정한다.
FastAPI가 최종 JSON을 조립한다.
```

---

## 2. 전체 구조

### 기존 방식

```text
사용자 발화
→ LLM 호출
→ LLM이 완성 JSON 생성
→ Flutter에서 JSON 파싱
```

### 문제점

```text
- LLM 출력이 항상 JSON으로 보장되지 않음
- conversation_state가 불안정함
- recommended_replies가 병원 직원 말투로 생성될 수 있음
- should_end_call 판단이 모델마다 달라질 수 있음
```

---

### 개선 방식

```text
사용자 발화
→ LangGraph / 서버 상태 머신이 현재 상태 판단
→ LLM은 현재 상태에 맞는 ai_message만 생성
→ recommended_replies는 상태별 템플릿으로 생성
→ should_end_call은 서버 로직으로 결정
→ FastAPI가 최종 JSON 조립
→ Flutter로 전달
```

---

## 3. 역할 분리

| 항목 | 담당 | 설명 |
|---|---|---|
| ai_message | LLM | 병원 접수 직원의 자연어 응답 생성 |
| conversation_state | LangGraph / 상태 머신 | 현재 대화 단계 판단 |
| recommended_replies | 상태별 템플릿 / 추천 로직 | 사용자가 다음에 말할 수 있는 문장 제공 |
| should_end_call | 서버 로직 | 통화 종료 가능 여부 판단 |
| 최종 JSON 조립 | FastAPI | Flutter로 전달할 응답 구조 생성 |

---

## 4. 병원 예약 시나리오 상태 정의

병원 예약 전화는 다음 상태 흐름으로 구성한다.

```text
START
→ greeting
→ asking_purpose
→ asking_department
→ asking_date
→ asking_time
→ confirming_info
→ closing
→ END
```

---

## 5. 상태별 의미

| 상태 | 의미 | 필요한 정보 |
|---|---|---|
| greeting | 통화 시작 및 인사 | 없음 |
| asking_purpose | 사용자의 전화 목적 확인 | 예약 / 문의 / 변경 / 취소 |
| asking_department | 진료과 확인 | 내과, 피부과, 정형외과 등 |
| asking_date | 예약 날짜 확인 | 오늘, 내일, 특정 날짜 |
| asking_time | 예약 시간 확인 | 오전, 오후, 3시 등 |
| confirming_info | 예약 정보 확인 | 진료과, 날짜, 시간, 이름, 연락처 |
| closing | 통화 마무리 | 예약 확인 또는 종료 인사 |
| END | 통화 종료 | should_end_call = true |

---

## 6. 병원 예약 상태 전이 규칙

### 6.1 기본 흐름

```text
greeting
→ asking_purpose
→ asking_department
→ asking_date
→ asking_time
→ confirming_info
→ closing
→ END
```

### 6.2 사용자 발화 기반 상태 판단 예시

#### 예시 1

```text
사용자 발화:
저기... 내일 오후에 진료 예약 가능할까요?
```

분석:

```text
예약 의도 있음
날짜 정보 있음: 내일
시간 정보 있음: 오후
진료과 정보 없음
```

다음 상태:

```text
asking_department
```

---

#### 예시 2

```text
사용자 발화:
내과 진료를 예약하고 싶습니다.
```

분석:

```text
진료과 정보 있음: 내과
날짜 정보 없음
시간 정보 없음
```

다음 상태:

```text
asking_date
```

---

#### 예시 3

```text
사용자 발화:
내일 오후 3시쯤 가능할까요?
```

분석:

```text
날짜 정보 있음: 내일
시간 정보 있음: 오후 3시
진료과 정보가 이미 state에 저장되어 있다면 다음 단계로 이동 가능
```

다음 상태:

```text
confirming_info
```

---

#### 예시 4

```text
사용자 발화:
네, 맞습니다.
```

현재 상태가 `confirming_info`라면 다음 상태:

```text
closing
```

---

## 7. 상태 데이터 구조

LangGraph 또는 서버 상태 머신에서 관리할 상태는 다음과 같다.

```python
class CallState:
    user_message: str
    scenario_type: str
    conversation_state: str

    department: str | None
    date: str | None
    time: str | None
    user_name: str | None
    phone_number: str | None

    ai_message: str | None
    recommended_replies: list[str]
    should_end_call: bool
```

예시 상태:

```json
{
  "scenario_type": "hospital_reservation",
  "conversation_state": "asking_department",
  "department": null,
  "date": "내일",
  "time": "오후",
  "user_name": null,
  "phone_number": null,
  "should_end_call": false
}
```

---

## 8. 상태별 ai_message 생성 방향

LLM은 현재 상태에 맞는 자연어 응답만 생성한다.

### asking_department

```text
목표:
사용자가 아직 진료과를 말하지 않았으므로 진료과를 부드럽게 묻는다.

프롬프트 방향:
현재 상태는 asking_department이다.
사용자는 내일 오후 진료 예약을 문의했다.
아직 진료과를 말하지 않았다.
병원 접수 직원처럼 진료과를 부드럽게 물어봐라.
예약 가능 여부는 확정하지 마라.
한 문장만 출력해라.
```

예상 응답:

```text
네, 내일 오후 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 확인해드리겠습니다.
```

---

### asking_date

```text
목표:
진료과는 확인되었지만 날짜가 없으므로 날짜를 묻는다.
```

예상 응답:

```text
네, 확인해드리겠습니다. 원하시는 예약 날짜를 말씀해주시겠어요?
```

---

### asking_time

```text
목표:
날짜는 확인되었지만 시간이 없으므로 시간대를 묻는다.
```

예상 응답:

```text
네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?
```

---

### confirming_info

```text
목표:
수집한 예약 정보를 확인한다.
```

예상 응답:

```text
말씀해주신 내용으로 확인해드리겠습니다. 내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?
```

---

### closing

```text
목표:
통화를 자연스럽게 마무리한다.
```

예상 응답:

```text
네, 확인 감사합니다. 추가로 궁금하신 점이 없으시면 통화 마무리 도와드리겠습니다.
```

---

## 9. 상태별 recommended_replies 템플릿

recommended_replies는 LLM이 직접 생성하지 않고 상태별 템플릿으로 제공한다.

### asking_department

```python
[
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 어느 과로 예약하면 될까요?",
    "증상이 있어서 진료과를 상담받고 싶습니다."
]
```

### asking_date

```python
[
    "내일로 예약하고 싶습니다.",
    "이번 주 금요일에 가능할까요?",
    "가능한 가장 빠른 날짜로 예약하고 싶습니다."
]
```

### asking_time

```python
[
    "오후 3시쯤 가능할까요?",
    "가능한 오후 시간대를 알려주세요.",
    "가장 빠른 오후 시간으로 예약하고 싶습니다."
]
```

### confirming_info

```python
[
    "네, 맞습니다.",
    "시간을 다시 확인하고 싶습니다.",
    "연락처를 다시 말씀드릴게요."
]
```

### closing

```python
[
    "네, 감사합니다.",
    "확인했습니다. 감사합니다.",
    "수고하세요."
]
```

---

## 10. 상태 전이 의사코드

```python
def determine_next_state(state: dict) -> str:
    current_state = state["conversation_state"]
    user_message = state["user_message"]

    has_reservation_intent = contains_any(user_message, ["예약", "진료", "가능"])
    has_department = contains_any(user_message, ["내과", "피부과", "정형외과", "외과", "이비인후과"])
    has_date = contains_any(user_message, ["오늘", "내일", "모레", "월요일", "화요일", "수요일", "목요일", "금요일"])
    has_time = contains_any(user_message, ["오전", "오후", "시", "반", "분"])

    if current_state in ["greeting", "asking_purpose"]:
        if has_reservation_intent:
            if not state.get("department") and not has_department:
                return "asking_department"
            if not state.get("date") and not has_date:
                return "asking_date"
            if not state.get("time") and not has_time:
                return "asking_time"
            return "confirming_info"

    if current_state == "asking_department":
        if has_department:
            return "asking_date" if not state.get("date") else "asking_time"
        return "asking_department"

    if current_state == "asking_date":
        if has_date:
            return "asking_time"
        return "asking_date"

    if current_state == "asking_time":
        if has_time:
            return "confirming_info"
        return "asking_time"

    if current_state == "confirming_info":
        if contains_any(user_message, ["네", "맞아요", "맞습니다", "확인했습니다"]):
            return "closing"
        return "confirming_info"

    if current_state == "closing":
        return "END"

    return current_state
```

---

## 11. FastAPI 최종 JSON 조립 구조

FastAPI는 다음 순서로 응답을 만든다.

```text
1. 사용자 발화를 받는다.
2. 현재 conversation_state와 사용자 발화를 기반으로 다음 상태를 결정한다.
3. 상태에 따라 LLM 프롬프트를 만든다.
4. LLM에게 ai_message만 생성하게 한다.
5. 상태별 recommended_replies를 가져온다.
6. should_end_call을 결정한다.
7. 최종 JSON을 조립한다.
```

최종 응답 예시:

```json
{
  "ai_message": "네, 내일 오후 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 확인해드리겠습니다.",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 어느 과로 예약하면 될까요?",
    "증상이 있어서 진료과를 상담받고 싶습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

---

## 12. FastAPI 응답 조립 의사코드

```python
def build_call_response(user_message: str, state: dict) -> dict:
    state["user_message"] = user_message

    next_state = determine_next_state(state)
    state["conversation_state"] = next_state

    ai_message = generate_ai_message_with_llm(state)

    recommended_replies = get_recommended_replies(next_state)

    should_end_call = next_state == "END"

    return {
        "ai_message": ai_message,
        "recommended_replies": recommended_replies,
        "conversation_state": next_state,
        "should_end_call": should_end_call,
    }
```

---

## 13. 기대 효과

| 기존 방식 | 개선 방식 |
|---|---|
| LLM이 JSON 전체 생성 | FastAPI가 JSON 조립 |
| JSON 깨짐 가능 | JSON 구조 안정 |
| 상태 판단 불안정 | LangGraph 상태 전이로 관리 |
| 추천 답변 역할 혼동 | 상태별 템플릿으로 고정 |
| 종료 판단 불안정 | 서버 로직으로 결정 |
| 모델 출력 제어 어려움 | LLM은 자연어 응답에 집중 |

---

## 14. 현재 모델 적용 방향

| 모델 | 역할 |
|---|---|
| Kanana 1.5 2.1B Instruct | 메인 ai_message 생성 후보 |
| EXAONE-4.0-1.2B | 속도 비교 기준 모델 |
| HyperCLOVA X SEED 1.5B | 한국어 자연스러움 참고 후보 |
| Gemma-ko-2B | 제외 |

---

## 15. 다음 진행

```text
1. LangGraph 상태 흐름을 Python 코드로 구현한다.
2. 병원 예약 시나리오용 상태 전이 함수를 작성한다.
3. 상태별 recommended_replies 템플릿을 코드로 분리한다.
4. LLM Provider는 ai_message만 반환하도록 수정한다.
5. FastAPI 라우터에서 최종 JSON을 조립한다.
6. Flutter 기존 응답 구조와 연결한다.
```
