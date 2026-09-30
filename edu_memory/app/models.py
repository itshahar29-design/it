from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    student_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Parent(Base):
    """Ota-ona (chat) va farzand bog'lanishi. Bir ota-onaga bir nechta farzand mumkin."""

    __tablename__ = "parents"

    parent_chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    linked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_parents_student_id", "student_id"),)


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        CheckConstraint("status IN ('present','absent','excused')", name="ck_attendance_status"),
        Index("ix_attendance_date", "date"),
    )


class ReportLog(Base):
    """Hisobot ikki marta yuborilib ketmasligi uchun himoya jadvali."""

    __tablename__ = "report_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # weekly | monthly
    period_key: Mapped[str] = mapped_column(String(16), nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("kind", "period_key", "chat_id", name="uq_report_once"),)


class AttendanceDraft(Base):
    """Saqlanmagan davomat belgilari. Bot restart bo'lsa ham yo'qolmaydi."""

    __tablename__ = "attendance_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_draft_student_date"),
        CheckConstraint("status IN ('present','absent','excused')", name="ck_draft_status"),
        Index("ix_draft_date", "date"),
    )
