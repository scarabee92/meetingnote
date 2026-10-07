"""요청·응답 스키마. 스펙 외 필드는 extra=forbid 로 막는다."""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def to_utc_naive(value: datetime) -> datetime:
    """tz 가 있으면 UTC 로 바꾸고, 없으면 UTC 로 간주한다."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None)


def format_utc(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    met_at: datetime
    attendees: str | None = None
    body: str = Field(min_length=1)

    _met_at_utc = field_validator("met_at")(to_utc_naive)


class NoteUpdate(NoteCreate):
    """PUT. 보낸 필드만 바꾼다 (선택 필드는 생략하면 그대로 둔다)."""

    summary: str | None = None
    decisions: str | None = None
    todos: str | None = None


class _NoteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    met_at: datetime
    attendees: str | None
    summary: str | None
    decisions: str | None
    todos: str | None

    @field_serializer("met_at")
    def _serialize_met_at(self, value: datetime) -> str:
        return format_utc(value)


class NoteListItem(_NoteBase):
    """목록 응답. body 는 제외한다."""


class NoteOut(_NoteBase):
    body: str


class TodoOut(BaseModel):
    what: str
    who: str
    when: str
    note_id: int
    note_title: str


class UploadOut(BaseModel):
    text: str
