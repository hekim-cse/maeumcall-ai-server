import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# 2차 테스트 첫 번째 모델: EXAONE
# 다른 모델 테스트할 때는 이 MODEL_NAME만 바꾸면 된다.
MODEL_NAME = "beomi/gemma-ko-2b"

BENCHMARK_PROMPT = """
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
"""


def build_prompt(tokenizer):
    """
    모델 tokenizer에 chat_template이 있으면 chat 형식으로 프롬프트를 구성한다.
    chat_template이 없으면 일반 텍스트 프롬프트로 구성한다.
    """
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
    print(f"Loading model: {MODEL_NAME}")

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

    # 2차 Improved Prompt 테스트 생성 조건
    # max_new_tokens=120: 불필요하게 길게 생성되는 것을 줄인다.
    # do_sample=False: 매번 최대한 동일한 조건으로 비교한다.
    # repetition_penalty=1.1: assistant 반복, 프롬프트 반복 출력을 줄인다.
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=160,
            do_sample=False,
            repetition_penalty=1.1,
        )

    end = time.perf_counter()

    # 입력 프롬프트를 제외하고 모델이 새로 생성한 부분만 출력한다.
    input_length = inputs["input_ids"].shape[-1]
    generated_tokens = outputs[0][input_length:]
    decoded = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    print("\n===== GENERATED OUTPUT ONLY =====")
    print(decoded)

    print("\n===== LATENCY =====")
    print(f"{end - start:.2f}s")


if __name__ == "__main__":
    main()