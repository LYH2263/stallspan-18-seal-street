from datetime import time

from app.services import window


def test_inside_regular_window():
    assert window.in_window(time(9, 0), time(12, 0), time(10, 30))


def test_outside_regular_window():
    assert not window.in_window(time(9, 0), time(12, 0), time(15, 0))


def test_start_inclusive_end_exclusive():
    assert window.in_window(time(9, 0), time(12, 0), time(9, 0))
    assert not window.in_window(time(9, 0), time(12, 0), time(12, 0))


def test_overnight_window():
    # 20:00–02:00 跨零点
    assert window.in_window(time(20, 0), time(2, 0), time(23, 30))
    assert window.in_window(time(20, 0), time(2, 0), time(1, 0))
    assert not window.in_window(time(20, 0), time(2, 0), time(12, 0))


def test_equal_endpoints_is_closed():
    assert not window.in_window(time(0, 0), time(0, 0), time(0, 0))
