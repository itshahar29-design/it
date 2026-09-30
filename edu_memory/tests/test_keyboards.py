from datetime import date
from app.keyboards import (
    admin_menu,
    parent_menu,
    page_count,
    attendance_keyboard,
    student_card_keyboard,
    delete_confirm_keyboard,
)
from app.models import Student
from app.texts import STATUS_CYCLE, PRESENT, ABSENT, EXCUSED

def test_status_cycle():
    # ⚪ -> 🟢 -> 🔴 -> 🟡 -> 🟢
    assert STATUS_CYCLE[None] == PRESENT
    assert STATUS_CYCLE[PRESENT] == ABSENT
    assert STATUS_CYCLE[ABSENT] == EXCUSED
    assert STATUS_CYCLE[EXCUSED] == PRESENT

def test_page_count():
    assert page_count(0) == 1
    assert page_count(15) == 1
    assert page_count(20) == 1
    assert page_count(21) == 2
    assert page_count(45) == 3

def test_admin_and_parent_menus():
    am = admin_menu()
    assert len(am.keyboard) == 3
    pm = parent_menu()
    assert len(pm.keyboard) == 1

def test_attendance_keyboard():
    students = [Student(id=i, full_name=f"Student {i}", student_code=f"COD{i:03d}") for i in range(1, 6)]
    today = date(2026, 9, 30)
    statuses = {1: PRESENT, 2: ABSENT}

    kb = attendance_keyboard(today, students, statuses, page=0)
    # 5 student rows + 1 save row = 6 rows
    assert len(kb.inline_keyboard) == 6
    assert kb.inline_keyboard[-1][0].text == "💾 Saqlash"
    assert kb.inline_keyboard[-1][0].callback_data == "att:s:20260930:0"

def test_student_card_and_delete_confirm_keyboards():
    card_kb = student_card_keyboard(student_id=42, page=1)
    # Tahrirlash, O'chirish, Ortga
    assert len(card_kb.inline_keyboard) == 3

    del_kb = delete_confirm_keyboard(student_id=42, page=1)
    # 1 qatorda 2 ta tugma: Tasdiqlash va Bekor qilish
    assert len(del_kb.inline_keyboard) == 1
    assert len(del_kb.inline_keyboard[0]) == 2
