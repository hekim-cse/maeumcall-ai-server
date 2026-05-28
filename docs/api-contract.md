# API Contract

이 문서는 Flutter 앱과 maeum-call-ai-server 사이의 API 연동 규칙을 정리한다.

현재 핵심 API는 병원 예약 시나리오를 포함한 통화 시뮬레이션용 /chat API이다.

---

## POST /chat

사용자 발화와 현재 시나리오 상태를 서버로 보내면, 서버는 다음 AI 응답과 갱신된 상태를 반환한다.

---

## Request Body

### category

시나리오 카테고리이다.

예시:

- 예약
- 문의
- 상담

### title

시나리오 제목이다.

예시:

- 병원 예약

### description

시나리오 설명이다.

예시:

- 병원 진료 예약 전화 상황

### userMessage

사용자의 현재 발화이다.

예시:

- 내일 오후에 내과 진료 예약 가능할까요?
- 네, 맞습니다.
- 오후 4시로 하겠습니다.

### conversationState

현재 대화 상태이다.

초기 요청에서는 greeting을 사용한다.

예시:

- greeting
- asking_department
- asking_date
- asking_time
- confirming_info
- checking_availability
- reservation_available
- reservation_unavailable
- suggest_alternative
- reservation_confirmed
- closing
- END

### scenarioState

서버가 이전 응답에서 내려준 시나리오 상태 객체이다.

Flutter는 이 값을 그대로 저장했다가 다음 /chat 요청에 다시 전달한다.

초기 요청에서는 빈 객체를 보낼 수 있다.

예시:

    {}

### history

이전 대화 기록이다.

서버는 history를 사용하여 LLM 응답 반복을 줄이고, 문맥 기반 응답 검증에 활용한다.

형식:

- role: user 또는 assistant
- content: 발화 내용

---

## Request Example

    {
      "category": "예약",
      "title": "병원 예약",
      "description": "병원 진료 예약 전화 상황",
      "userMessage": "내일 오후에 내과 진료 예약 가능할까요?",
      "conversationState": "greeting",
      "scenarioState": {},
      "history": []
    }

---

## Response Body

### response

사용자에게 보여줄 AI 응답 문장이다.

Flutter의 채팅 UI에는 이 값을 표시한다.

### etiquetteTip

통화 예절 또는 말하기 팁이다.

현재는 null일 수 있다.

### recommendedReplies

사용자에게 추천할 답변 목록이다.

Flutter에서는 추천 답변 버튼 또는 칩 UI로 표시할 수 있다.

### conversationState

서버가 갱신한 현재 대화 상태이다.

Flutter는 이 값을 저장한 뒤 다음 요청의 conversationState로 다시 전달한다.

### shouldEndCall

통화를 종료해야 하는지 여부이다.

true이면 Flutter는 통화 종료 처리 또는 결과 화면 이동을 수행한다.

### scenarioState

갱신된 시나리오 상태 객체이다.

Flutter는 이 값을 그대로 저장한 뒤 다음 요청에 다시 전달한다.

---

## Response Example

    {
      "response": "네, 내일 오후 3시에 내과 진료 예약이 가능합니다. 이 시간으로 진행하시겠습니까?",
      "etiquetteTip": null,
      "recommendedReplies": [
        "네, 그 시간으로 예약하고 싶습니다.",
        "다른 시간도 확인할 수 있을까요?",
        "잠시만요, 시간을 다시 확인해볼게요."
      ],
      "conversationState": "reservation_available",
      "shouldEndCall": false,
      "scenarioState": {
        "intent": "reservation",
        "department": "내과",
        "date": "내일",
        "time": "오후",
        "conversation_state": "reservation_available",
        "availability_status": "available",
        "available_time": "오후 3시",
        "alternative_times": [],
        "reservation_confirmed": null
      }
    }

---

## Flutter 저장 규칙

Flutter는 /chat 응답을 받은 뒤 다음 값을 저장해야 한다.

- conversationState
- scenarioState
- recommendedReplies
- shouldEndCall

다음 요청에서는 저장된 conversationState와 scenarioState를 다시 서버에 전달해야 한다.

---

## history 누적 규칙

Flutter는 사용자의 발화와 AI 응답을 순서대로 누적한다.

예시:

    [
      {
        "role": "user",
        "content": "내일 오후에 진료 예약 가능할까요?"
      },
      {
        "role": "assistant",
        "content": "원하시는 진료과를 알려주시겠어요?"
      }
    ]

주의 사항:

- 현재 전송하는 userMessage와 history의 마지막 user 발화가 중복되지 않도록 관리한다.
- 서버는 history를 LLM 응답 생성 및 검증에 참고한다.

---

## 통화 종료 규칙

서버 응답에서 shouldEndCall이 true이면 Flutter는 통화를 종료한다.

예시:

    {
      "conversationState": "END",
      "shouldEndCall": true
    }

Flutter 처리 예시:

- STT 중지
- 녹음 종료
- 음성 분석 요청
- 통화 결과 화면 이동
