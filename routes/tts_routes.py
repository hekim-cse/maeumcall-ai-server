from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from core.auth import AuthenticatedUser, require_authenticated_user
from schemas.tts_models import TTSRequest, TTSVoiceCatalogResponse
from services.tts.catalog import TTS_VOICE_CATALOG
from services.tts.provider import TTSProvider
from services.tts.service import get_tts_provider

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices", response_model=TTSVoiceCatalogResponse)
def list_tts_voices() -> TTSVoiceCatalogResponse:
    return TTSVoiceCatalogResponse(voices=list(TTS_VOICE_CATALOG))


@router.post("/synthesize")
async def synthesize_speech(
    request: TTSRequest,
    _: AuthenticatedUser = Depends(require_authenticated_user),
    provider: TTSProvider = Depends(get_tts_provider),
) -> Response:
    result = await asyncio.to_thread(
        provider.synthesize,
        text=request.text,
        voice=request.voice,
    )
    return Response(
        content=result.audio,
        media_type=result.media_type,
        headers={
            "X-TTS-Provider": result.provider,
            "X-TTS-Model": result.model,
            "X-TTS-Model-Revision": result.model_revision,
            "X-TTS-Voice": result.voice.value,
            "X-Audio-Sample-Rate": str(result.sample_rate),
            "Cache-Control": "private, no-store",
        },
    )
