from __future__ import annotations

import hashlib
import io
import json
import threading
from pathlib import Path
from typing import Any

from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech


class QwenVoiceCloneTTSProvider:
    provider_name = "qwen3-tts-voice-clone"
    role_id = "family_mother"
    voice_id = "reference_warm_everyday_mature_age_restrained_prosody"

    def __init__(
        self,
        *,
        manifest_path: Path | None,
        local_files_only: bool,
        device: str,
        dtype: str,
    ) -> None:
        self.manifest_path = manifest_path
        self.local_files_only = local_files_only
        self.device = device
        self.dtype = dtype
        self._model: Any | None = None
        self._prompt_items: list[Any] | None = None
        self._manifest: dict[str, Any] | None = None
        self._model_path: Path | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest is not None:
            return self._manifest
        path = self.manifest_path
        if path is None:
            raise TTSServiceError(
                "TTS_VOICE_CLONE_NOT_CONFIGURED",
                "승인된 엄마 음성 자산 경로가 설정되지 않았습니다.",
                status_code=503,
            )
        if not path.is_absolute():
            raise TTSServiceError(
                "TTS_VOICE_CLONE_PATH_INVALID",
                "엄마 음성 자산 경로는 절대 경로여야 합니다.",
                status_code=503,
            )
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TTSServiceError(
                "TTS_VOICE_CLONE_MANIFEST_INVALID",
                "엄마 음성 자산 명세를 읽지 못했습니다.",
                status_code=503,
            ) from exc
        expected = {
            "schemaVersion": 1,
            "castVersion": 2,
            "roleId": self.role_id,
            "voiceId": self.voice_id,
            "validationStatus": "approved-by-user",
            "provider": self.provider_name,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise TTSServiceError(
                "TTS_VOICE_CLONE_MANIFEST_INVALID",
                "엄마 음성 자산이 승인된 배역 계약과 일치하지 않습니다.",
                status_code=503,
            )
        prompt = manifest.get("prompt")
        if not isinstance(prompt, dict) or prompt.get("format") != "safetensors":
            raise TTSServiceError(
                "TTS_VOICE_CLONE_MANIFEST_INVALID",
                "엄마 음성 프롬프트 명세가 올바르지 않습니다.",
                status_code=503,
            )
        prompt_path = path.parent / str(prompt.get("filename", ""))
        if not prompt_path.is_file() or self._sha256(prompt_path) != prompt.get("sha256"):
            raise TTSServiceError(
                "TTS_VOICE_ASSET_UNAVAILABLE",
                "승인된 엄마 음성 프롬프트 파일을 검증하지 못했습니다.",
                status_code=503,
            )
        self._manifest = manifest
        return manifest

    def _validate_device(self, torch: Any) -> None:
        if self.device == "mps" and not torch.backends.mps.is_available():
            raise TTSServiceError(
                "TTS_DEVICE_UNAVAILABLE",
                "설정한 Apple MPS 음성 합성 장치를 사용할 수 없습니다.",
                status_code=503,
            )
        if self.device == "cuda" and not torch.cuda.is_available():
            raise TTSServiceError(
                "TTS_DEVICE_UNAVAILABLE",
                "설정한 CUDA 음성 합성 장치를 사용할 수 없습니다.",
                status_code=503,
            )
        if self.device == "cpu" and self.dtype != "float32":
            raise TTSServiceError(
                "TTS_DTYPE_INVALID",
                "CPU 음성 합성은 float32 정밀도로 설정해야 합니다.",
                status_code=503,
            )

    def _resolve_model_path(self, manifest: dict[str, Any]) -> Path:
        if self._model_path is not None:
            return self._model_path
        try:
            from huggingface_hub import snapshot_download

            resolved = snapshot_download(
                repo_id=manifest["model"],
                revision=manifest["modelRevision"],
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            raise TTSServiceError(
                "TTS_MODEL_UNAVAILABLE",
                "고정된 엄마 음성 합성 모델을 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._model_path = Path(resolved)
        return self._model_path

    def probe(self) -> None:
        try:
            import torch
            from qwen_tts import Qwen3TTSModel  # noqa: F401
            from safetensors import safe_open  # noqa: F401
        except Exception as exc:
            raise TTSServiceError(
                "TTS_RUNTIME_UNAVAILABLE",
                "엄마 음성 합성 실행 패키지를 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._validate_device(torch)
        manifest = self._load_manifest()
        self._resolve_model_path(manifest)

    def _load_runtime(self) -> tuple[Any, list[Any], dict[str, Any]]:
        manifest = self._load_manifest()
        if self._model is not None and self._prompt_items is not None:
            return self._model, self._prompt_items, manifest
        try:
            import torch
            from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem
            from safetensors import safe_open

            self._validate_device(torch)
            prompt = manifest["prompt"]
            prompt_path = self.manifest_path.parent / prompt["filename"]  # type: ignore[union-attr]
            with safe_open(str(prompt_path), framework="pt", device="cpu") as prompt_file:
                metadata = prompt_file.metadata()
                ref_code = prompt_file.get_tensor("ref_code")
                ref_spk_embedding = prompt_file.get_tensor("ref_spk_embedding")
            expected_metadata = {
                "schemaVersion": "1",
                "castVersion": "2",
                "roleId": self.role_id,
                "voiceId": self.voice_id,
                "model": manifest["model"],
                "modelRevision": manifest["modelRevision"],
                "referenceSha256": manifest["reference"]["sha256"],
                "referenceText": manifest["reference"]["text"],
                "xVectorOnlyMode": "false",
                "iclMode": "true",
            }
            if metadata != expected_metadata:
                raise TTSServiceError(
                    "TTS_VOICE_CLONE_MANIFEST_INVALID",
                    "엄마 음성 프롬프트 내부 메타데이터가 명세와 일치하지 않습니다.",
                    status_code=503,
                )
            prompt_items = [
                VoiceClonePromptItem(
                    ref_code=ref_code,
                    ref_spk_embedding=ref_spk_embedding,
                    x_vector_only_mode=False,
                    icl_mode=True,
                    ref_text=metadata["referenceText"],
                )
            ]
            torch_dtype = {
                "float32": torch.float32,
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
            }[self.dtype]
            model = Qwen3TTSModel.from_pretrained(
                str(self._resolve_model_path(manifest)),
                device_map=self.device,
                dtype=torch_dtype,
                attn_implementation="eager",
            )
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_MODEL_LOAD_FAILED",
                "엄마 음성 합성 모델과 프롬프트를 메모리에 올리지 못했습니다.",
                status_code=503,
            ) from exc
        self._model = model
        self._prompt_items = prompt_items
        return model, prompt_items, manifest

    def synthesize(self, *, text: str, voice: str) -> SynthesizedSpeech:
        if voice != self.voice_id:
            raise TTSServiceError(
                "TTS_VOICE_UNSUPPORTED",
                "승인되지 않은 엄마 음성입니다.",
                status_code=422,
            )
        if not self._lock.acquire(blocking=False):
            raise TTSServiceError(
                "TTS_BUSY",
                "다른 음성 합성 요청을 처리하고 있습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
            )
        try:
            import soundfile as sf
            import torch

            model, prompt_items, manifest = self._load_runtime()
            generation = manifest["generation"]
            torch.manual_seed(generation["seed"])
            wavs, sample_rate = model.generate_voice_clone(
                text=text,
                language=generation["language"],
                voice_clone_prompt=prompt_items,
                non_streaming_mode=generation["nonStreamingMode"],
                max_new_tokens=generation["maxNewTokens"],
                temperature=generation["temperature"],
                subtalker_temperature=generation["subtalkerTemperature"],
            )
            output = io.BytesIO()
            sf.write(output, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_SYNTHESIS_FAILED",
                "엄마 음성 합성을 완료하지 못했습니다.",
                status_code=502,
            ) from exc
        finally:
            self._lock.release()
        return SynthesizedSpeech(
            audio=output.getvalue(),
            media_type="audio/wav",
            sample_rate=int(sample_rate),
            voice=voice,
            provider=self.provider_name,
            model=manifest["model"],
            model_revision=manifest["modelRevision"],
        )

    def unload(self) -> None:
        had_model = self._model is not None
        self._model = None
        self._prompt_items = None
        if not had_model:
            return
        import torch

        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        if self.device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()
