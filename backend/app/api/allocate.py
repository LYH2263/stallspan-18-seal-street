import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AllocationRun, MarketDay, Pillar, Segment, Vendor
from app.services.alloc_window import require_within_alloc_window
from app.services.first_fit_engine import allocate_first_fit, result_to_dict

router = APIRouter(prefix="/allocate", tags=["allocate"])


def _load_segment(db: Session, segment_id: int) -> Segment:
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    return seg


def _compute_allocation(db: Session, seg: Segment) -> dict:
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == seg.id)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    return result


def _gate_writable(db: Session, seg: Segment) -> None:
    """确认与试摆共用同一道窗闸；窗外一律 403 且报文点明不在可分配时段。"""
    day = db.get(MarketDay, seg.market_day_id)
    if not day:
        raise HTTPException(404, "集日不存在")
    require_within_alloc_window(day)


@router.post("/run")
def run_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    """确认分配：窗内才落库，每次确认运行条数 +1；窗外 403、行数不变。"""
    seg = _load_segment(db, segment_id)
    _gate_writable(db, seg)
    result = _compute_allocation(db, seg)
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps(result, ensure_ascii=False))
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, **result}


@router.post("/preview")
def preview_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    """试摆：与确认同一道窗闸，只演算不落库，运行条数不变。"""
    seg = _load_segment(db, segment_id)
    _gate_writable(db, seg)
    return {"id": None, "preview": True, **_compute_allocation(db, seg)}


@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    """只读取最近运行：窗外也可看旧色块，但任何时刻都不新增、不改写运行。"""
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if not run:
        raise HTTPException(404, "暂无运行记录")
    data = json.loads(run.result_json)
    return {"id": run.id, **data}
