"""Gemini 호출: 받아쓰기와 세 갈래 구분."""
import io
import logging
import time

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import get_gemini_api_key, get_gemini_model

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_MS = 120_000
INLINE_LIMIT_BYTES = 15 * 1024 * 1024  # 이보다 크면 File API 로 올린다
FILE_POLL_SECONDS = 2
FILE_POLL_MAX = 60

TRANSCRIBE_PROMPT = (
    "이 녹취를 들리는 그대로 한국어로 받아써라. "
    "요약, 설명, 머리말 없이 받아쓴 본문만 출력해라."
)

CLASSIFY_PROMPT = """다음 회의 본문을 세 갈래로 구분해라.
요약   - 회의 전체를 3~5줄로. 새로운 사실을 지어내지 말 것
결정사항 - 「하기로 했다 / 확정 / 승인」 처럼 합의가 끝난 것만
       논의만 하고 안 정한 것은 넣지 말 것
할 일   - 담당자와 기한이 드러난 것만. 담당자가 없으면 미정으로 적을 것
       기한은 회의에서 말한 그대로 적고 날짜로 바꾸지 말 것
셋 중 어디에도 안 들어가는 잡담은 버릴 것

회의 본문:
"""


class GeminiError(Exception):
    """Gemini 호출 실패 (키 없음, API 오류, 응답 형식 오류 등)."""


class _TodoItem(BaseModel):
    what: str
    who: str
    when: str


class _Classified(BaseModel):
    summary: str
    decisions: list[str]
    todos: list[_TodoItem]


# 클라이언트는 모듈에 한 번만 만들어 재사용한다 (호출 도중 회수 방지)
_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = get_gemini_api_key()
        if not api_key:
            raise GeminiError("GEMINI_API_KEY 가 설정되지 않았다")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    return _client


def _clean(text: str) -> str:
    """todos 저장 형식의 구분자(|)와 줄바꿈이 값에 섞이지 않게 한다."""
    return " ".join(text.replace("|", "/").split())


def format_classified(result: _Classified) -> dict[str, str]:
    decisions = [_clean(item) for item in result.decisions if _clean(item)]
    todos = [
        f"{_clean(t.what)} | {_clean(t.who) or '미정'} | {_clean(t.when)}"
        for t in result.todos
        if _clean(t.what)
    ]
    return {
        "summary": result.summary.strip(),
        "decisions": "\n".join(decisions),
        "todos": "\n".join(todos),
    }


def classify(body: str) -> dict[str, str]:
    """본문을 summary / decisions / todos 로 나눈다. 실패하면 GeminiError."""
    client = get_client()
    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=CLASSIFY_PROMPT + body,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_Classified,
            ),
        )
        result = _Classified.model_validate_json(response.text or "")
    except (errors.APIError, httpx.HTTPError, ValueError) as exc:
        raise GeminiError(f"구분 실패: {exc}") from exc
    return format_classified(result)


def _wait_until_active(client: genai.Client, name: str) -> types.File:
    for _ in range(FILE_POLL_MAX):
        file = client.files.get(name=name)
        state = file.state.name if file.state else None
        if state == "ACTIVE":
            return file
        if state == "FAILED":
            raise GeminiError("업로드한 파일 처리에 실패했다")
        time.sleep(FILE_POLL_SECONDS)
    raise GeminiError("업로드한 파일 처리 시간이 초과됐다")


def transcribe(data: bytes, mime_type: str) -> str:
    """녹취 파일을 본문 텍스트로 받아쓴다. 실패하면 GeminiError."""
    client = get_client()
    uploaded: types.File | None = None
    try:
        if len(data) <= INLINE_LIMIT_BYTES:
            audio = types.Part.from_bytes(data=data, mime_type=mime_type)
        else:
            uploaded = client.files.upload(
                file=io.BytesIO(data), config=types.UploadFileConfig(mime_type=mime_type)
            )
            audio = _wait_until_active(client, uploaded.name)
        response = client.models.generate_content(
            model=get_gemini_model(), contents=[TRANSCRIBE_PROMPT, audio]
        )
        return (response.text or "").strip()
    except (errors.APIError, httpx.HTTPError, ValueError) as exc:
        raise GeminiError(f"받아쓰기 실패: {exc}") from exc
    finally:
        if uploaded is not None:
            try:
                client.files.delete(name=uploaded.name)
            except (errors.APIError, httpx.HTTPError):
                logger.warning("업로드한 임시 파일을 지우지 못했다: %s", uploaded.name)
