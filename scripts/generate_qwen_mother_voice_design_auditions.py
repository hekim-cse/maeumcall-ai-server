from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.generate_tts_auditions import DEFAULT_MAX_NEW_TOKENS, DEFAULT_SEED
from scripts.tts_audition_common import (
    describe_wav,
    describe_wav_pitch,
    prepare_output_directory,
    seed_local_inference,
    write_manifest,
)

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
MODEL_REVISION = "5ecdb67327fd37bb2e042aab12ff7391903235d3"
QWEN_TTS_VERSION = "0.1.1"
AUDITION_TEXT = "응, 전화 잘 받았어. 오늘은 어떻게 지냈는지 천천히 이야기해 봐."
USER_DIRECTED_PROSODY_TEXT = "어, 전화 잘 받았어. 오늘은 어떻게 지냈는지 천천히 이야기해 봐."
USER_DIRECTED_PROSODY_CONTOUR = (
    "어→, 전↓화↑ 잘→ 받↓았↑어→. 오늘은→ 어↓떻↑게→ 지↓냈↑는↓지→ 천↑천↑히↑ 이↓야↑기↑ 해봐→."
)
USER_DIRECTED_FLAT_TELEPHONE_CONTOUR = (
    "어→, 전→화→ 잘→ 받↓았↑어→. 오늘은→ 어↓떻↑게→ 지↓냈↑는↓지→ 천↑천↑히↑ 이↓야↑기↑ 해봐→."
)


@dataclass(frozen=True)
class MotherVoiceDesign:
    id: str
    direction: str
    seed_offset: int
    parent_id: str | None = None
    requires_acoustic_reference: bool = False
    controlled_axis: str | None = None
    audition_text: str = AUDITION_TEXT
    prosody_contour: str | None = None


MOTHER_VOICE_DESIGNS: tuple[MotherVoiceDesign, ...] = (
    MotherVoiceDesign(
        id="warm_calm_midlow",
        direction=(
            "40대 후반에서 50대 초반의 한국인 여성 목소리. 부드러운 중저음으로, "
            "엄마가 자녀의 하루를 따뜻하고 차분하게 물어보듯 자연스럽게 말한다. "
            "과장된 연기와 지나치게 젊은 느낌은 피한다."
        ),
        seed_offset=0,
    ),
    MotherVoiceDesign(
        id="natural_everyday",
        direction=(
            "40대에서 50대의 한국인 여성 목소리. 실제 가족 통화처럼 편안하고 생활감 있게, "
            "꾸미지 않은 발성과 안정된 속도로 다정하게 말한다."
        ),
        seed_offset=1,
    ),
    MotherVoiceDesign(
        id="mature_reassuring",
        direction=(
            "50대 한국인 여성의 성숙하고 안정적인 목소리. 낮고 포근한 음색으로, "
            "자녀가 안심할 수 있도록 여유 있고 믿음직스럽게 말한다."
        ),
        seed_offset=2,
    ),
    MotherVoiceDesign(
        id="bright_affectionate",
        direction=(
            "40대 후반 한국인 여성의 밝고 다정한 목소리. 반가움이 느껴지되 들뜨거나 "
            "어리게 들리지 않도록, 따뜻한 미소를 머금고 자연스럽게 말한다."
        ),
        seed_offset=3,
    ),
    MotherVoiceDesign(
        id="gentle_concerned",
        direction=(
            "50대 한국인 여성의 온화하고 세심한 목소리. 자녀의 상태를 걱정하면서도 "
            "부담을 주지 않도록 부드러운 중저음과 느긋한 호흡으로 말한다."
        ),
        seed_offset=4,
    ),
)

MOTHER_VOICE_REFINEMENTS: tuple[MotherVoiceDesign, ...] = (
    MotherVoiceDesign(
        id="natural_everyday_mature_low",
        direction=(
            "50대 한국인 여성 목소리. 실제 가족 통화처럼 꾸미지 않고 생활감 있게 말한다. "
            "기본 음높이를 낮게 유지하고 두터운 중저음 공명을 사용하며, 억양의 폭을 줄이고 "
            "조금 느긋한 속도로 다정하게 말한다. 인위적으로 눌러 말하거나 노인처럼 떨리는 "
            "목소리는 피한다."
        ),
        seed_offset=5,
        parent_id="natural_everyday",
    ),
    MotherVoiceDesign(
        id="natural_everyday_deep_alto",
        direction=(
            "A Korean woman in her late fifties with a distinctly low fundamental pitch, "
            "a deep and full-bodied alto timbre, and strong chest resonance. Keep the natural, "
            "unpolished feeling of an everyday family phone call. Speak at a relaxed pace with "
            "restrained intonation. Do not sound high-pitched, thin, bright, youthful, airy, "
            "breathy, nasal, or falsetto."
        ),
        seed_offset=6,
        parent_id="natural_everyday_mature_low",
    ),
    MotherVoiceDesign(
        id="natural_everyday_contralto",
        direction=(
            "A mature Korean mother around sixty with a low-register contralto voice, dense warm "
            "vocal body, and a low center of resonance in the chest. Use a calm, slightly slow, "
            "natural conversational delivery. Avoid head voice, narrow thin tone, high pitch, "
            "youthful brightness, excessive breathiness, and exaggerated elderly trembling."
        ),
        seed_offset=7,
        parent_id="natural_everyday_mature_low",
    ),
    MotherVoiceDesign(
        id="natural_everyday_warm_husky",
        direction=(
            "A Korean woman in her late fifties with a low, rich, gently husky voice and solid "
            "low-mid chest resonance. She sounds warm and familiar like a real mother speaking "
            "to her adult child on the phone, with measured pacing and small pitch movements. "
            "The voice must not be high, thin, girlish, airy, sharp, nasal, or artificially aged."
        ),
        seed_offset=8,
        parent_id="natural_everyday_mature_low",
    ),
)

REFERENCE_CALIBRATED_MOTHER_VOICE_DESIGNS: tuple[MotherVoiceDesign, ...] = (
    MotherVoiceDesign(
        id="reference_warm_everyday",
        direction=(
            "A Korean woman in her fifties speaking naturally to her adult child on the phone. "
            "Use an ordinary medium speaking pitch, a warm full vocal body, comfortable lower-mid "
            "resonance, and small but natural intonation movements. Sound familiar and unpolished, "
            "not like an announcer or actor. Do not force the pitch downward and do not sound "
            "girlish, elderly, breathy, hoarse, or theatrical."
        ),
        seed_offset=9,
        parent_id="natural_everyday",
        requires_acoustic_reference=True,
    ),
    MotherVoiceDesign(
        id="reference_calm_reassuring",
        direction=(
            "A calm Korean mother in her late fifties with a mature but ordinary conversational "
            "voice. Keep the speaking pitch in a comfortable medium range and create age through "
            "steady breath support, rounded resonance, measured pacing, and restrained intonation. "
            "She should sound reassuring and attentive, without an artificially low register, "
            "exaggerated age, excessive sweetness, or professional narration."
        ),
        seed_offset=10,
        parent_id="natural_everyday",
        requires_acoustic_reference=True,
    ),
    MotherVoiceDesign(
        id="reference_gentle_lived_in",
        direction=(
            "A Korean woman in her fifties with a gentle, lived-in everyday voice and a warm dense "
            "timbre. Use a natural medium pitch, relaxed timing, clear consonants, and subtle "
            "affection as if checking on her grown child. Keep the delivery intimate and realistic. "
            "Avoid forced bass, thin brightness, youthful excitement, breathy whispering, strong "
            "husky rasp, and exaggerated emotional acting."
        ),
        seed_offset=11,
        parent_id="natural_everyday",
        requires_acoustic_reference=True,
    ),
)

CONTROLLED_MOTHER_VOICE_REFINEMENTS: tuple[MotherVoiceDesign, ...] = (
    MotherVoiceDesign(
        id="reference_warm_everyday_natural_prosody",
        direction=(
            "A Korean woman in her fifties speaking naturally to her adult child on the phone. "
            "Keep the same warm, full, lower-mid vocal body and ordinary medium speaking pitch. "
            "Use plain everyday Korean conversational prosody: connect phrases smoothly, place "
            "only small emphasis on meaning-bearing words, and let sentence endings settle "
            "gently without a repeated melodic pattern. The timing should feel spontaneous, "
            "not read aloud. Do not sound like an announcer, actor, audiobook narrator, or "
            "customer-service agent. Avoid sing-song intonation and exaggerated concern."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday",
        requires_acoustic_reference=True,
        controlled_axis="prosody-naturalness",
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age",
        direction=(
            "A Korean mother in her late fifties to early sixties speaking to her adult child on "
            "the phone. Keep an ordinary conversational delivery and medium-low speaking pitch, "
            "but give the voice a more mature physical presence through a settled full vocal body, "
            "rounded lower-mid resonance, steady breath support, and an unhurried cadence. She "
            "should sound experienced and familiar rather than youthful. Do not imitate frailty, "
            "trembling, rasp, breathiness, an elderly stereotype, or an artificially forced bass."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday",
        requires_acoustic_reference=True,
        controlled_axis="perceived-age",
    ),
)

MATURE_AGE_PROSODY_REFINEMENTS: tuple[MotherVoiceDesign, ...] = (
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_natural_prosody",
        direction=(
            "A Korean mother in her late fifties to early sixties speaking to her adult child on "
            "the phone. Preserve the settled full vocal body, rounded lower-mid resonance, steady "
            "breath support, medium-low speaking pitch, and mature physical presence of the source "
            "candidate. Keep the unhurried cadence, but make the Korean intonation slightly more "
            "natural and conversational: join each phrase smoothly, use only subtle emphasis on "
            "meaning-bearing words, and finish each sentence softly without a repeated melodic "
            "pattern. Do not change the perceived age or make the delivery noticeably brighter, "
            "faster, more animated, theatrical, sing-song, or announcer-like. Do not imitate "
            "frailty, trembling, rasp, breathiness, or an artificially forced bass."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age",
        requires_acoustic_reference=True,
        controlled_axis="prosody-naturalness",
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_restrained_prosody",
        direction=(
            "A Korean mother in her late fifties to early sixties speaking quietly to her adult "
            "child on the phone. Preserve the settled full vocal body, rounded lower-mid "
            "resonance, steady breath support, medium-low speaking pitch, and mature physical "
            "presence of the source candidate. Use restrained everyday Korean intonation with "
            "a narrow pitch range and a stable baseline. Avoid sharp rises, deep falls, dramatic "
            "stress, and repeated melodic contours. Keep word emphasis light and let sentence "
            "endings settle only a little. Maintain enough small variation to sound human and "
            "warm, never flat, robotic, theatrical, sing-song, or announcer-like. Do not change "
            "the perceived age or imitate frailty, trembling, rasp, breathiness, or forced bass."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age",
        requires_acoustic_reference=True,
        controlled_axis="prosody-range",
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_soft_warm_prosody",
        direction=(
            "A Korean mother in her late fifties to early sixties speaking gently to her adult "
            "child on the phone. Preserve the mature medium-low pitch, settled full vocal body, "
            "rounded lower-mid resonance, and steady breath support of the source candidate. "
            "Let quiet affection and reassuring warmth sit naturally in the voice, as if she is "
            "glad to hear her child and wants them to feel at ease. Connect phrases very smoothly "
            "with soft edges, light consonant attacks, and an unhurried conversational flow. Keep "
            "the pitch range compact, avoid strong word stress, and let sentence endings rest "
            "gently instead of rising or dropping sharply. Sound intimate and motherly without "
            "becoming bright, youthful, overly sweet, sleepy, whispery, theatrical, sing-song, "
            "customer-service-like, or artificially aged."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age_restrained_prosody",
        requires_acoustic_reference=True,
        controlled_axis="delivery-warmth",
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_understated_warmth",
        direction=(
            "A Korean mother in her late fifties to early sixties having a quiet, familiar phone "
            "conversation with her adult child. Preserve the mature medium-low pitch, settled "
            "full vocal body, rounded lower-mid resonance, compact pitch range, and restrained "
            "everyday intonation of the source candidate. Express warmth only through a soft "
            "rounded vocal color, steady relaxed breath, gentle consonant onsets, close intimate "
            "presence, and unhurried pacing—not through a brighter pitch or larger melodic "
            "movement. Keep emphasis small, connect phrases smoothly, and let sentence endings "
            "land softly with minimal rise or fall. She should sound quietly caring and familiar, "
            "never cold, flat, robotic, youthful, overly sweet, excited, sleepy, whispery, "
            "theatrical, sing-song, customer-service-like, or artificially aged."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age_restrained_prosody",
        requires_acoustic_reference=True,
        controlled_axis="vocal-warmth",
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_user_directed_contour",
        direction=(
            "A warm Korean mother in her late fifties to early sixties speaking gently to her "
            "adult child. Preserve the mature medium-low pitch, settled full vocal body, rounded "
            "lower-mid resonance, soft vocal edges, and quietly affectionate presence of the "
            "source candidate. Follow this syllable-level Korean pitch contour exactly: "
            f"'{USER_DIRECTED_PROSODY_CONTOUR}' The arrows describe pitch direction only and "
            "must never be pronounced. A right arrow means level pitch, a down arrow means a "
            "small smooth fall, and an up arrow means a small smooth rise. Connect all marked "
            "syllables naturally without choppy breaks. Keep every rise and fall rounded and "
            "moderate, including the consecutive rises in '천천히' and '이야기'. Retain warmth "
            "through vocal color and relaxed breath rather than exaggerated melody. Never sound "
            "youthful, overly sweet, theatrical, sing-song, robotic, or customer-service-like."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age_understated_warmth",
        requires_acoustic_reference=True,
        controlled_axis="user-directed-prosody",
        audition_text=USER_DIRECTED_PROSODY_TEXT,
        prosody_contour=USER_DIRECTED_PROSODY_CONTOUR,
    ),
    MotherVoiceDesign(
        id="reference_warm_everyday_mature_age_user_directed_flat_telephone",
        direction=(
            "A warm Korean mother in her late fifties to early sixties speaking gently to her "
            "adult child. Keep the entire voice in the same mature medium-low register with a "
            "settled full vocal body and rounded lower-mid resonance. Do not raise or lower the "
            "overall speaking pitch. Follow this syllable-level Korean contour exactly: "
            f"'{USER_DIRECTED_FLAT_TELEPHONE_CONTOUR}' The arrows are relative local intonation "
            "directions around the unchanged medium-low baseline and must never be pronounced. "
            "A right arrow means level pitch, a down arrow means a small smooth fall, and an up "
            "arrow means a small smooth rise. Pronounce both syllables of '전화' on the same "
            "level pitch. Connect all syllables naturally without choppy breaks. Keep every local "
            "movement small and rounded, including the consecutive rises in '천천히' and "
            "'이야기'. Preserve quiet maternal warmth through vocal color and relaxed breath, "
            "not through a higher register or exaggerated melody. Never sound youthful, overly "
            "sweet, theatrical, sing-song, robotic, or customer-service-like."
        ),
        seed_offset=9,
        parent_id="reference_warm_everyday_mature_age_user_directed_contour",
        requires_acoustic_reference=True,
        controlled_axis="user-directed-prosody",
        audition_text=USER_DIRECTED_PROSODY_TEXT,
        prosody_contour=USER_DIRECTED_FLAT_TELEPHONE_CONTOUR,
    ),
)

ALL_MOTHER_VOICE_DESIGNS = (
    MOTHER_VOICE_DESIGNS
    + MOTHER_VOICE_REFINEMENTS
    + REFERENCE_CALIBRATED_MOTHER_VOICE_DESIGNS
    + CONTROLLED_MOTHER_VOICE_REFINEMENTS
    + MATURE_AGE_PROSODY_REFINEMENTS
)


def load_acoustic_reference(path: Path) -> dict[str, float | str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        dataset = payload["dataset"]
        coverage = payload["coverage"]
        privacy = payload["privacy"]
        pitch_range = payload["acousticReference"]["speakerMedianF0Hz"]
        p25 = float(pitch_range["p25"])
        median = float(pitch_range["median"])
        p75 = float(pitch_range["p75"])
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise RuntimeError(f"Invalid acoustic reference manifest: {path}") from error
    if payload.get("referenceContractVersion") != 1:
        raise RuntimeError("Acoustic reference contract version must be 1.")
    if payload.get("purpose") != "family-mother-candidate-acoustic-calibration":
        raise RuntimeError(
            "Acoustic reference purpose does not allow mother-candidate calibration."
        )
    if dataset.get("id") != 71558 or dataset.get("rawDataCommitted") is not False:
        raise RuntimeError(
            "Acoustic reference must use the approved aggregate dataset 71558 contract."
        )
    if coverage.get("selectedSpeakers", 0) < 20:
        raise RuntimeError("Acoustic reference requires at least 20 selected speakers.")
    required_privacy_contract = {
        "containsSpeakerIdentifiers": False,
        "containsSourceFileNames": False,
        "containsTranscripts": False,
        "containsAudio": False,
        "statisticsAreAggregateOnly": True,
    }
    if any(privacy.get(key) is not value for key, value in required_privacy_contract.items()):
        raise RuntimeError("Acoustic reference does not satisfy the aggregate privacy contract.")
    if not p25 < median < p75:
        raise RuntimeError("Acoustic reference pitch quartiles must be strictly increasing.")
    return {
        "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "p25F0Hz": p25,
        "medianF0Hz": median,
        "p75F0Hz": p75,
    }


def evaluate_pitch_against_reference(
    median_f0_hz: float, reference: dict[str, float | str]
) -> dict[str, float | str]:
    p25 = float(reference["p25F0Hz"])
    p75 = float(reference["p75F0Hz"])
    return {
        "referenceManifestSha256": str(reference["manifestSha256"]),
        "referenceP25F0Hz": p25,
        "referenceP75F0Hz": p75,
        "candidateMedianF0Hz": median_f0_hz,
        "result": (
            "within-reference-interquartile-range"
            if p25 <= median_f0_hz <= p75
            else "outside-reference-interquartile-range"
        ),
        "decisionBoundary": "acoustic-screening-only-requires-user-listening",
    }


def resolve_model_snapshot(*, allow_network: bool) -> str:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ModuleNotFoundError as error:
        if error.name != "huggingface_hub":
            raise
        raise RuntimeError(
            "Qwen VoiceDesign generation requires the optional TTS dependencies. "
            "Install them with 'pip install -r requirements-tts.txt'."
        ) from error

    if allow_network:
        model_info = HfApi().model_info(MODEL_ID)
        if model_info.sha != MODEL_REVISION:
            raise RuntimeError(
                f"Qwen VoiceDesign revision changed: expected {MODEL_REVISION}, "
                f"received {model_info.sha}"
            )
    return snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_files_only=not allow_network,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate controlled Korean mother-role candidates with Qwen VoiceDesign."
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
        "--design-id",
        action="append",
        choices=tuple(design.id for design in ALL_MOTHER_VOICE_DESIGNS),
        help=(
            "Generate only the selected design. Repeat the option for multiple designs. "
            "When omitted, the five base candidates are generated."
        ),
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow checking and downloading the exact pinned model revision.",
    )
    parser.add_argument(
        "--acoustic-reference",
        type=Path,
        help=(
            "Aggregate AI Hub reference manifest. Required for reference-calibrated designs; "
            "speaker-level data and source audio are not accepted."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = prepare_output_directory(args.output_dir)
    designs_by_id = {design.id: design for design in ALL_MOTHER_VOICE_DESIGNS}
    selected_designs = (
        tuple(designs_by_id[design_id] for design_id in dict.fromkeys(args.design_id))
        if args.design_id
        else MOTHER_VOICE_DESIGNS
    )
    selected_texts = {design.audition_text for design in selected_designs}
    if len(selected_texts) != 1:
        raise RuntimeError("One generation batch cannot mix different audition texts.")
    audition_text = next(iter(selected_texts))

    runtime_version = importlib.metadata.version("qwen-tts")
    if runtime_version != QWEN_TTS_VERSION:
        raise RuntimeError(
            f"qwen-tts version mismatch: expected {QWEN_TTS_VERSION}, received {runtime_version}"
        )

    model_path = resolve_model_snapshot(allow_network=args.allow_network)

    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("Qwen VoiceDesign requested MPS, but MPS is not available.")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Qwen VoiceDesign requested CUDA, but CUDA is not available.")
    if args.device == "cpu" and args.dtype != "float32":
        raise RuntimeError("Qwen VoiceDesign CPU execution requires float32.")
    torch_dtype = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[args.dtype]
    model = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=args.device,
        dtype=torch_dtype,
        attn_implementation="eager",
    )

    reference_required = any(design.requires_acoustic_reference for design in selected_designs)
    if reference_required and args.acoustic_reference is None:
        raise RuntimeError("Reference-calibrated designs require --acoustic-reference.")
    acoustic_reference = (
        load_acoustic_reference(args.acoustic_reference.resolve())
        if args.acoustic_reference is not None
        else None
    )

    artifacts: list[dict[str, str | int]] = []
    for position, design in enumerate(selected_designs, start=1):
        seed = args.seed + design.seed_offset
        seed_local_inference(seed)
        wavs, sample_rate = model.generate_voice_design(
            text=design.audition_text,
            language="Korean",
            instruct=design.direction,
            max_new_tokens=args.max_new_tokens,
        )
        output_path = output_dir / f"{position:02d}_{design.id}.wav"
        sf.write(output_path, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
        artifact = describe_wav(
            output_path,
            position=position,
            voice=design.id,
            description=design.direction,
        )
        artifact["seed"] = seed
        artifact["pitchAnalysis"] = describe_wav_pitch(output_path)
        if design.requires_acoustic_reference:
            if acoustic_reference is None:
                raise RuntimeError("Acoustic reference was not loaded.")
            artifact["acousticReferenceEvaluation"] = evaluate_pitch_against_reference(
                float(artifact["pitchAnalysis"]["medianF0Hz"]),
                acoustic_reference,
            )
        if design.parent_id is not None:
            artifact["parentCandidateId"] = design.parent_id
        if design.controlled_axis is not None:
            artifact["controlledAxis"] = design.controlled_axis
        if design.prosody_contour is not None:
            artifact["prosodyContour"] = design.prosody_contour
        artifacts.append(artifact)
        print(f"generated {position:02d}/{len(selected_designs)} {design.id}", flush=True)

    manifest = {
        "castVersion": 2,
        "roleId": "family_mother",
        "selectionStatus": "awaiting-user-selection",
        "generatedAt": datetime.now(UTC).isoformat(),
        "provider": "qwen3-tts-voice-design",
        "executionMode": "local-evaluation",
        "model": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "runtimeVersion": runtime_version,
        "language": "Korean",
        "device": args.device,
        "dtype": args.dtype,
        "text": audition_text,
        "maxNewTokens": args.max_new_tokens,
        "baseSeed": args.seed,
        "seedStrategy": "base-seed-plus-stable-design-offset",
        "designIds": [design.id for design in selected_designs],
        "artifacts": artifacts,
    }
    if acoustic_reference is not None:
        manifest["acousticReference"] = acoustic_reference
    manifest_path = write_manifest(output_dir, manifest)
    print(f"manifest {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
