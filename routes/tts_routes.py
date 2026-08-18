from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from core.auth import AuthenticatedUser, require_authenticated_user
from schemas.tts_models import TTSRequest, TTSScenarioRequest, TTSVoiceCatalogResponse
from services.tts.casting import (
    ScenarioVoiceAssignment,
    TTSProviderId,
    resolve_scenario_voice_assignment,
)
from services.tts.catalog import TTS_VOICE_CATALOG
from services.tts.provider import SynthesizedSpeech
from services.tts.service import TTSRuntime, TTSRuntimeResult, get_tts_runtime

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices", response_model=TTSVoiceCatalogResponse)
def list_tts_voices() -> TTSVoiceCatalogResponse:
    return TTSVoiceCatalogResponse(voices=list(TTS_VOICE_CATALOG))


@router.post("/synthesize")
async def synthesize_speech(
    request: TTSRequest,
    _: AuthenticatedUser = Depends(require_authenticated_user),
    runtime: TTSRuntime = Depends(get_tts_runtime),
) -> Response:
    result = await asyncio.to_thread(
        runtime.synthesize,
        text=request.text,
        assignment=ScenarioVoiceAssignment(
            provider=TTSProviderId.QWEN3_TTS,
            voice=request.voice.value,
            role_id="direct_preview",
        ),
    )
    return _audio_response(result)


@router.post("/scenario/synthesize")
async def synthesize_scenario_speech(
    request: TTSScenarioRequest,
    _: AuthenticatedUser = Depends(require_authenticated_user),
    runtime: TTSRuntime = Depends(get_tts_runtime),
) -> Response:
    assignment = resolve_scenario_voice_assignment(
        scenario_key=request.scenarioKey,
        cast_version=request.castVersion,
        persona_id=request.personaId,
    )
    result = await asyncio.to_thread(
        runtime.synthesize,
        text=request.text,
        assignment=assignment,
    )
    headers = {
        "X-TTS-Cast-Version": str(request.castVersion),
        "X-TTS-Scenario-Key": quote(request.scenarioKey, safe=":"),
        "X-TTS-Role": assignment.role_id,
    }
    if assignment.persona_id is not None:
        headers["X-TTS-Persona"] = assignment.persona_id.value
    return _audio_response(result, extra_headers=headers)


def _audio_response(
    result: TTSRuntimeResult,
    *,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    speech: SynthesizedSpeech = result.speech
    timing = result.timing
    headers = {
        "X-TTS-Provider": speech.provider,
        "X-TTS-Model": speech.model,
        "X-TTS-Model-Revision": speech.model_revision,
        "X-TTS-Voice": speech.voice,
        "X-TTS-Model-State": timing.model_state,
        "X-Audio-Sample-Rate": str(speech.sample_rate),
        "Server-Timing": (
            f"tts_transition;dur={timing.transition_seconds * 1000:.3f}, "
            f"tts_synthesis;dur={timing.synthesis_seconds * 1000:.3f}, "
            f"tts_total;dur={timing.total_seconds * 1000:.3f}"
        ),
        "Cache-Control": "private, no-store",
    }
    if extra_headers:
        headers.update(extra_headers)
    return Response(
        content=speech.audio,
        media_type=speech.media_type,
        headers=headers,
    )
