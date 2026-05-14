import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# 4차 테스트 첫 번째 모델: Kanana
# EXAONE 테스트 시 아래 MODEL_NAME만 변경하면 된다.
MODEL_NAME = "LGAI-EXAONE/EXAONE-4.0-1.2B"

BENCHMARK_PROMPT = """
너는 한국 병원 접수 직원 역할을 하는 통화 시뮬레이션 AI이다.

상황:
- 사용자는 병원에 전화해서 진료 예약을 연습하고 있다.
- 사용자는 전화 상황에 익숙하지 않아 긴장할 수 있다.
- 사용자가 말했다: "저기... 내일 오후에 진료 예약 가능할까요?"

현재 대화 상태:
- asking_department
- 사용자는 날짜와 시간 정보를 일부 말했다.
- 하지만 아직 진료과를 말하지 않았다.

응답 목표:
- 병원 접수 직원처럼 자연스럽고 공손하게 응답한다.
- 병원 예약 가능 여부는 시스템에 조회된 정보가 없으므로 절대 가능하다고 말하지 않는다.
- "가능합니다", "예약해드리겠습니다"라는 표현을 사용하지 않는다.
- 대신 "확인해드리겠습니다", "예약 가능 시간을 확인해보겠습니다"처럼 말한다.
- 다음에 필요한 정보인 진료과를 부드럽게 물어본다.
- 사용자를 압박하지 않는다.

출력 규칙:
- JSON을 출력하지 않는다.
- markdown 코드블록을 출력하지 않는다.
- assistant, user 같은 역할 이름을 출력하지 않는다.
- 설명을 붙이지 않는다.
- 병원 접수 직원의 응답 문장만 출력한다.
- 반드시 한 문장만 출력한다.
"""


def build_prompt(tokenizer):
    messages = [
        {"role": "user", "content": BENCHMARK_PROMPT.strip()},
    ]

    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    return BENCHMARK_PROMPT.strip() + "\n\n답변:"


def main():
    print(f"Loading model: {MODEL_NAME}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    prompt = build_prompt(tokenizer)

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
    ).to(model.device)

    start = time.perf_counter()

    # 4차 ai_message 전용 테스트 조건
    # max_new_tokens=60: 한 문장 응답만 생성하도록 제한한다.
    # do_sample=False: 모델별 비교 조건을 고정한다.
    # repetition_penalty=1.1: 반복 출력을 줄인다.
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=60,
            do_sample=False,
            repetition_penalty=1.1,
        )

    end = time.perf_counter()

    input_length = inputs["input_ids"].shape[-1]
    generated_tokens = outputs[0][input_length:]
    decoded = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    print("\n===== AI MESSAGE ONLY =====")
    print(decoded)

    print("\n===== LATENCY =====")
    print(f"{end - start:.2f}s")


if __name__ == "__main__":
    main()