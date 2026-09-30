from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from .. import repository as repo
from ..config import Settings
from ..keyboards import BTN_PARENT_ADD, BTN_PARENT_STATS, parent_menu
from ..texts import (
    ADMIN_ONLY,
    ASK_CODE,
    BRAND,
    CODE_NOT_FOUND,
    LINK_OK,
    PARENT_HELP,
    esc,
    stats_block,
)

log = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
BLOCK_WINDOW_SEC = 600


class LinkParent(StatesGroup):
    waiting_code = State()


class _AttemptLimiter:
    """Student kodini tanlab topishga urinishlarni cheklaydi."""

    def __init__(self) -> None:
        self._fails: dict[int, deque[float]] = defaultdict(deque)

    def _prune(self, chat_id: int) -> deque[float]:
        bucket = self._fails[chat_id]
        cutoff = time.monotonic() - BLOCK_WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return bucket

    def blocked(self, chat_id: int) -> bool:
        return len(self._prune(chat_id)) >= MAX_FAILED_ATTEMPTS

    def fail(self, chat_id: int) -> None:
        self._prune(chat_id).append(time.monotonic())


def build_router(settings: Settings) -> Router:
    router = Router(name="parent")
    limiter = _AttemptLimiter()

    async def ask_code(message: Message, state: FSMContext) -> None:
        await state.set_state(LinkParent.waiting_code)
        await message.answer(ASK_CODE)

    async def show_stats(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await state.clear()
        children = await repo.get_children(session, message.chat.id)
        if not children:
            await ask_code(message, state)
            return
        blocks = []
        for child in children:
            s = await repo.get_stats(session, child.id)
            blocks.append(stats_block(child.full_name, s.present, s.absent, s.excused, s.total, s.percent))
        await message.answer(f"📊 <b>{BRAND}</b>\n\n" + "\n\n".join(blocks), reply_markup=parent_menu())

    # ---------- /start ----------
    @router.message(Command("start"))
    async def start(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await state.clear()
        children = await repo.get_children(session, message.chat.id)
        if children:
            await message.answer(PARENT_HELP, reply_markup=parent_menu())
        else:
            await message.answer(
                f"👋 <b>{BRAND}</b> tizimiga xush kelibsiz!\n"
                "Bu bot farzandingizning maktab davomatini kuzatish uchun.",
            )
            await ask_code(message, state)

    @router.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        await message.answer(PARENT_HELP, reply_markup=parent_menu())

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("❎ Bekor qilindi.", reply_markup=parent_menu())

    # ---------- Menyu tugmalari (FSM matn handlerdan OLDIN turishi shart) ----------
    @router.message(Command("stats"))
    @router.message(F.text == BTN_PARENT_STATS)
    async def stats(message: Message, session: AsyncSession, state: FSMContext) -> None:
        await show_stats(message, session, state)

    @router.message(Command("link"))
    @router.message(F.text == BTN_PARENT_ADD)
    async def link(message: Message, state: FSMContext) -> None:
        await ask_code(message, state)

    # ---------- Admin buyruqlari oddiy foydalanuvchiga yopiq ----------
    @router.message(Command("davomat", "add_student", "students"))
    async def not_admin(message: Message) -> None:
        await message.answer(ADMIN_ONLY)

    @router.callback_query(F.data.startswith("att:"))
    async def not_admin_callback(callback: CallbackQuery) -> None:
        await callback.answer(ADMIN_ONLY, show_alert=True)

    @router.callback_query(F.data == "noop")
    async def noop(callback: CallbackQuery) -> None:
        await callback.answer()

    # ---------- Student kodini qabul qilish ----------
    @router.message(StateFilter(LinkParent.waiting_code), F.text, ~F.text.startswith("/"))
    async def receive_code(message: Message, session: AsyncSession, state: FSMContext) -> None:
        chat_id = message.chat.id
        if limiter.blocked(chat_id):
            await message.answer("⏳ Juda ko‘p noto‘g‘ri urinish. Bir necha daqiqadan keyin qayta urinib ko‘ring.")
            return

        student = await repo.get_student_by_code(session, message.text or "")
        if student is None:
            limiter.fail(chat_id)
            await message.answer(f"{CODE_NOT_FOUND}\nKodni tekshirib, qayta kiriting yoki /cancel bosing.")
            return

        created = await repo.link_parent(session, chat_id, student.id)
        await state.clear()
        if created:
            await message.answer(f"{LINK_OK}\n👤 {esc(student.full_name)}", reply_markup=parent_menu())
        else:
            await message.answer(f"ℹ️ {esc(student.full_name)} allaqachon bog‘langan.", reply_markup=parent_menu())

    @router.message(F.text, ~F.text.startswith("/"))
    async def fallback(message: Message, session: AsyncSession, state: FSMContext) -> None:
        children = await repo.get_children(session, message.chat.id)
        if children:
            await message.answer(PARENT_HELP, reply_markup=parent_menu())
        else:
            await ask_code(message, state)

    return router
