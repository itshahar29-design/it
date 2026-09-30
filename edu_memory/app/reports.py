from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import repository as repo
from .texts import BRAND, esc, fmt_date

log = logging.getLogger(__name__)

# Bir vaqtning o'zida faqat bitta hisobot yuborilsin (cron + catch-up to'qnashmasligi uchun)
_send_lock = asyncio.Lock()

SEND_DELAY = 0.05  # Telegram: ~30 xabar/soniya chegarasidan pastda


def weekly_period(fire_date: date) -> tuple[date, date, str]:
    """Dushanba → hisobot kuni (odatda shanba)."""
    start = fire_date - timedelta(days=fire_date.weekday())
    return start, fire_date, fire_date.isoformat()


def monthly_period(fire_date: date) -> tuple[date, date, str]:
    return fire_date.replace(day=1), fire_date, fire_date.strftime("%Y-%m")


def _child_block(name: str, present: int, absent: int, excused: int, percent: float) -> str:
    return (
        f"👤 <b>{esc(name)}</b>\n"
        f"🟢 Bor: {present}\n"
        f"🔴 Yo‘q: {absent}\n"
        f"🟡 Sababli: {excused}\n"
        f"📈 Davomat: {percent:.1f}%"
    )


async def _send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after + 1)
        await bot.send_message(chat_id, text)


async def send_report(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    kind: str,
    title: str,
    start: date,
    end: date,
    period_key: str,
    notify_ids: Iterable[int] = (),
) -> tuple[int, int]:
    """Barcha ota-onalarga individual hisobot yuboradi. (yuborildi, o'tkazib yuborildi) qaytaradi.

    Yuborishda muammo bo'lsa (bot bloklangan yoki xato), adminlarga qisqa xulosa boradi."""
    sent = skipped = blocked = failed = 0
    async with _send_lock:
        async with sessionmaker() as session:
            parents = await repo.get_all_parents_children(session)

        for chat_id, children in parents.items():
            async with sessionmaker() as session:
                if not await repo.claim_report(session, kind, period_key, chat_id):
                    skipped += 1  # allaqachon yuborilgan
                    continue

                blocks = []
                for child in children:
                    stats = await repo.get_stats(session, child.id, start, end)
                    if stats.total == 0:
                        continue  # bu davrda davomat belgilanmagan
                    blocks.append(_child_block(child.full_name, stats.present, stats.absent, stats.excused, stats.percent))

                if not blocks:
                    await repo.release_report(session, kind, period_key, chat_id)
                    skipped += 1
                    continue

                text = (
                    f"📊 <b>{BRAND}</b>\n"
                    f"📅 {title}\n"
                    f"🗓 {fmt_date(start)} — {fmt_date(end)}\n\n" + "\n\n".join(blocks)
                )
                try:
                    await _send(bot, chat_id, text)
                    sent += 1
                except TelegramForbiddenError:
                    log.warning("Ota-ona %s botni bloklagan — hisobot o'tkazib yuborildi", chat_id)
                    blocked += 1
                    skipped += 1
                except Exception:
                    log.exception("Hisobotni %s ga yuborib bo'lmadi — keyingi urinishga qoldirildi", chat_id)
                    await repo.release_report(session, kind, period_key, chat_id)
                    failed += 1
                    skipped += 1
            await asyncio.sleep(SEND_DELAY)

    log.info(
        "%s hisobot [%s]: yuborildi=%s, o'tkazildi=%s, bloklagan=%s, xato=%s",
        kind, period_key, sent, skipped, blocked, failed,
    )
    if blocked or failed:
        summary = (
            f"📤 <b>{BRAND}</b> — {title}\n"
            f"✅ Yuborildi: {sent}\n"
            f"🚫 Botni bloklaganlar: {blocked}\n"
            f"⚠️ Xatolik: {failed}"
        )
        for admin_id in notify_ids:
            try:
                await bot.send_message(admin_id, summary)
            except Exception:
                log.warning("Admin %s ga hisobot xulosasi yuborilmadi", admin_id)
    return sent, skipped


async def send_weekly(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    fire_date: date,
    notify_ids: Iterable[int] = (),
) -> None:
    start, end, key = weekly_period(fire_date)
    await send_report(
        bot, sessionmaker, kind="weekly", title="Haftalik davomat hisoboti",
        start=start, end=end, period_key=key, notify_ids=notify_ids,
    )


async def send_monthly(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    fire_date: date,
    notify_ids: Iterable[int] = (),
) -> None:
    start, end, key = monthly_period(fire_date)
    await send_report(
        bot, sessionmaker, kind="monthly", title="Oylik davomat hisoboti",
        start=start, end=end, period_key=key, notify_ids=notify_ids,
    )
