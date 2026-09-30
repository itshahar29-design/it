from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ha"}


def _int(value: str | None, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value) if value not in (None, "") else default
    except ValueError as exc:
        raise RuntimeError(f"Noto'g'ri raqam: {value!r}") from exc
    if not lo <= number <= hi:
        raise RuntimeError(f"Qiymat {lo}..{hi} oralig'ida bo'lishi kerak: {number}")
    return number


def _admin_ids(raw: str | None) -> frozenset[int]:
    ids: set[int] = set()
    for part in (raw or "").replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise RuntimeError(f"ADMIN_IDS ichida noto'g'ri ID: {part!r}") from exc
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    database_url: str
    timezone: str
    weekly_enabled: bool
    report_hour: int
    report_minute: int
    monthly_enabled: bool
    monthly_hour: int

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini yarating (.env.example'dan nusxa oling).")

    admins = _admin_ids(os.getenv("ADMIN_IDS"))
    if not admins:
        raise RuntimeError("ADMIN_IDS bo'sh. Kamida bitta admin Telegram ID'sini kiriting.")

    timezone = os.getenv("TIMEZONE", "Asia/Tashkent").strip() or "Asia/Tashkent"
    ZoneInfo(timezone)  # noto'g'ri bo'lsa, shu yerda xato beradi

    return Settings(
        bot_token=token,
        admin_ids=admins,
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///attendance.db").strip(),
        timezone=timezone,
        weekly_enabled=_bool(os.getenv("WEEKLY_REPORT_ENABLED"), True),
        report_hour=_int(os.getenv("REPORT_HOUR"), 18, 0, 23),
        report_minute=_int(os.getenv("REPORT_MINUTE"), 0, 0, 59),
        monthly_enabled=_bool(os.getenv("MONTHLY_REPORT_ENABLED"), True),
        monthly_hour=_int(os.getenv("MONTHLY_REPORT_HOUR"), 19, 0, 23),
    )
