"""MeetingNote API (02-specs 4장)."""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import PurePath

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import gemini_service
from app.config import ALLOWED_AUDIO, MAX_UPLOAD_BYTES, PORT
from app.database import Base, engine, get_db
from app.gemini_service import GeminiError
from app.models import Meeting
from app.schemas import NoteCreate, NoteListItem, NoteOut, NoteUpdate, TodoOut, UploadOut

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="MeetingNote", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """검증 실패는 400. 스펙 외 필드 오류뿐인 경우에만 422 로 남긴다."""
    errs = exc.errors()
    only_extra = bool(errs) and all(e["type"] == "extra_forbidden" for e in errs)
    return JSONResponse(
        status_code=422 if only_extra else 400,
        content={"detail": jsonable_encoder(errs)},
    )


def get_note_or_404(db: Session, note_id: int) -> Meeting:
    note = db.get(Meeting, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="회의록을 찾을 수 없다")
    return note


@app.post("/api/notes", response_model=NoteOut, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> Meeting:
    parts = {"summary": "", "decisions": "", "todos": ""}
    try:
        parts = gemini_service.classify(payload.body)
    except GeminiError:
        # 구분에 실패해도 저장은 진행한다 (02-specs 7장)
        logger.exception("세 갈래 구분 실패")
    note = Meeting(**payload.model_dump(), **parts)
    db.add(note)
    db.commit()
    return note


@app.get("/api/notes", response_model=list[NoteListItem])
def list_notes(
    q: str | None = None,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
) -> list[Meeting]:
    stmt = select(Meeting)
    if q and q.strip():
        term = q.strip()
        stmt = stmt.where(
            Meeting.title.contains(term, autoescape=True)
            | Meeting.attendees.contains(term, autoescape=True)
        )
    if from_date:
        stmt = stmt.where(Meeting.met_at >= datetime.combine(from_date, time.min))
    if to_date:
        # to 는 그날 끝까지 포함
        stmt = stmt.where(Meeting.met_at < datetime.combine(to_date + timedelta(days=1), time.min))
    stmt = stmt.order_by(Meeting.met_at.desc(), Meeting.id.desc())
    return list(db.scalars(stmt))


@app.get("/api/todos", response_model=list[TodoOut])
def list_todos(db: Session = Depends(get_db)) -> list[TodoOut]:
    notes = db.scalars(select(Meeting).order_by(Meeting.met_at.asc(), Meeting.id.asc()))
    result: list[TodoOut] = []
    for note in notes:
        for line in (note.todos or "").splitlines():
            if not line.strip():
                continue
            # 내용 | 담당자 | 기한 - 내용에 | 가 섞여도 뒤에서부터 나눈다
            pieces = [p.strip() for p in line.rsplit("|", 2)]
            while len(pieces) < 3:
                pieces.append("")
            what, who, when = pieces
            result.append(
                TodoOut(what=what, who=who, when=when, note_id=note.id, note_title=note.title)
            )
    return result


@app.get("/api/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)) -> Meeting:
    return get_note_or_404(db, note_id)


@app.put("/api/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)) -> Meeting:
    note = get_note_or_404(db, note_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    return note


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)) -> Response:
    note = get_note_or_404(db, note_id)
    db.delete(note)
    db.commit()
    return Response(status_code=204)


@app.post("/api/upload", response_model=UploadOut)
def upload_audio(file: UploadFile = File(...)) -> UploadOut:
    suffix = PurePath(file.filename or "").suffix.lower()
    mime_type = ALLOWED_AUDIO.get(suffix)
    if mime_type is None:
        raise HTTPException(status_code=415, detail="mp3, wav 파일만 올릴 수 있다")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="25MB 이하 파일만 올릴 수 있다")
    try:
        text = gemini_service.transcribe(data, mime_type)
    except GeminiError as exc:
        logger.exception("받아쓰기 실패")
        raise HTTPException(status_code=502, detail="받아쓰기 호출에 실패했다") from exc
    return UploadOut(text=text)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT)
