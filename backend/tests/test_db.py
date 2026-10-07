from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Meeting


def test_meeting_has_8_fields_in_order():
    assert [c.name for c in Meeting.__table__.columns] == [
        "id", "title", "met_at", "attendees", "body", "summary", "decisions", "todos",
    ]


def test_deleted_id_is_not_reused():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        ddl = conn.execute(text("select sql from sqlite_master where name='meetings'")).scalar()
    assert "AUTOINCREMENT" in ddl
    with Session(engine) as db:
        first = Meeting(title="a", met_at=datetime(2026, 1, 1), body="x")
        db.add(first)
        db.commit()
        first_id = first.id
        db.delete(first)
        db.commit()
        second = Meeting(title="b", met_at=datetime(2026, 1, 1), body="x")
        db.add(second)
        db.commit()
        assert second.id > first_id
    assert inspect(engine).has_table("meetings")
