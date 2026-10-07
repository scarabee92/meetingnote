"""Meeting 모델 (02-specs 1장: 필드 8개, 이 순서)."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"
    # SQLite 는 PK 만 주면 지운 id 를 재사용하므로 AUTOINCREMENT 를 명시한다
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    met_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC (naive 로 저장)
    attendees: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    decisions: Mapped[str | None] = mapped_column(Text)
    todos: Mapped[str | None] = mapped_column(Text)
