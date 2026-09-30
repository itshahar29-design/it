from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .reports import send_monthly, send_weekly

log = logging.getLogger(__name__)

CATCHUP_WINDOW = timedelta(hours=24)  # restartdan keyin shuncha vaqt ichida o'tkazib yuborilgan hisobot qayta yuboriladi


def last_weekly_fire(now: datetime, settings: Settings) -> datetime:
    """Eng oxirgi shanba HH:MM (now'dan oldingi)."""
    days_back = (now.weekday() - 5) % 7
    fire = (now - timedelta(days=days_back)).replace(
        hour=settings.report_hour, minute=settings.report_minute, second=0, microsecond=0
    )
    if fire > now:
        fire -= timedelta(days=7)
    return fire


def last_monthly_fire(now: datetime, settings: Settings) -> datetime:
    """Eng oxirgi 'oy oxiri' HH:00 (now'dan oldingi)."""

    def month_end(year: int, month: int) -> datetime:
        day = calendar.monthrange(year, month)[1]
        return now.replace(
            year=year, month=month, day=day, hour=settings.monthly_hour, minute=0, second=0, microsecond=0
        )

    fire = month_end(now.year, now.month)
    if fire > now:
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        fire = month_end(year, month)
    return fire


def build_scheduler(
    bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=settings.tz,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
    )

    async def weekly_job() -> None:
        await send_weekly(bot, sessionmaker, settings.today(), settings.admin_ids)

    async def monthly_job() -> None:
        await send_monthly(bot, sessionmaker, settings.today(), settings.admin_ids)

    async def catch_up() -> None:
        """Bot o'chiq turgan paytda o'tkazib yuborilgan hisobotlarni yuboradi (dublikatdan DB himoya qiladi)."""
        now = settings.now()
        if settings.weekly_enabled:
            fire = last_weekly_fire(now, settings)
            if now - fire <= CATCHUP_WINDOW:
                await send_weekly(bot, sessionmaker, fire.date(), settings.admin_ids)
        if settings.monthly_enabled:
            fire = last_monthly_fire(now, settings)
            if now - fire <= CATCHUP_WINDOW:
                await send_monthly(bot, sessionmaker, fire.date(), settings.admin_ids)

    if settings.weekly_enabled:
        scheduler.add_job(
            weekly_job,
            CronTrigger(
                day_of_week="sat",
                hour=settings.report_hour,
                minute=settings.report_minute,
                timezone=settings.tz,
            ),
            id="weekly_report",
            replace_existing=True,
        )
    if settings.monthly_enabled:
        scheduler.add_job(
            monthly_job,
            CronTrigger(day="last", hour=settings.monthly_hour, minute=0, timezone=settings.tz),
            id="monthly_report",
            replace_existing=True,
        )
    if settings.weekly_enabled or settings.monthly_enabled:
        scheduler.add_job(
            catch_up,
            "date",
            run_date=settings.now() + timedelta(seconds=15),
            id="catch_up",
            replace_existing=True,
        )
    return scheduler
