from __future__ import annotations

import html
from datetime import date

BRAND = "EDU MEMORY"

PRESENT = "present"
ABSENT = "absent"
EXCUSED = "excused"

# Boshlang'ich holat None (⚪ Belgilanmagan): ⚪ → 🟢 Bor → 🔴 Yo‘q → 🟡 Sababli → 🟢 Bor
STATUS_CYCLE = {None: PRESENT, PRESENT: ABSENT, ABSENT: EXCUSED, EXCUSED: PRESENT}
STATUS_EMOJI = {None: "⚪", PRESENT: "🟢", ABSENT: "🔴", EXCUSED: "🟡"}
STATUS_LABEL = {None: "Belgilanmagan", PRESENT: "Bor", ABSENT: "Yo‘q", EXCUSED: "Sababli"}

ADMIN_ONLY = "⛔ Bu buyruq faqat o‘qituvchilar (adminlar) uchun."


def esc(value: str) -> str:
    return html.escape(value, quote=False)


def fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def stats_block(name: str, present: int, absent: int, excused: int, total: int, percent: float) -> str:
    return (
        f"👤 <b>{esc(name)}</b>\n"
        f"🟢 Bor: {present}\n"
        f"🔴 Yo‘q: {absent}\n"
        f"🟡 Sababli: {excused}\n"
        f"📚 Jami: {total}\n"
        f"📈 Davomat: {percent:.1f}%"
    )


ADMIN_HELP = (
    f"👨‍🏫 <b>{BRAND}</b> — o‘qituvchi paneli\n\n"
    "/davomat — bugungi davomatni belgilash\n"
    "/add_student — yangi o‘quvchi qo‘shish\n"
    "/students — o‘quvchilar ro‘yxati va ID kodlari\n"
    "/manage — o‘quvchini tahrirlash yoki o‘chirish\n"
    "/cancel — joriy amalni bekor qilish\n"
    "/link — o‘zingizni ham ota-ona sifatida bog‘lash"
)

PARENT_HELP = (
    f"👋 <b>{BRAND}</b>\n\n"
    "📊 Davomat — farzandingiz davomati statistikasi\n"
    "➕ Farzand qo‘shish — yana bir farzandni ID kodi orqali bog‘lash\n\n"
    "Haftalik hisobot har shanba 18:00 da avtomatik yuboriladi."
)

ASK_CODE = "🔑 Farzandingizning maxsus ID kodini kiriting:"
CODE_NOT_FOUND = "❌ Bunday student kodi topilmadi."
LINK_OK = f"✅ Farzandingiz {BRAND} tizimiga muvaffaqiyatli bog‘landi."
