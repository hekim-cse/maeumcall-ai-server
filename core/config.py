# core/config.py
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=False, encoding="utf-8-sig")

def getenv(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) else default


def getenv_bool(name: str, default: bool = False) -> bool:
    raw = getenv(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def getenv_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value

OPENAI_API_KEY = getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = getenv_int("OPENAI_TIMEOUT", 8)
PROMPT_CACHE = getenv_bool("PROMPT_CACHE", True)
HF_LOCAL_MODEL_ENABLED = getenv_bool("HF_LOCAL_MODEL_ENABLED", False)
HF_LOCAL_FILES_ONLY = getenv_bool("HF_LOCAL_FILES_ONLY", True)
HF_MODEL_NAME = getenv(
    "HF_MODEL_NAME",
    "kakaocorp/kanana-1.5-2.1b-instruct-2505",
)
HF_MODEL_REVISION = getenv(
    "HF_MODEL_REVISION",
    "7df4bc35ccd610e451809d7106e1c3cf82bfd44c",
)

_cors_origins = getenv("CORS_ALLOW_ORIGINS", "*")
CORS_ALLOW_ORIGINS = [item.strip() for item in _cors_origins.split(",") if item.strip()]
AUDIO_UPLOAD_MAX_BYTES = getenv_int("AUDIO_UPLOAD_MAX_MB", 20) * 1024 * 1024
BASELINE_ID_HMAC_SECRET = getenv("BASELINE_ID_HMAC_SECRET", "")
DATABASE_URL = getenv("DATABASE_URL", "")
DATABASE_POOL_SIZE = getenv_int("DATABASE_POOL_SIZE", 5)
DATABASE_MAX_OVERFLOW = getenv_int("DATABASE_MAX_OVERFLOW", 10, minimum=0)
DATABASE_CONNECT_TIMEOUT = getenv_int("DATABASE_CONNECT_TIMEOUT", 3)
KAKAO_APP_ID = getenv("KAKAO_APP_ID", "")
FIREBASE_PROJECT_ID = getenv("FIREBASE_PROJECT_ID", "")
AUTH_SUBJECT_HMAC_SECRET = getenv("AUTH_SUBJECT_HMAC_SECRET", "")
KAKAO_TOKEN_VERIFY_TIMEOUT = getenv_int("KAKAO_TOKEN_VERIFY_TIMEOUT", 5)
