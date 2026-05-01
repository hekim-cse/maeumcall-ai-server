# core/config.py
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")

def getenv(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if isinstance(v, str) else default

OPENAI_API_KEY = getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_SUGGEST = getenv("OPENAI_MODEL_SUGGEST", OPENAI_MODEL)
OPENAI_MODEL_REWRITE = getenv("OPENAI_MODEL_REWRITE", OPENAI_MODEL)
PROMPT_CACHE = getenv("PROMPT_CACHE", "1") != "0"