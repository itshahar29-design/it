from __future__ import annotations

import math
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Student
from .texts import STATUS_EMOJI

PAGE_SIZE = 20

BTN_ADMIN_ATTENDANCE = "📋 Davomat"
BTN_ADMIN_STUDENTS = "👥 O‘quvchilar"
BTN_ADMIN_ADD = "➕ O‘quvchi qo‘shish"
BTN_ADMIN_MANAGE = "🛠 Boshqarish"
BTN_PARENT_STATS = "📊 Davomat"
BTN_PARENT_ADD = "➕ Farzand qo‘shish"


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADMIN_ATTENDANCE)],
            [KeyboardButton(text=BTN_ADMIN_STUDENTS), KeyboardButton(text=BTN_ADMIN_ADD)],
            [KeyboardButton(text=BTN_ADMIN_MANAGE)],
        ],
        resize_keyboard=True,
    )


def parent_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_PARENT_STATS), KeyboardButton(text=BTN_PARENT_ADD)]],
        resize_keyboard=True,
    )


def page_count(total: int) -> int:
    return max(1, math.ceil(total / PAGE_SIZE))


def attendance_keyboard(
    day: date,
    students: list[Student],
    statuses: dict[int, str],
    page: int,
) -> InlineKeyboardMarkup:
    """Callback formati: att:t:<YYYYMMDD>:<student_id>:<page> | att:p:<YYYYMMDD>:<page> | att:s:<YYYYMMDD>:<page>"""
    key = day.strftime("%Y%m%d")
    pages = page_count(len(students))
    page = min(max(page, 0), pages - 1)
    chunk = students[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    builder = InlineKeyboardBuilder()
    for student in chunk:
        emoji = STATUS_EMOJI[statuses.get(student.id)]
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {student.full_name}"[:60],
                callback_data=f"att:t:{key}:{student.id}:{page}",
            )
        )

    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"att:p:{key}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"att:p:{key}:{page + 1}"))
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="💾 Saqlash", callback_data=f"att:s:{key}:{page}"))
    return builder.as_markup()


def students_manage_keyboard(students: list[Student], page: int) -> InlineKeyboardMarkup:
    """Callback: stu:l:<page> (ro'yxat) | stu:v:<id>:<page> (kartochka)"""
    pages = page_count(len(students))
    page = min(max(page, 0), pages - 1)
    builder = InlineKeyboardBuilder()
    for student in students[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]:
        builder.row(
            InlineKeyboardButton(text=student.full_name[:60], callback_data=f"stu:v:{student.id}:{page}")
        )
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"stu:l:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"stu:l:{page + 1}"))
        builder.row(*nav)
    return builder.as_markup()


def student_card_keyboard(student_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Ismni o‘zgartirish", callback_data=f"stu:r:{student_id}"))
    builder.row(InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"stu:d:{student_id}:{page}"))
    builder.row(InlineKeyboardButton(text="⬅️ Ro‘yxatga qaytish", callback_data=f"stu:l:{page}"))
    return builder.as_markup()


def delete_confirm_keyboard(student_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o‘chirish", callback_data=f"stu:x:{student_id}:{page}"),
        InlineKeyboardButton(text="❌ Yo‘q", callback_data=f"stu:v:{student_id}:{page}"),
    )
    return builder.as_markup()
