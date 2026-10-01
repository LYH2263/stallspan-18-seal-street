"""可分配时段窗判定 —— 集日页、确认入口、试摆入口、运行条数共用的唯一口径。

任何"现在能不能写"的判断都必须走这里的 is_within_alloc_window /
require_within_alloc_window，禁止各入口各自实现导致口径分叉。
判定每次调用都基于传入的 MarketDay 当前字段实时计算，不缓存旧窗结果。
"""
from __future__ import annotations

from datetime import datetime, time

from fastapi import HTTPException

from app.models.models import MarketDay


def is_within_alloc_window(day: MarketDay, now: datetime | None = None) -> bool:
    """当前时刻是否落在集日的可分配时段窗内。

    - start <= end：普通同日窗，如 08:00–12:00；
    - start > end：跨午夜窗，如 20:00–02:00（夜市）；
    - start == end：空窗，任何时刻都不可写。
    边界时刻（恰为 start 或 end）视为窗内。
    """
    now = now or datetime.now()
    t = now.time()
    start, end = day.alloc_start, day.alloc_end
    if start == end:
        return False
    if start < end:
        return start <= t <= end
    return t >= start or t <= end


def _fmt(t: time) -> str:
    return t.strftime("%H:%M")


def alloc_window_detail(day: MarketDay, now: datetime | None = None) -> str:
    """窗外拒写时的统一报文：必须点明不在可分配时段。"""
    now = now or datetime.now()
    return (
        f"不在可分配时段：「{day.name}」可分配时段为 "
        f"{_fmt(day.alloc_start)}–{_fmt(day.alloc_end)}，"
        f"当前时刻 {_fmt(now.time())}，确认与试摆仅在时段窗内开放"
    )


def require_within_alloc_window(day: MarketDay, now: datetime | None = None) -> None:
    """窗外即 403；确认与试摆入口共用此闸门，行数不会因窗外请求变化。"""
    now = now or datetime.now()
    if not is_within_alloc_window(day, now):
        raise HTTPException(status_code=403, detail=alloc_window_detail(day, now))
