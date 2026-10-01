from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AllocationRun, MarketDay, Segment
from app.services.alloc_window import is_within_alloc_window

router = APIRouter(prefix="/days", tags=["days"])


class AllocWindowIn(BaseModel):
    alloc_start: time
    alloc_end: time


def day_to_dict(db: Session, r: MarketDay, now: datetime | None = None) -> dict:
    """集日页展示与确认/试摆共用同一套窗内判定；run_count 为该集日全部街段的运行条数。"""
    run_count = db.scalar(
        select(func.count()).select_from(AllocationRun)
        .join(Segment, AllocationRun.segment_id == Segment.id)
        .where(Segment.market_day_id == r.id)
    ) or 0
    return {
        "id": r.id,
        "name": r.name,
        "day": r.day.isoformat(),
        "alloc_start": r.alloc_start.strftime("%H:%M"),
        "alloc_end": r.alloc_end.strftime("%H:%M"),
        "writable": is_within_alloc_window(r, now),
        "run_count": run_count,
    }


@router.get("")
def list_days(db: Session = Depends(get_db)):
    now = datetime.now()
    return [day_to_dict(db, r, now)
            for r in db.scalars(select(MarketDay).order_by(MarketDay.id)).all()]


@router.put("/{day_id}")
def update_alloc_window(day_id: int, body: AllocWindowIn, db: Session = Depends(get_db)):
    """改可分配时段；保存后所有入口立即按新窗判定（判定不缓存，实时读库）。"""
    day = db.get(MarketDay, day_id)
    if not day:
        raise HTTPException(404, "集日不存在")
    day.alloc_start = body.alloc_start
    day.alloc_end = body.alloc_end
    db.commit()
    db.refresh(day)
    return day_to_dict(db, day)
