from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.generate_tts_auditions import (
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_REVISION,
    DEFAULT_SEED,
)
from scripts.tts_audition_common import (
    describe_wav,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)
from services.tts.catalog import TTS_VOICE_CATALOG
from services.tts.qwen_provider import QwenTTSProvider


@dataclass(frozen=True)
class RoleAudition:
    id: str
    categories: tuple[str, ...]
    direction: str
    text: str


ROLE_AUDITIONS: tuple[RoleAudition, ...] = (
    RoleAudition(
        id="service_agent",
        categories=("예약", "시청", "고객센터"),
        direction="또렷하고 차분하게 정보를 안내하는 젊은 상담원",
        text="안녕하세요. 문의하신 내용을 확인해 드리겠습니다. 필요한 정보를 차례대로 말씀해 주세요.",
    ),
    RoleAudition(
        id="delivery_agent",
        categories=("배달",),
        direction="침착하게 문제를 확인하는 중년층 배달 상담원",
        text="배달 상황을 확인해 보겠습니다. 주문번호와 현재 발생한 문제를 말씀해 주세요.",
    ),
    RoleAudition(
        id="family_mother",
        categories=("가족",),
        direction="엄마처럼 따뜻하게 이야기를 들어 주는 중년 여성",
        text="응, 전화 잘 받았어. 오늘은 어떻게 지냈는지 천천히 이야기해 봐.",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Generate every verified Qwen3-TTS voice for each unresolved cast-v2 role.")
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), required=True)
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
        required=True,
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS)
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow downloading the exact pinned Qwen revision when it is not cached.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = prepare_output_directory(args.output_dir)
    provider = QwenTTSProvider(
        model_name=DEFAULT_MODEL,
        model_revision=DEFAULT_REVISION,
        local_files_only=not args.allow_network,
        device=args.device,
        dtype=args.dtype,
        max_new_tokens=args.max_new_tokens,
    )
    provider.probe()

    artifacts: list[dict[str, str | int | bool | list[str]]] = []
    generation_position = 0
    for role in ROLE_AUDITIONS:
        role_output_dir = output_dir / role.id
        role_output_dir.mkdir()
        for voice_position, profile in enumerate(TTS_VOICE_CATALOG, start=1):
            generation_position += 1
            seed = args.seed + generation_position - 1
            seed_local_inference(seed)
            result = provider.synthesize(text=role.text, voice=profile.id)
            filename = f"{voice_position:02d}_{profile.id.value}.wav"
            output_path = role_output_dir / filename
            output_path.write_bytes(result.audio)
            artifact = describe_wav(
                output_path,
                position=generation_position,
                voice=profile.id.value,
                description=profile.description,
            )
            artifact.update(
                {
                    "filename": f"{role.id}/{filename}",
                    "roleId": role.id,
                    "categories": list(role.categories),
                    "direction": role.direction,
                    "text": role.text,
                    "nativeLanguage": profile.nativeLanguage,
                    "nativeKorean": profile.nativeKorean,
                    "seed": seed,
                }
            )
            artifacts.append(artifact)
            print(
                f"generated {generation_position:02d}/{len(ROLE_AUDITIONS) * len(TTS_VOICE_CATALOG)} "
                f"{role.id}:{profile.id.value}",
                flush=True,
            )

    manifest = {
        "castVersion": 2,
        "selectionStatus": "awaiting-user-selection",
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": provider.provider_name,
        "executionMode": "local-evaluation",
        "model": DEFAULT_MODEL,
        "modelRevision": DEFAULT_REVISION,
        "language": "Korean",
        "device": args.device,
        "dtype": args.dtype,
        "maxNewTokens": args.max_new_tokens,
        "baseSeed": args.seed,
        "seedStrategy": "base-seed-plus-zero-based-generation-position",
        "roles": [
            {
                "id": role.id,
                "categories": list(role.categories),
                "direction": role.direction,
                "text": role.text,
            }
            for role in ROLE_AUDITIONS
        ],
        "artifacts": artifacts,
    }
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
