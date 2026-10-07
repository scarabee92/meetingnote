"""환경 설정. 키는 .env 로만 읽는다."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

PORT = 8000
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO = {".mp3": "audio/mpeg", ".wav": "audio/wav"}


def get_database_url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{BACKEND_DIR / 'meetingnote.db'}"


def get_gemini_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or None


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite"
