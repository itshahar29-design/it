from datetime import date
import pytest
from app.reports import weekly_period, monthly_period, _child_block
from app.config import _bool, _int, _admin_ids
from app.texts import esc, fmt_date

def test_weekly_period():
    # 2026-10-03 - Shanba (Saturday)
    saturday = date(2026, 10, 3)
    start, end, key = weekly_period(saturday)
    # Shanba uchun dushanba 2026-09-28 bo'lishi kerak
    assert start == date(2026, 9, 28)
    assert end == saturday
    assert key == "2026-10-03"

def test_monthly_period():
    # 2026-09-30 - Sentyabrning oxirgi kuni
    last_day = date(2026, 9, 30)
    start, end, key = monthly_period(last_day)
    assert start == date(2026, 9, 1)
    assert end == last_day
    assert key == "2026-09"

def test_child_block():
    block = _child_block("Ali Valiyev", 10, 1, 1, 83.33)
    assert "Ali Valiyev" in block
    assert "10" in block
    assert "83.3%" in block

def test_config_parsers():
    # _bool
    assert _bool("true", False) is True
    assert _bool("1", False) is True
    assert _bool("yes", False) is True
    assert _bool("ha", False) is True
    assert _bool("false", True) is False
    assert _bool("0", True) is False
    assert _bool(None, True) is True

    # _int
    assert _int("18", 10, 0, 23) == 18
    assert _int(None, 10, 0, 23) == 10
    with pytest.raises(RuntimeError):
        _int("25", 10, 0, 23)

    # _admin_ids
    assert _admin_ids("123, 456; 789") == frozenset({123, 456, 789})
    assert _admin_ids("") == frozenset()
    with pytest.raises(RuntimeError):
        _admin_ids("123, abc")

def test_esc_and_fmt_date():
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert fmt_date(date(2026, 9, 30)) == "30.09.2026"
