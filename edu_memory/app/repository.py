from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Attendance, AttendanceDraft, Parent, ReportLog, Student
from .texts import ABSENT, EXCUSED, PRESENT

# O'xshash belgilar (0/O, 1/I) chiqarib tashlangan
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


@dataclass(frozen=True)
class Stats:
    present: int = 0
    absent: int = 0
    excused: int = 0

    @property
    def total(self) -> int:
        return self.present + self.absent + self.excused

    @property
    def percent(self) -> float:
        return (self.present / self.total * 100) if self.total else 0.0


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str:
    return "".join(raw.split()).upper()


# ---------- O'quvchilar ----------

async def add_student(session: AsyncSession, full_name: str) -> Student:
    for _ in range(20):
        student = Student(full_name=full_name, student_code=generate_code())
        session.add(student)
        try:
            await session.commit()
            return student
        except IntegrityError:  # kod to'qnashuvi — yangisini yaratamiz
            await session.rollback()
    raise RuntimeError("Unique student kodi yaratib bo'lmadi")


async def list_students(session: AsyncSession) -> list[Student]:
    result = await session.execute(select(Student).order_by(Student.full_name, Student.id))
    return list(result.scalars())


async def get_student_by_code(session: AsyncSession, code: str) -> Student | None:
    result = await session.execute(select(Student).where(Student.student_code == normalize_code(code)))
    return result.scalar_one_or_none()


async def get_student(session: AsyncSession, student_id: int) -> Student | None:
    return await session.get(Student, student_id)


async def rename_student(session: AsyncSession, student_id: int, full_name: str) -> Student | None:
    student = await session.get(Student, student_id)
    if student is None:
        return None
    student.full_name = full_name
    await session.commit()
    return student


async def delete_student(session: AsyncSession, student_id: int) -> bool:
    """O'quvchini o'chiradi. Davomat, qoralama va ota-ona bog'lanishlari FK CASCADE orqali o'chadi."""
    student = await session.get(Student, student_id)
    if student is None:
        return False
    await session.delete(student)
    await session.commit()
    return True


# ---------- Ota-onalar ----------

async def link_parent(session: AsyncSession, chat_id: int, student_id: int) -> bool:
    """Yangi bog'lanish yaratilsa True, allaqachon bor bo'lsa False."""
    existing = await session.get(Parent, (chat_id, student_id))
    if existing:
        return False
    session.add(Parent(parent_chat_id=chat_id, student_id=student_id))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def get_children(session: AsyncSession, chat_id: int) -> list[Student]:
    result = await session.execute(
        select(Student)
        .join(Parent, Parent.student_id == Student.id)
        .where(Parent.parent_chat_id == chat_id)
        .order_by(Student.full_name, Student.id)
    )
    return list(result.scalars())


async def get_all_parents_children(session: AsyncSession) -> dict[int, list[Student]]:
    result = await session.execute(
        select(Parent.parent_chat_id, Student)
        .join(Student, Parent.student_id == Student.id)
        .order_by(Parent.parent_chat_id, Student.full_name, Student.id)
    )
    grouped: dict[int, list[Student]] = {}
    for chat_id, student in result.all():
        grouped.setdefault(chat_id, []).append(student)
    return grouped


# ---------- Davomat ----------

async def get_attendance_map(session: AsyncSession, day: date) -> dict[int, str]:
    result = await session.execute(
        select(Attendance.student_id, Attendance.status).where(Attendance.date == day)
    )
    return {student_id: status for student_id, status in result.all()}


async def save_attendance(session: AsyncSession, day: date, statuses: dict[int, str]) -> int:
    """Kunlik davomatni saqlaydi. Mavjud yozuv bo'lsa — UPDATE, bo'lmasa — INSERT (upsert)."""
    valid_status = {PRESENT, ABSENT, EXCUSED}
    known_ids = set((await session.execute(select(Student.id))).scalars())
    rows = [
        {"student_id": sid, "date": day, "status": status}
        for sid, status in statuses.items()
        if sid in known_ids and status in valid_status
    ]
    if not rows:
        return 0
    for i in range(0, len(rows), 200):  # SQLite o'zgaruvchilar limitidan oshmaslik uchun bo'laklab
        stmt = sqlite_insert(Attendance).values(rows[i : i + 200])
        stmt = stmt.on_conflict_do_update(
            index_elements=["student_id", "date"],
            set_={"status": stmt.excluded.status},
        )
        await session.execute(stmt)
    await session.commit()
    return len(rows)


# ---------- Davomat qoralamasi (restartdan saqlanadi) ----------

async def get_draft_map(session: AsyncSession, day: date) -> dict[int, str]:
    result = await session.execute(
        select(AttendanceDraft.student_id, AttendanceDraft.status).where(AttendanceDraft.date == day)
    )
    return {student_id: status for student_id, status in result.all()}


async def set_draft(session: AsyncSession, day: date, student_id: int, status: str) -> None:
    stmt = sqlite_insert(AttendanceDraft).values(student_id=student_id, date=day, status=status)
    stmt = stmt.on_conflict_do_update(
        index_elements=["student_id", "date"], set_={"status": stmt.excluded.status}
    )
    await session.execute(stmt)
    await session.commit()


async def clear_drafts(session: AsyncSession, day: date) -> None:
    await session.execute(delete(AttendanceDraft).where(AttendanceDraft.date == day))
    await session.commit()


async def purge_old_drafts(session: AsyncSession, before: date) -> None:
    await session.execute(delete(AttendanceDraft).where(AttendanceDraft.date < before))
    await session.commit()


async def get_stats(
    session: AsyncSession,
    student_id: int,
    start: date | None = None,
    end: date | None = None,
) -> Stats:
    query = select(Attendance.status, func.count()).where(Attendance.student_id == student_id)
    if start is not None:
        query = query.where(Attendance.date >= start)
    if end is not None:
        query = query.where(Attendance.date <= end)
    query = query.group_by(Attendance.status)
    counts = {status: count for status, count in (await session.execute(query)).all()}
    return Stats(
        present=counts.get(PRESENT, 0),
        absent=counts.get(ABSENT, 0),
        excused=counts.get(EXCUSED, 0),
    )


# ---------- Hisobot dublikatidan himoya ----------

async def claim_report(session: AsyncSession, kind: str, period_key: str, chat_id: int) -> bool:
    """Hisobotni 'band qiladi'. True — bu chatga hali yuborilmagan, yuborish mumkin."""
    stmt = (
        sqlite_insert(ReportLog)
        .values(kind=kind, period_key=period_key, chat_id=chat_id)
        .on_conflict_do_nothing(index_elements=["kind", "period_key", "chat_id"])
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount == 1


async def release_report(session: AsyncSession, kind: str, period_key: str, chat_id: int) -> None:
    """Yuborish muvaffaqiyatsiz bo'lsa, keyingi urinish uchun 'band'ni bekor qiladi."""
    row = (
        await session.execute(
            select(ReportLog).where(
                ReportLog.kind == kind,
                ReportLog.period_key == period_key,
                ReportLog.chat_id == chat_id,
            )
        )
    ).scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()


def ids_of(students: Iterable[Student]) -> list[int]:
    return [s.id for s in students]
