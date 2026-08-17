# 병원 예약 시나리오 상태 설계

> 상태: 병원 예약 상세 그래프의 초기 설계 기록. 최신 코드와 전체 라우팅 구조는 [`services/flow/README.md`](../../services/flow/README.md)를 기준으로 한다.

## 1. 목적

이 문서는 마음콜의 병원 예약 전화 시나리오를 상태 기반으로 설계하기 위한 문서이다.

기존 Hugging Face 모델 비교에서는 LLM이 `ai_message`, `recommended_replies`, `conversation_state`, `should_end_call`을 포함한 완성 JSON을 직접 생성하도록 테스트했다.

그러나 여러 테스트에서 다음 문제가 반복적으로 발생했다.

```text
- JSON 중간 잘림
- conversation_state 필드 누락
- should_end_call 필드 누락
- recommended_replies 역할 혼동
- 모델별 상태 판단 불일치
```

따라서 병원 예약 시나리오에서는 LLM이 전체 응답 구조를 직접 생성하지 않고, 다음과 같이 역할을 분리한다.

```text
LLM → ai_message 생성
상태 머신 / LangGraph → conversation_state 결정
상태별 템플릿 → recommended_replies 생성
서버 로직 → should_end_call 결정
FastAPI → 최종 JSON 조립
```

---

## 2. 병원 예약 시나리오 전체 흐름

병원 예약 전화는 다음 상태 흐름을 기준으로 진행한다.

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

다만 사용자가 처음부터 여러 정보를 한 번에 말할 수 있으므로, 항상 순서대로만 진행하지는 않는다.

예를 들어 사용자가 처음부터 다음과 같이 말할 수 있다.

```text
내일 오후 3시에 내과 예약하고 싶어요.
```

이 경우에는 이미 다음 정보가 포함되어 있다.

```text
진료과: 내과
날짜: 내일
시간: 오후 3시
목적: 예약
```

따라서 상태 머신은 불필요한 질문을 건너뛰고 `confirming_info` 단계로 이동할 수 있어야 한다.

---

## 3. 상태 목록

| 상태 | 의미 | 필요한 정보 | 다음 목표 |
|-----|-----|----------|---------|
| greeting | 통화 시작 및 인사 | 없음 | 전화 목적 확인 |
| asking_purpose | 전화 목적 확인 | 예약 / 변경 / 취소 / 문의 | 예약 목적 파악 |
| asking_department | 진료과 확인 | 내과, 피부과, 정형외과 등 | 진료과 수집 |
| asking_date | 예약 날짜 확인 | 오늘, 내일, 특정 날짜 | 날짜 수집 |
| asking_time | 예약 시간 확인 | 오전, 오후, 3시 등 | 시간 수집 |
| confirming_info | 예약 정보 확인 | 진료과, 날짜, 시간, 이름, 연락처 | 예약 정보 확인 |
| closing | 통화 마무리 | 최종 확인 여부 | 통화 종료 |
| END | 통화 종료 | 없음 | should_end_call = true |

---

## 4. 상태별 필요 정보

### 4.1 greeting

#### 목적

사용자에게 자연스럽게 전화를 시작하는 인사 단계이다.

#### 필요한 정보

```text
없음
```

#### 다음 상태

```text
asking_purpose
```

#### ai_message 예시

```text
안녕하세요, 마음병원입니다. 무엇을 도와드릴까요?
```

#### recommended_replies 예시

```python
[
    "진료 예약을 하고 싶습니다.",
    "예약 가능한 시간을 문의하고 싶습니다.",
    "처음 방문인데 예약이 가능할까요?"
]
```

---

### 4.2 asking_purpose

#### 목적

사용자가 전화를 건 목적을 확인한다.

#### 필요한 정보

```text
예약 / 변경 / 취소 / 문의
```

#### 다음 상태 규칙

```text
예약 의도가 있으면 → asking_department
예약 변경 의도가 있으면 → changing_reservation
예약 취소 의도가 있으면 → canceling_reservation
단순 문의이면 → general_inquiry
```

현재 `병원 예약` 등록 키의 계약은 신규 예약 흐름을 소유한다. 예약 의도가 확인되면 `asking_department`로 이동하며, 변경·취소는 별도 제품 시나리오와 처리 계약이 정의되기 전까지 지원하는 것처럼 추정하지 않는다.

#### ai_message 예시

```text
네, 진료 예약을 도와드리겠습니다. 원하시는 진료과가 있으실까요?
```

#### recommended_replies 예시

```python
[
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 어느 과로 예약하면 될까요?",
    "증상이 있어서 진료과를 상담받고 싶습니다."
]
```

---

### 4.3 asking_department

#### 목적

사용자가 아직 진료과를 말하지 않았을 때 진료과를 확인한다.

#### 필요한 정보

```text
진료과
```

#### 다음 상태 규칙

```text
진료과가 확인되면:
- 날짜 정보가 없으면 → asking_date
- 날짜 정보가 있으면 → asking_time
- 날짜와 시간 정보가 모두 있으면 → confirming_info
```

#### ai_message 예시

```text
네, 내일 오후에 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 바로 확인해드리겠습니다.
```

#### recommended_replies 예시

```python
[
    "내과 진료를 예약하고 싶습니다.",
    "피부과 진료를 예약하고 싶습니다.",
    "어느 과로 가야 할지 상담받고 싶습니다."
]
```

---

### 4.4 asking_date

#### 목적

진료과는 확인되었지만 예약 날짜가 없을 때 날짜를 확인한다.

#### 필요한 정보

```text
예약 날짜
```

#### 다음 상태 규칙

```text
날짜가 확인되면:
- 시간 정보가 없으면 → asking_time
- 시간 정보가 있으면 → confirming_info
```

#### ai_message 예시

```text
네, 확인해드리겠습니다. 원하시는 예약 날짜를 말씀해주시겠어요?
```

#### recommended_replies 예시

```python
[
    "내일로 예약하고 싶습니다.",
    "이번 주 금요일에 가능할까요?",
    "가능한 가장 빠른 날짜로 예약하고 싶습니다."
]
```

---

### 4.5 asking_time

#### 목적

진료과와 날짜는 확인되었지만 예약 시간이 없을 때 시간대를 확인한다.

#### 필요한 정보

```text
예약 시간
```

#### 다음 상태

```text
confirming_info
```

#### ai_message 예시

```text
네, 확인해드리겠습니다. 원하시는 시간대를 말씀해주시겠어요?
```

#### recommended_replies 예시

```python
[
    "오후 3시쯤 가능할까요?",
    "가능한 오후 시간대를 알려주세요.",
    "가장 빠른 오후 시간으로 예약하고 싶습니다."
]
```

---

### 4.6 confirming_info

#### 목적

수집한 예약 정보를 사용자에게 확인한다.

#### 필요한 정보

```text
진료과
날짜
시간
이름
```

예약 대상을 식별하기 위해 이름은 필수로 수집한다. 현재 가용성 공급자와 예약 계약에서 사용하지 않는 연락처는 개인정보 최소 수집 원칙에 따라 받지 않는다.

#### 다음 상태 규칙

```text
사용자가 확인하면 → checking_availability
사용자가 수정 요청하면 → 해당 정보 상태로 이동
```

예시:

```text
시간을 바꾸고 싶어요 → asking_time
날짜를 바꾸고 싶어요 → asking_date
진료과를 바꾸고 싶어요 → asking_department
```

#### ai_message 예시

```text
말씀해주신 내용으로 확인해드리겠습니다. 내일 오후 내과 진료 예약을 원하시는 것이 맞으실까요?
```

#### recommended_replies 예시

```python
[
    "네, 맞습니다.",
    "시간을 다시 확인하고 싶습니다.",
    "연락처를 다시 말씀드릴게요."
]
```

---

### 4.7 closing

#### 목적

통화를 자연스럽게 마무리한다.

#### 필요한 정보

```text
최종 확인 여부
```

#### 다음 상태

```text
END
```

#### ai_message 예시

```text
네, 확인 감사합니다. 추가로 궁금하신 점이 없으시면 통화 마무리 도와드리겠습니다.
```

#### recommended_replies 예시

```python
[
    "네, 감사합니다.",
    "확인했습니다. 감사합니다.",
    "수고하세요."
]
```

---

## 5. 상태 전이 규칙

## 5.1 기본 전이

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

---

## 5.2 정보 기반 전이

사용자 발화에서 이미 포함된 정보는 다시 묻지 않는다.

| 사용자 발화 정보 | 다음 상태 |
|---|---|
| 예약 의도만 있음 | asking_department |
| 예약 의도 + 진료과 있음 | asking_date |
| 예약 의도 + 진료과 + 날짜 있음 | asking_time |
| 예약 의도 + 진료과 + 날짜 + 시간 있음 | confirming_info |
| confirming_info 상태에서 “네”, “맞습니다” | closing |
| closing 상태에서 감사/종료 표현 | END |

---

## 6. 예시 상태 전이

### 예시 1

#### 사용자 발화

```text
저기... 내일 오후에 진료 예약 가능할까요?
```

#### 추출 정보

```json
{
  "intent": "reservation",
  "department": null,
  "date": "내일",
  "time": "오후"
}
```

#### 다음 상태

```text
asking_department
```

#### 최종 응답 예시

```json
{
  "ai_message": "네, 내일 오후에 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 바로 확인해드리겠습니다.",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "피부과 진료를 예약하고 싶습니다.",
    "어느 과로 가야 할지 상담받고 싶습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

---

### 예시 2

#### 사용자 발화

```text
내과 진료를 예약하고 싶습니다.
```

#### 추출 정보

```json
{
  "intent": "reservation",
  "department": "내과",
  "date": null,
  "time": null
}
```

#### 다음 상태

```text
asking_date
```

#### 최종 응답 예시

```json
{
  "ai_message": "네, 내과 진료 예약을 도와드리겠습니다. 원하시는 날짜를 말씀해주시겠어요?",
  "recommended_replies": [
    "내일로 예약하고 싶습니다.",
    "이번 주 금요일에 가능할까요?",
    "가능한 가장 빠른 날짜로 예약하고 싶습니다."
  ],
  "conversation_state": "asking_date",
  "should_end_call": false
}
```

---

### 예시 3

#### 사용자 발화

```text
내일 오후 3시쯤 가능할까요?
```

#### 기존 상태

```json
{
  "conversation_state": "asking_time",
  "department": "내과",
  "date": "내일",
  "time": null
}
```

#### 추출 정보

```json
{
  "time": "오후 3시"
}
```

#### 다음 상태

```text
confirming_info
```

#### 최종 응답 예시

```json
{
  "ai_message": "말씀해주신 내용으로 확인해드리겠습니다. 내일 오후 3시 내과 진료 예약을 원하시는 것이 맞으실까요?",
  "recommended_replies": [
    "네, 맞습니다.",
    "시간을 다시 확인하고 싶습니다.",
    "연락처를 다시 말씀드릴게요."
  ],
  "conversation_state": "confirming_info",
  "should_end_call": false
}
```

---

## 7. recommended_replies 템플릿

```python
RECOMMENDED_REPLIES = {
    "greeting": [
        "진료 예약을 하고 싶습니다.",
        "예약 가능한 시간을 문의하고 싶습니다.",
        "처음 방문인데 예약이 가능할까요?"
    ],
    "asking_purpose": [
        "진료 예약을 하고 싶습니다.",
        "예약 시간을 변경하고 싶습니다.",
        "예약 관련해서 문의드리고 싶습니다."
    ],
    "asking_department": [
        "내과 진료를 예약하고 싶습니다.",
        "피부과 진료를 예약하고 싶습니다.",
        "어느 과로 가야 할지 상담받고 싶습니다."
    ],
    "asking_date": [
        "내일로 예약하고 싶습니다.",
        "이번 주 금요일에 가능할까요?",
        "가능한 가장 빠른 날짜로 예약하고 싶습니다."
    ],
    "asking_time": [
        "오후 3시쯤 가능할까요?",
        "가능한 오후 시간대를 알려주세요.",
        "가장 빠른 오후 시간으로 예약하고 싶습니다."
    ],
    "confirming_info": [
        "네, 맞습니다.",
        "시간을 다시 확인하고 싶습니다.",
        "연락처를 다시 말씀드릴게요."
    ],
    "closing": [
        "네, 감사합니다.",
        "확인했습니다. 감사합니다.",
        "수고하세요."
    ]
}
```

---

## 8. 상태 판단 의사코드

```python
def determine_next_state(state: dict, extracted: dict) -> str:
    current_state = state.get("conversation_state", "greeting")

    department = extracted.get("department") or state.get("department")
    date = extracted.get("date") or state.get("date")
    time = extracted.get("time") or state.get("time")
    intent = extracted.get("intent") or state.get("intent")

    if current_state == "greeting":
        return "asking_purpose"

    if current_state == "asking_purpose":
        if intent == "reservation":
            if not department:
                return "asking_department"
            if not date:
                return "asking_date"
            if not time:
                return "asking_time"
            return "confirming_info"
        return "asking_purpose"

    if current_state == "asking_department":
        if department:
            if not date:
                return "asking_date"
            if not time:
                return "asking_time"
            return "confirming_info"
        return "asking_department"

    if current_state == "asking_date":
        if date:
            if not time:
                return "asking_time"
            return "confirming_info"
        return "asking_date"

    if current_state == "asking_time":
        if time:
            return "confirming_info"
        return "asking_time"

    if current_state == "confirming_info":
        if extracted.get("confirmed"):
            return "closing"
        if extracted.get("change_target") == "department":
            return "asking_department"
        if extracted.get("change_target") == "date":
            return "asking_date"
        if extracted.get("change_target") == "time":
            return "asking_time"
        return "confirming_info"

    if current_state == "closing":
        return "END"

    return current_state
```

---

## 9. FastAPI 응답 조립 구조

FastAPI는 다음 순서로 응답을 만든다.

```text
1. 사용자 발화 수신
2. 기존 state 조회
3. 사용자 발화에서 intent, department, date, time 추출
4. 다음 conversation_state 결정
5. 현재 상태에 맞는 ai_message 프롬프트 생성
6. LLM으로 ai_message 생성
7. 상태별 recommended_replies 선택
8. should_end_call 결정
9. 최종 JSON 조립
```

---

## 10. FastAPI 응답 예시

```json
{
  "ai_message": "네, 내일 오후에 진료 예약을 원하시는군요. 원하시는 진료과를 알려주시면 바로 확인해드리겠습니다.",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "피부과 진료를 예약하고 싶습니다.",
    "어느 과로 가야 할지 상담받고 싶습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}
```

---

## 11. 다음 구현 방향

```text
1. hospital_reservation_state_design.md 기준으로 상태 전이 코드를 작성한다.
2. 상태별 recommended_replies 템플릿을 별도 파일로 분리한다.
3. LLM Provider는 ai_message만 반환하도록 수정한다.
4. FastAPI 라우터에서 최종 JSON을 조립한다.
5. 이후 병원 예약 시나리오가 안정화되면 professor, cityhall, family 등 다른 시나리오로 확장한다.
```
