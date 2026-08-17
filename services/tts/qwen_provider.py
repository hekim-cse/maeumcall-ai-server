from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Any

from services.tts.catalog import TTSVoiceId
from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech


class QwenTTSProvider:
    provider_name = "qwen3-tts"

    def __init__(
        self,
        *,
        model_name: str,
        model_revision: str,
        local_files_only: bool,
        device: str,
        dtype: str,
        max_new_tokens: int,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.local_files_only = local_files_only
        self.device = device
        self.dtype = dtype
        self.max_new_tokens = max_new_tokens
        self._model: Any | None = None
        self._model_path: Path | None = None
        self._lock = threading.Lock()

    def _resolve_model_path(self) -> Path:
        if self._model_path is not None:
            return self._model_path
        try:
            from huggingface_hub import snapshot_download

            resolved = snapshot_download(
                repo_id=self.model_name,
                revision=self.model_revision,
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            raise TTSServiceError(
                "TTS_MODEL_UNAVAILABLE",
                "고정된 음성 합성 모델을 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._model_path = Path(resolved)
        return self._model_path

    def _torch_dtype(self, torch: Any) -> Any:
        return {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }[self.dtype]

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

    def probe(self) -> None:
        try:
            import torch
            from qwen_tts import Qwen3TTSModel  # noqa: F401
        except Exception as exc:
            raise TTSServiceError(
                "TTS_RUNTIME_UNAVAILABLE",
                "음성 합성 실행 패키지를 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._validate_device(torch)
        self._resolve_model_path()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import torch
            from qwen_tts import Qwen3TTSModel

            self._validate_device(torch)
            self._model = Qwen3TTSModel.from_pretrained(
                str(self._resolve_model_path()),
                device_map=self.device,
                dtype=self._torch_dtype(torch),
                attn_implementation="eager",
            )
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_MODEL_LOAD_FAILED",
                "음성 합성 모델을 메모리에 올리지 못했습니다.",
                status_code=503,
            ) from exc
        return self._model

    def synthesize(self, *, text: str, voice: TTSVoiceId) -> SynthesizedSpeech:
        if not self._lock.acquire(blocking=False):
            raise TTSServiceError(
                "TTS_BUSY",
                "다른 음성 합성 요청을 처리하고 있습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
            )
        try:
            import soundfile as sf

            model = self._load_model()
            wavs, sample_rate = model.generate_custom_voice(
                text=text,
                language="Korean",
                speaker=voice.value,
                max_new_tokens=self.max_new_tokens,
            )
            output = io.BytesIO()
            sf.write(output, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_SYNTHESIS_FAILED",
                "음성 합성을 완료하지 못했습니다.",
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
            model=self.model_name,
            model_revision=self.model_revision,
        )
