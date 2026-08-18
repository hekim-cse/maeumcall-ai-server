from __future__ import annotations

import argparse
import shutil
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.generate_magpie_tts_auditions import (
    MODEL_ID as MAGPIE_MODEL_ID,
)
from scripts.generate_magpie_tts_auditions import (
    MODEL_REVISION as MAGPIE_MODEL_REVISION,
)
from scripts.generate_magpie_tts_auditions import (
    MODEL_VERSION as MAGPIE_MODEL_VERSION,
)
from scripts.generate_magpie_tts_auditions import (
    SPACE_ID as MAGPIE_SPACE_ID,
)
from scripts.generate_magpie_tts_auditions import (
    SPACE_REVISION as MAGPIE_SPACE_REVISION,
)
from scripts.generate_magpie_tts_auditions import (
    assert_remote_revisions,
)
from scripts.generate_tts_auditions import (
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_SEED,
)
from scripts.generate_tts_auditions import (
    DEFAULT_MODEL as QWEN_MODEL_ID,
)
from scripts.generate_tts_auditions import (
    DEFAULT_REVISION as QWEN_MODEL_REVISION,
)
from scripts.tts_audition_common import (
    describe_wav,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)
from services.flow.registry import FLOW_REGISTRY
from services.tts.casting import (
    SCENARIO_VOICE_CAST,
    TTSProviderId,
)
from services.tts.catalog import TTSVoiceId
from services.tts.qwen_provider import QwenTTSProvider


@dataclass(frozen=True)
class AuditionLine:
    text: str
    rationale: str


SCENARIO_AUDITION_LINES = {
    "예약:병원 예약": AuditionLine(
        "네, 예약을 도와드리겠습니다. 진료과와 방문하실 날짜를 말씀해 주세요.",
        "진료과와 날짜 수집",
    ),
    "예약:식당 예약": AuditionLine(
        "예약을 도와드리겠습니다. 방문 날짜와 시간, 인원을 말씀해 주세요.",
        "날짜·시간·인원 수집",
    ),
    "예약:미용실 예약": AuditionLine(
        "원하시는 시술과 방문 날짜, 시간을 말씀해 주세요.",
        "시술·날짜·시간 수집",
    ),
    "예약:스터디룸 예약": AuditionLine(
        "이용하실 날짜와 시간, 사용 인원을 말씀해 주세요.",
        "날짜·시간·인원 수집",
    ),
    "교수님:면담 예약": AuditionLine(
        "면담 목적과 가능한 날짜, 시간을 구체적으로 이야기해 보세요.",
        "면담 목적과 일정 확인",
    ),
    "교수님:과제 문의": AuditionLine(
        "과제에서 어떤 부분이 궁금한지 먼저 구체적으로 이야기해 보세요.",
        "과제 문의 주제 확인",
    ),
    "교수님:결석 사유 전달": AuditionLine(
        "결석한 수업 날짜와 사유를 차례대로 말씀해 보세요.",
        "결석 일자와 사유 확인",
    ),
    "배달:주문 변경": AuditionLine(
        "주문 변경을 도와드리겠습니다. 주문번호와 변경할 내용을 말씀해 주세요.",
        "주문 식별과 변경 내용 수집",
    ),
    "배달:배달 지연 문의": AuditionLine(
        "배달 상황을 확인해 보겠습니다. 주문번호와 현재 지연 상황을 말씀해 주세요.",
        "주문 식별과 지연 상황 수집",
    ),
    "배달:환불/재배달 문의": AuditionLine(
        "불편을 드려 죄송합니다. 주문번호와 발생한 문제를 말씀해 주세요.",
        "주문 식별과 문제 유형 수집",
    ),
    "시청:여권 발급 문의": AuditionLine(
        "최초 발급, 재발급, 긴급여권 중 어떤 신청을 문의하시나요?",
        "여권 신청 유형 분기",
    ),
    "시청:주민등록 등본 문의": AuditionLine(
        "주민등록표 등본과 초본 중 어떤 서류가 필요하신가요?",
        "민원 서류 유형 분기",
    ),
    "시청:대형폐기물 배출": AuditionLine(
        "대형폐기물을 배출할 지역과 품목을 말씀해 주세요.",
        "배출 지역과 품목 수집",
    ),
    "고객센터:인터넷/통화 문제 문의": AuditionLine(
        "문제가 발생한 서비스와 현재 증상을 구체적으로 말씀해 주세요.",
        "서비스 유형과 장애 증상 수집",
    ),
    "고객센터:요금/약정 상담": AuditionLine(
        "청구 내역, 요금제 변경, 약정 만료 중 어떤 상담을 원하시나요?",
        "상담 목적 분기",
    ),
    "고객센터:a/s 접수": AuditionLine(
        "A/S 접수를 도와드리겠습니다. 제품 종류와 고장 증상을 말씀해 주세요.",
        "제품과 고장 증상 수집",
    ),
    "가족:안부인사": AuditionLine(
        "응, 전화 잘 받았어. 오늘은 어떻게 지냈니?",
        "따뜻한 안부 대화",
    ),
    "가족:일정 조율": AuditionLine(
        "그래, 같이 일정 맞춰보자. 어느 날이 편하니?",
        "가족 일정 조율",
    ),
    "가족:도움 부탁": AuditionLine(
        "그래, 어떤 도움이 필요한지 천천히 말해 봐.",
        "도움 요청 경청",
    ),
    "친구:생일 축하 전화": AuditionLine(
        "고마워! 덕분에 기분 좋다. 우리 조만간 같이 보자.",
        "밝은 축하 반응",
    ),
    "친구:심심해서 거는 전화": AuditionLine(
        "나도 마침 심심했어. 오늘 있었던 일부터 편하게 얘기하자.",
        "가벼운 일상 대화",
    ),
    "친구:약속 잡는 전화": AuditionLine(
        "좋아! 언제 어디서 만날지 같이 정해 보자.",
        "발랄한 약속 조율",
    ),
    "친구:약속 변경/취소": AuditionLine(
        "알겠어. 괜찮으니까 우리 둘 다 가능한 다른 날짜를 찾아보자.",
        "변경 수용과 대안 제시",
    ),
    "친구:스터디 제안": AuditionLine(
        "좋지! 어떤 과목을 언제 같이 공부할까?",
        "경쾌한 스터디 제안",
    ),
    "연인:안부인사": AuditionLine(
        "응, 목소리 들으니까 좋다. 오늘 하루는 어땠어?",
        "다정한 안부 대화",
    ),
    "연인:데이트 약속 잡기": AuditionLine(
        "좋아, 우리 둘 다 편한 시간과 장소를 천천히 정해 보자.",
        "데이트 일정 조율",
    ),
    "연인:서운함 표현": AuditionLine(
        "그렇게 느꼈구나. 어떤 점이 서운했는지 차분히 듣고 싶어.",
        "감정 확인과 경청",
    ),
    "연인:사과하기": AuditionLine(
        "알겠어. 왜 그랬는지 솔직하게 말해 줬으면 좋겠어.",
        "사과 상황의 감정 대화",
    ),
    "회사:보고서 제출": AuditionLine(
        "보고서가 아직 확인되지 않았습니다. 현재 진행률과 제출 시간을 말씀해 주세요.",
        "긴장감 있는 제출 확인",
    ),
    "회사:진행상황 보고": AuditionLine(
        "현재 진행률과 남아 있는 문제를 빠짐없이 보고해 주세요.",
        "단호한 진행상황 확인",
    ),
    "회사:회의 일정 조율": AuditionLine(
        "가능한 회의 시간과 주요 안건을 정리해서 말씀해 주세요.",
        "업무 중심 일정 조율",
    ),
    "회사:연차/반차 신청": AuditionLine(
        "희망 일정과 업무 인수인계 계획을 구체적으로 말씀해 주세요.",
        "단호한 휴가 신청 확인",
    ),
}


def validate_audition_contract() -> None:
    registered_keys = set(FLOW_REGISTRY)
    cast_keys = set(SCENARIO_VOICE_CAST)
    line_keys = set(SCENARIO_AUDITION_LINES)
    if cast_keys != registered_keys:
        raise RuntimeError(
            f"TTS cast does not match flow registry: missing={sorted(registered_keys - cast_keys)}, "
            f"unknown={sorted(cast_keys - registered_keys)}"
        )
    if line_keys != registered_keys:
        raise RuntimeError(
            f"TTS audition lines do not match flow registry: "
            f"missing={sorted(registered_keys - line_keys)}, "
            f"unknown={sorted(line_keys - registered_keys)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one cast audition line for every registered scenario."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"))
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--provider",
        choices=tuple(provider.value for provider in TTSProviderId),
        required=True,
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Acknowledge that the public audition lines will be sent to NVIDIA's official Space.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_provider = TTSProviderId(args.provider)
    if selected_provider is TTSProviderId.NVIDIA_MAGPIE and not args.allow_network:
        raise RuntimeError("Magpie scenario auditions require explicit --allow-network.")
    if selected_provider is TTSProviderId.QWEN3_TTS and (
        args.device is None or args.dtype is None
    ):
        raise RuntimeError("Qwen scenario auditions require --device and --dtype.")
    validate_audition_contract()
    output_dir = prepare_output_directory(args.output_dir)

    qwen_provider: QwenTTSProvider | None = None
    if selected_provider is TTSProviderId.QWEN3_TTS:
        assert args.device is not None
        assert args.dtype is not None
        qwen_provider = QwenTTSProvider(
            model_name=QWEN_MODEL_ID,
            model_revision=QWEN_MODEL_REVISION,
            local_files_only=True,
            device=args.device,
            dtype=args.dtype,
            max_new_tokens=DEFAULT_MAX_NEW_TOKENS,
        )
        qwen_provider.probe()
        client_context = nullcontext(None)
    else:
        assert_remote_revisions()
        client_context = TemporaryDirectory(
            prefix="maeum-call-scenario-auditions-"
        )

    selected_scenarios = [
        (position, scenario_key, registration)
        for position, (scenario_key, registration) in enumerate(
            FLOW_REGISTRY.items(),
            start=1,
        )
        if SCENARIO_VOICE_CAST[scenario_key].provider is selected_provider
    ]

    artifacts: list[dict[str, str | int]] = []
    with client_context as download_dir:
        magpie_client = None
        if selected_provider is TTSProviderId.NVIDIA_MAGPIE:
            from gradio_client import Client
            from huggingface_hub import get_token

            magpie_client = Client(
                MAGPIE_SPACE_ID,
                token=get_token(),
                verbose=False,
                download_files=download_dir,
            )

        for generated_count, (
            position,
            scenario_key,
            registration,
        ) in enumerate(selected_scenarios, start=1):
            assignment = SCENARIO_VOICE_CAST[scenario_key]
            audition_line = SCENARIO_AUDITION_LINES[scenario_key]
            output_path = output_dir / f"{position:02d}_{assignment.voice}.wav"
            seed: int | None = None

            if assignment.provider is TTSProviderId.QWEN3_TTS:
                if qwen_provider is None:
                    raise RuntimeError("Qwen audition provider was not initialized.")
                seed = args.seed + position - 1
                seed_local_inference(seed)
                result = qwen_provider.synthesize(
                    text=audition_line.text,
                    voice=TTSVoiceId(assignment.voice),
                )
                output_path.write_bytes(result.audio)
            else:
                if magpie_client is None:
                    raise RuntimeError("Magpie audition client was not initialized.")
                downloaded_path = magpie_client.predict(
                    audition_line.text,
                    "Korean",
                    assignment.voice.title(),
                    "Apply TN",
                    api_name="/demo_tts",
                )
                shutil.copyfile(Path(downloaded_path), output_path)

            artifact = describe_wav(
                output_path,
                position=position,
                voice=assignment.voice,
                description=audition_line.rationale,
            )
            artifact.update(
                {
                    "scenarioKey": scenario_key,
                    "category": registration.category,
                    "title": registration.title,
                    "provider": assignment.provider.value,
                    "text": audition_line.text,
                }
            )
            if seed is not None:
                artifact["seed"] = seed
            artifacts.append(artifact)
            print(
                f"generated {generated_count:02d}/{len(selected_scenarios)} "
                f"[{position:02d}] {scenario_key} "
                f"({assignment.provider.value}:{assignment.voice})",
                flush=True,
            )

    manifest = {
        "castVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "language": "Korean",
        "provider": selected_provider.value,
        "executionMode": (
            "local-evaluation"
            if selected_provider is TTSProviderId.QWEN3_TTS
            else "hosted-evaluation-only"
        ),
        "runtime": (
            {
                "model": QWEN_MODEL_ID,
                "modelRevision": QWEN_MODEL_REVISION,
                "device": args.device,
                "dtype": args.dtype,
                "baseSeed": args.seed,
            }
            if selected_provider is TTSProviderId.QWEN3_TTS
            else {
                "model": MAGPIE_MODEL_ID,
                "modelVersion": MAGPIE_MODEL_VERSION,
                "modelRevision": MAGPIE_MODEL_REVISION,
                "space": MAGPIE_SPACE_ID,
                "spaceRevision": MAGPIE_SPACE_REVISION,
                "textNormalization": True,
                "seedControlAvailable": False,
            }
        ),
        "artifacts": artifacts,
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
