from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import MarketDay
from app.services import window

router = APIRouter(prefix="/days", tags=["days"])


def parse_clock(value: str | time) -> time:
    """接受 HH:MM 或 HH:MM:SS 的墙钟。"""
    if isinstance(value, time):
        return value
    try:
        parts = [int(x) for x in value.split(":")]
        if len(parts) == 2:
            return time(parts[0], parts[1])
        if len(parts) == 3:
            return time(parts[0], parts[1], parts[2])
    except (ValueError, AttributeError):
        pass
    raise HTTPException(422, f"时钟格式应为 HH:MM，收到：{value!r}")


def day_to_dict(r: MarketDay) -> dict:
    """集日的唯一出参形状：时段与 writable 都在这里按当前窗算出。"""
    return {
        "id": r.id,
        "name": r.name,
        "day": r.day.isoformat(),
        "window_start": r.window_start.strftime("%H:%M"),
        "window_end": r.window_end.strftime("%H:%M"),
        "server_now": window.now().strftime("%H:%M"),
        "writable": window.in_window(r.window_start, r.window_end),
    }


class DayPatch(BaseModel):
    name: str | None = None
    day: date | None = None
    window_start: str | None = None
    window_end: str | None = None


@router.get("")
def list_days(db: Session = Depends(get_db)):
    return [day_to_dict(r)
            for r in db.scalars(select(MarketDay).order_by(MarketDay.id)).all()]


@router.patch("/{day_id}")
def update_day(day_id: int, body: DayPatch, db: Session = Depends(get_db)):
    day_row = db.get(MarketDay, day_id)
    if not day_row:
        raise HTTPException(404, "集日不存在")
    if body.name is not None:
        day_row.name = body.name
    if body.day is not None:
        day_row.day = body.day
    new_start = parse_clock(body.window_start) if body.window_start is not None else None
    new_end = parse_clock(body.window_end) if body.window_end is not None else None
    if new_start is not None:
        day_row.window_start = new_start
    if new_end is not None:
        day_row.window_end = new_end
    # 改时段后必须按刚改的窗判定，不缓存旧窗结果 —— commit 后重新取算。
    db.commit()
    db.refresh(day_row)
    return day_to_dict(day_row)
