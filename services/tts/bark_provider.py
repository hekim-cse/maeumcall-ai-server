from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Any

from services.tts.errors import TTSServiceError
from services.tts.provider import SynthesizedSpeech


class BarkTTSProvider:
    provider_name = "bark-small"
    supported_voice = "ko_speaker_5"
    generation_seed = 47

    def __init__(
        self,
        *,
        model_name: str,
        model_revision: str,
        local_files_only: bool,
        device: str,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.local_files_only = local_files_only
        self.device = device
        self._model: Any | None = None
        self._processor: Any | None = None
        self._history_prompt: dict[str, Any] | None = None
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
                "고정된 Bark 음성 합성 모델을 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._model_path = Path(resolved)
        return self._model_path

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

    def probe(self) -> None:
        try:
            import torch
            from transformers import AutoProcessor, BarkModel  # noqa: F401
        except Exception as exc:
            raise TTSServiceError(
                "TTS_RUNTIME_UNAVAILABLE",
                "Bark 음성 합성 실행 패키지를 불러오지 못했습니다.",
                status_code=503,
            ) from exc
        self._validate_device(torch)
        model_path = self._resolve_model_path()
        preset_prefix = f"speaker_embeddings/v2/{self.supported_voice}"
        required = tuple(
            model_path / f"{preset_prefix}_{component}_prompt.npy"
            for component in ("semantic", "coarse", "fine")
        )
        if not all(path.is_file() for path in required):
            raise TTSServiceError(
                "TTS_VOICE_ASSET_UNAVAILABLE",
                "승인된 Bark 한국어 음색 파일을 찾지 못했습니다.",
                status_code=503,
            )

    def _load_runtime(self) -> tuple[Any, Any, dict[str, Any]]:
        if self._model is not None and self._processor is not None and self._history_prompt:
            return self._processor, self._model, self._history_prompt
        try:
            import numpy as np
            import torch
            from transformers import AutoProcessor, BarkModel

            self._validate_device(torch)
            model_path = self._resolve_model_path()
            processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True)
            model = BarkModel.from_pretrained(
                str(model_path),
                local_files_only=True,
                dtype=torch.float32,
            ).to(self.device)
            model.eval()
            preset_prefix = f"speaker_embeddings/v2/{self.supported_voice}"
            history_prompt = {
                key: np.load(model_path / f"{preset_prefix}_{key}.npy")
                for key in ("semantic_prompt", "coarse_prompt", "fine_prompt")
            }
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_MODEL_LOAD_FAILED",
                "Bark 음성 합성 모델을 메모리에 올리지 못했습니다.",
                status_code=503,
            ) from exc
        self._processor = processor
        self._model = model
        self._history_prompt = history_prompt
        return processor, model, history_prompt

    def synthesize(self, *, text: str, voice: str) -> SynthesizedSpeech:
        if voice != self.supported_voice:
            raise TTSServiceError(
                "TTS_VOICE_UNSUPPORTED",
                "승인되지 않은 Bark 음색입니다.",
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

            processor, model, history_prompt = self._load_runtime()
            torch.manual_seed(self.generation_seed)
            inputs = processor(
                text,
                voice_preset=history_prompt,
                return_tensors="pt",
            ).to(self.device)
            if "attention_mask" not in inputs:
                inputs["attention_mask"] = torch.ones_like(inputs["input_ids"])
            with torch.inference_mode():
                audio = model.generate(**inputs)
            samples = audio.detach().cpu().float().numpy().squeeze()
            sample_rate = int(model.generation_config.sample_rate)
            output = io.BytesIO()
            sf.write(output, samples, sample_rate, format="WAV", subtype="PCM_16")
        except TTSServiceError:
            raise
        except Exception as exc:
            raise TTSServiceError(
                "TTS_SYNTHESIS_FAILED",
                "Bark 음성 합성을 완료하지 못했습니다.",
                status_code=502,
            ) from exc
        finally:
            self._lock.release()
        return SynthesizedSpeech(
            audio=output.getvalue(),
            media_type="audio/wav",
            sample_rate=sample_rate,
            voice=voice,
            provider=self.provider_name,
            model=self.model_name,
            model_revision=self.model_revision,
        )

    def unload(self) -> None:
        had_model = self._model is not None
        self._model = None
        self._processor = None
        self._history_prompt = None
        if not had_model:
            return
        import torch

        if self.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        if self.device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()
