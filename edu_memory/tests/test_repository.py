from datetime import date, timedelta
import pytest
from app import repository as repo
from app.texts import PRESENT, ABSENT, EXCUSED

@pytest.mark.asyncio
async def test_add_and_list_students(async_session):
    s1 = await repo.add_student(async_session, "Valiyev Ali")
    s2 = await repo.add_student(async_session, "Anvarov Bekzod")

    assert s1.id is not None
    assert len(s1.student_code) == 6
    assert s2.id is not None

    students = await repo.list_students(async_session)
    assert len(students) == 2
    # Tartiblangan bo'lishi kerak: Anvarov Bekzod, keyin Valiyev Ali
    assert students[0].full_name == "Anvarov Bekzod"
    assert students[1].full_name == "Valiyev Ali"

@pytest.mark.asyncio
async def test_get_student_by_code(async_session):
    student = await repo.add_student(async_session, "Jasur Toshmatov")
    code = student.student_code

    # Aniq kod bo'yicha topish
    found = await repo.get_student_by_code(async_session, code)
    assert found is not None
    assert found.id == student.id

    # Kichik harf va probellar bilan kiritilganda ham normalize qilinishi kerak
    found_normalized = await repo.get_student_by_code(async_session, f"  {code.lower()}  ")
    assert found_normalized is not None
    assert found_normalized.id == student.id

    # Noto'g'ri kod
    not_found = await repo.get_student_by_code(async_session, "WRONG1")
    assert not_found is None

@pytest.mark.asyncio
async def test_rename_and_delete_student(async_session):
    student = await repo.add_student(async_session, "Eski Ism")
    renamed = await repo.rename_student(async_session, student.id, "Yangi Ism")
    assert renamed is not None
    assert renamed.full_name == "Yangi Ism"

    # O'chirish
    ok = await repo.delete_student(async_session, student.id)
    assert ok is True
    assert await repo.get_student(async_session, student.id) is None

    # Mavjud bo'lmagan o'quvchini o'chirish
    assert await repo.delete_student(async_session, 999999) is False

@pytest.mark.asyncio
async def test_parent_linking(async_session):
    s1 = await repo.add_student(async_session, "Farzand 1")
    s2 = await repo.add_student(async_session, "Farzand 2")

    chat_id = 987654321

    # 1-marta bog'lash: True
    assert await repo.link_parent(async_session, chat_id, s1.id) is True
    assert await repo.link_parent(async_session, chat_id, s2.id) is True

    # 2-marta bog'lash: False (allaqachon bog'langan)
    assert await repo.link_parent(async_session, chat_id, s1.id) is False

    children = await repo.get_children(async_session, chat_id)
    assert len(children) == 2
    assert {c.id for c in children} == {s1.id, s2.id}

@pytest.mark.asyncio
async def test_attendance_save_and_upsert(async_session):
    s1 = await repo.add_student(async_session, "O'quvchi 1")
    s2 = await repo.add_student(async_session, "O'quvchi 2")

    today = date(2026, 9, 30)

    # Birinchi marta saqlash
    count = await repo.save_attendance(async_session, today, {
        s1.id: PRESENT,
        s2.id: ABSENT,
    })
    assert count == 2

    att_map = await repo.get_attendance_map(async_session, today)
    assert att_map[s1.id] == PRESENT
    assert att_map[s2.id] == ABSENT

    # Yangilash (upsert) — s2 sababli bo'ldi
    count_update = await repo.save_attendance(async_session, today, {
        s1.id: PRESENT,
        s2.id: EXCUSED,
    })
    assert count_update == 2

    att_map_updated = await repo.get_attendance_map(async_session, today)
    assert att_map_updated[s1.id] == PRESENT
    assert att_map_updated[s2.id] == EXCUSED

@pytest.mark.asyncio
async def test_drafts(async_session):
    student = await repo.add_student(async_session, "O'quvchi Draft")
    today = date(2026, 9, 30)

    await repo.set_draft(async_session, today, student.id, PRESENT)
    drafts = await repo.get_draft_map(async_session, today)
    assert drafts[student.id] == PRESENT

    # Draftni yangilash
    await repo.set_draft(async_session, today, student.id, ABSENT)
    drafts = await repo.get_draft_map(async_session, today)
    assert drafts[student.id] == ABSENT

    # Tozalash
    await repo.clear_drafts(async_session, today)
    drafts_empty = await repo.get_draft_map(async_session, today)
    assert len(drafts_empty) == 0

@pytest.mark.asyncio
async def test_stats_calculation(async_session):
    student = await repo.add_student(async_session, "Statistika Talabasi")

    d1 = date(2026, 9, 1)
    d2 = date(2026, 9, 2)
    d3 = date(2026, 9, 3)
    d4 = date(2026, 9, 4)

    await repo.save_attendance(async_session, d1, {student.id: PRESENT})
    await repo.save_attendance(async_session, d2, {student.id: PRESENT})
    await repo.save_attendance(async_session, d3, {student.id: ABSENT})
    await repo.save_attendance(async_session, d4, {student.id: EXCUSED})

    stats = await repo.get_stats(async_session, student.id)
    assert stats.present == 2
    assert stats.absent == 1
    assert stats.excused == 1
    assert stats.total == 4
    assert stats.percent == 50.0

@pytest.mark.asyncio
async def test_report_claim_and_release(async_session):
    chat_id = 112233
    kind = "weekly"
    period = "2026-W40"

    # Birinchi claim muvaffaqiyatli
    assert await repo.claim_report(async_session, kind, period, chat_id) is True

    # Ikkinchi claim dublikat bo'lgani uchun False
    assert await repo.claim_report(async_session, kind, period, chat_id) is False

    # Bekor qilish (release)
    await repo.release_report(async_session, kind, period, chat_id)

    # Release qilingandan so'ng yana claim qilish mumkin
    assert await repo.claim_report(async_session, kind, period, chat_id) is True
