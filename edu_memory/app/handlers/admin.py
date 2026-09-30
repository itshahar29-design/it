from __future__ import annotations

import logging
import re
from datetime import date, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from .. import repository as repo
from ..config import Settings
from ..keyboards import (
    BTN_ADMIN_ADD,
    BTN_ADMIN_ATTENDANCE,
    BTN_ADMIN_MANAGE,
    BTN_ADMIN_STUDENTS,
    PAGE_SIZE,
    admin_menu,
    attendance_keyboard,
    delete_confirm_keyboard,
    page_count,
    student_card_keyboard,
    students_manage_keyboard,
)
from ..models import Student
from ..texts import ADMIN_HELP, BRAND, STATUS_CYCLE, STATUS_EMOJI, STATUS_LABEL, esc, fmt_date

log = logging.getLogger(__name__)

NAME_RE = re.compile(r"^[^\W\d_][^\d_]{1,99}$", re.UNICODE)


class AddStudent(StatesGroup):
    name = State()


class RenameStudent(StatesGroup):
    name = State()


# ---------- Davomat: yordamchi funksiyalar ----------

async def _current_state(
    session: AsyncSession, day: date, students: list[Student]
) -> tuple[dict[int, str], bool]:
    """Saqlangan davomat + saqlanmagan qoralama. (statuslar, qoralama_bormi)."""
    statuses = await repo.get_attendance_map(session, day)
    drafts = await repo.get_draft_map(session, day)
    statuses.update(drafts)
    ids = {s.id for s in students}
    return {sid: st for sid, st in statuses.items() if sid in ids}, bool(drafts)


def _render(day: date, students: list[Student], statuses: dict[int, str], page: int, dirty: bool):
    pages = page_count(len(students))
    page = min(max(page, 0), pages - 1)
    chunk = students[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    lines = [f"📋 <b>{BRAND} — Davomat</b>", f"📅 {fmt_date(day)}", ""]
    for student in chunk:
        status = statuses.get(student.id)
        lines.append(f"{esc(student.full_name)} — {STATUS_EMOJI[status]} {STATUS_LABEL[status]}")

    counts: dict[str | None, int] = {key: 0 for key in STATUS_CYCLE}
    for student in students:
        counts[statuses.get(student.id)] += 1
    lines.append("")
    lines.append(
        f"🟢 {counts['present']}  🔴 {counts['absent']}  🟡 {counts['excused']}  "
        f"⚪ {counts[None]}  ·  📚 {len(students)}"
    )
    if pages > 1:
        lines.append(f"📄 Sahifa {page + 1}/{pages}")
    if counts[None]:
        lines.append(f"⚠️ {counts[None]} ta o‘quvchi belgilanmagan. Hammasini belgilab, «Saqlash»ni bosing.")
    elif dirty:
        lines.append("✏️ O‘zgarishlar hali saqlanmagan — «Saqlash»ni bosing.")
    else:
        lines.append("💾 Saqlangan")

    return "\n".join(lines), attendance_keyboard(day, students, statuses, page)


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _parse_day(key: str) -> date | None:
    try:
        return datetime.strptime(key, "%Y%m%d").date()
    except ValueError:
        return None


def _students_header(count: int) -> str:
    return f"🛠 <b>{BRAND} — O‘quvchilarni boshqarish ({count})</b>\nO‘quvchini tanlang:"


def build_router(settings: Settings) -> Router:
    router = Router(name="admin")
    is_admin = F.from_user.id.in_(settings.admin_ids)
    router.message.filter(is_admin)
    router.callback_query.filter(is_admin)

    # ---------- /start, /help, /cancel ----------
    @router.message(Command("start", "help"))
    async def admin_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(ADMIN_HELP, reply_markup=admin_menu())

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        if await state.get_state() is None:
            await message.answer("Bekor qilinadigan amal yo‘q.", reply_markup=admin_menu())
            return
        await state.clear()
        await message.answer("❎ Bekor qilindi.", reply_markup=admin_menu())

    @router.callback_query(F.data == "noop")
    async def noop(callback: CallbackQuery) -> None:
        await callback.answer()

    # ---------- Davomat ----------
    @router.message(Command("davomat"))
    @router.message(F.text == BTN_ADMIN_ATTENDANCE)
    async def attendance(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await state.clear()
        students = await repo.list_students(session)
        if not students:
            await message.answer(
                "📭 Hali o‘quvchilar yo‘q. /add_student orqali o‘quvchi qo‘shing.",
                reply_markup=admin_menu(),
            )
            return
        day = settings.today()
        await repo.purge_old_drafts(session, day)  # kechagi tugallanmagan qoralamalar o'chadi
        statuses, dirty = await _current_state(session, day, students)
        text, markup = _render(day, students, statuses, 0, dirty)
        await message.answer(text, reply_markup=markup)

    @router.callback_query(F.data.startswith("att:t:"))
    async def toggle(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, key, sid, page = (callback.data or "").split(":")
            student_id, page_no = int(sid), int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        day = _parse_day(key)
        if day is None:
            await callback.answer("Noto‘g‘ri sana.", show_alert=True)
            return

        students = await repo.list_students(session)
        if student_id not in {s.id for s in students}:
            await callback.answer("O‘quvchi topilmadi. /davomat ni qayta yuboring.", show_alert=True)
            return

        statuses, _ = await _current_state(session, day, students)
        new_status = STATUS_CYCLE[statuses.get(student_id)]
        await repo.set_draft(session, day, student_id, new_status)
        statuses[student_id] = new_status

        text, markup = _render(day, students, statuses, page_no, True)
        await _edit(callback, text, markup)
        await callback.answer()

    @router.callback_query(F.data.startswith("att:p:"))
    async def paginate(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, key, page = (callback.data or "").split(":")
            page_no = int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        day = _parse_day(key)
        if day is None:
            await callback.answer("Noto‘g‘ri sana.", show_alert=True)
            return
        students = await repo.list_students(session)
        statuses, dirty = await _current_state(session, day, students)
        text, markup = _render(day, students, statuses, page_no, dirty)
        await _edit(callback, text, markup)
        await callback.answer()

    @router.callback_query(F.data.startswith("att:s:"))
    async def save(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, key, page = (callback.data or "").split(":")
            page_no = int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        day = _parse_day(key)
        if day is None:
            await callback.answer("Noto‘g‘ri sana.", show_alert=True)
            return

        students = await repo.list_students(session)
        statuses, _ = await _current_state(session, day, students)

        missing = [s.full_name for s in students if s.id not in statuses]
        if missing:
            # Belgilanmagan o'quvchi bo'lsa saqlanmaydi — noto'g'ri davomat ketib qolmasin
            names = ", ".join(missing[:3]) + (f" va yana {len(missing) - 3} ta" if len(missing) > 3 else "")
            await callback.answer(f"⚠️ Belgilanmagan: {names}"[:190], show_alert=True)
            return

        await repo.save_attendance(session, day, statuses)
        await repo.clear_drafts(session, day)

        text, markup = _render(day, students, statuses, page_no, False)
        await _edit(callback, text, markup)
        await callback.answer("💾 Saqlandi")

    # ---------- O'quvchilar ro'yxati ----------
    @router.message(Command("students"))
    @router.message(F.text == BTN_ADMIN_STUDENTS)
    async def students_list(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await state.clear()
        students = await repo.list_students(session)
        if not students:
            await message.answer("📭 Hali o‘quvchilar yo‘q. /add_student orqali qo‘shing.")
            return
        header = f"👥 <b>{BRAND} — O‘quvchilar ({len(students)})</b>\n"
        chunk, size = [header], len(header)
        for index, student in enumerate(students, 1):
            line = f"{index}. {esc(student.full_name)} — <code>{student.student_code}</code>"
            if size + len(line) > 3800:
                await message.answer("\n".join(chunk))
                chunk, size = [], 0
            chunk.append(line)
            size += len(line) + 1
        await message.answer("\n".join(chunk))

    # ---------- O'quvchini qo'shish ----------
    @router.message(Command("add_student"))
    @router.message(F.text == BTN_ADMIN_ADD)
    async def add_student_start(
        message: Message,
        state: FSMContext,
        session: AsyncSession,
        command: CommandObject | None = None,
    ) -> None:
        await state.clear()
        if command and command.args:
            await _create_student(message, session, command.args)
            return
        await state.set_state(AddStudent.name)
        await message.answer("👤 Ism-familiya:\n\n(bekor qilish: /cancel)")

    async def _create_student(message: Message, session: AsyncSession, raw_name: str) -> bool:
        name = " ".join(raw_name.split())
        if not NAME_RE.match(name):
            await message.answer("❌ Ism-familiya noto‘g‘ri. Raqamlarsiz, kamida 2 ta belgi bo‘lsin. Qayta kiriting:")
            return False
        student = await repo.add_student(session, name)
        await message.answer(
            f"✅ O‘quvchi qo‘shildi\n"
            f"👤 {esc(student.full_name)}\n"
            f"🔑 Student ID: <code>{student.student_code}</code>\n\n"
            "Bu kodni ota-onaga bering — ular botga kirib shu kod bilan bog‘lanishadi.",
            reply_markup=admin_menu(),
        )
        return True

    # ---------- O'quvchini tahrirlash / o'chirish ----------
    @router.message(Command("manage", "edit_student", "delete_student"))
    @router.message(F.text == BTN_ADMIN_MANAGE)
    async def manage(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await state.clear()
        students = await repo.list_students(session)
        if not students:
            await message.answer("📭 Hali o‘quvchilar yo‘q. /add_student orqali qo‘shing.")
            return
        await message.answer(_students_header(len(students)), reply_markup=students_manage_keyboard(students, 0))

    @router.callback_query(F.data.startswith("stu:l:"))
    async def manage_page(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            page = int((callback.data or "").split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        students = await repo.list_students(session)
        if not students:
            await _edit(callback, "📭 Hali o‘quvchilar yo‘q.", None)
        else:
            await _edit(callback, _students_header(len(students)), students_manage_keyboard(students, page))
        await callback.answer()

    @router.callback_query(F.data.startswith("stu:v:"))
    async def student_card(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, sid, page = (callback.data or "").split(":")
            student_id, page_no = int(sid), int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        student = await repo.get_student(session, student_id)
        if student is None:
            await callback.answer("O‘quvchi topilmadi.", show_alert=True)
            return
        await _edit(
            callback,
            f"👤 <b>{esc(student.full_name)}</b>\n🔑 Student ID: <code>{student.student_code}</code>",
            student_card_keyboard(student.id, page_no),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("stu:r:"))
    async def rename_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
        try:
            student_id = int((callback.data or "").split(":")[2])
        except (ValueError, IndexError):
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        student = await repo.get_student(session, student_id)
        if student is None or not isinstance(callback.message, Message):
            await callback.answer("O‘quvchi topilmadi.", show_alert=True)
            return
        await state.set_state(RenameStudent.name)
        await state.update_data(student_id=student_id)
        await callback.message.answer(
            f"✏️ <b>{esc(student.full_name)}</b> uchun yangi ism-familiyani kiriting:\n\n(bekor qilish: /cancel)"
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("stu:d:"))
    async def delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, sid, page = (callback.data or "").split(":")
            student_id, page_no = int(sid), int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        student = await repo.get_student(session, student_id)
        if student is None:
            await callback.answer("O‘quvchi topilmadi.", show_alert=True)
            return
        await _edit(
            callback,
            f"🗑 <b>{esc(student.full_name)}</b> o‘chirilsinmi?\n\n"
            "⚠️ Uning barcha davomat yozuvlari va ota-ona bog‘lanishlari ham o‘chadi. Bu amalni qaytarib bo‘lmaydi.",
            delete_confirm_keyboard(student.id, page_no),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("stu:x:"))
    async def delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
        try:
            _, _, sid, page = (callback.data or "").split(":")
            student_id, page_no = int(sid), int(page)
        except ValueError:
            await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
            return
        student = await repo.get_student(session, student_id)
        name = student.full_name if student else None
        deleted = await repo.delete_student(session, student_id)
        students = await repo.list_students(session)
        if students:
            await _edit(callback, _students_header(len(students)), students_manage_keyboard(students, page_no))
        else:
            await _edit(callback, "📭 Hali o‘quvchilar yo‘q.", None)
        await callback.answer(f"🗑 {name} o‘chirildi" if deleted and name else "O‘quvchi topilmadi.")

    # ---------- FSM matn handlerlari (menyu tugmalaridan KEYIN turishi shart) ----------
    @router.message(StateFilter(AddStudent.name), F.text, ~F.text.startswith("/"))
    async def add_student_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
        if await _create_student(message, session, message.text or ""):
            await state.clear()

    @router.message(StateFilter(RenameStudent.name), F.text, ~F.text.startswith("/"))
    async def rename_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
        name = " ".join((message.text or "").split())
        if not NAME_RE.match(name):
            await message.answer("❌ Ism-familiya noto‘g‘ri. Raqamlarsiz, kamida 2 ta belgi bo‘lsin. Qayta kiriting:")
            return
        data = await state.get_data()
        student = await repo.rename_student(session, int(data.get("student_id", 0)), name)
        await state.clear()
        if student is None:
            await message.answer("❌ O‘quvchi topilmadi.", reply_markup=admin_menu())
            return
        await message.answer(
            f"✅ Ism yangilandi: <b>{esc(student.full_name)}</b>\n🔑 <code>{student.student_code}</code>",
            reply_markup=admin_menu(),
        )

    # Admin tasodifiy matn yuborsa — ota-ona kodi so'ralmasin, yordam ko'rsatilsin
    @router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
    async def admin_fallback(message: Message) -> None:
        await message.answer(ADMIN_HELP, reply_markup=admin_menu())

    return router
