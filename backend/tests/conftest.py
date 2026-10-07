import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Meeting


@pytest.fixture(autouse=True)
def pause_after_gemini_test(request):
    """Gemini 호출 테스트는 한도에 걸리지 않게 호출 사이를 1초 띄운다."""
    yield
    if request.node.get_closest_marker("gemini"):
        time.sleep(1)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_note(session_factory):
    """Gemini 를 거치지 않고 DB 에 바로 회의록을 넣는다 (조회·수정·삭제 테스트용)."""

    def _make(**overrides) -> int:
        values = {
            "title": "기획 회의",
            "met_at": datetime(2026, 10, 7, 1, 0, 0),
            "attendees": "김대리, 이주임",
            "body": "원문",
            "summary": "요약",
            "decisions": "결정 1",
            "todos": "보고서 작성 | 김대리 | 다음 주 금요일",
        }
        values.update(overrides)
        with session_factory() as db:
            note = Meeting(**values)
            db.add(note)
            db.commit()
            return note.id

    return _make
