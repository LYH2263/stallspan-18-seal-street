import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AllocationRun, MarketDay, Pillar, Segment, Vendor
from app.services import window
from app.services.first_fit_engine import allocate_first_fit, result_to_dict

router = APIRouter(prefix="/allocate", tags=["allocate"])


def get_segment_day(segment_id: int, db: Session) -> tuple[Segment, MarketDay]:
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    day = db.get(MarketDay, seg.market_day_id)
    if not day:
        raise HTTPException(404, "集日不存在")
    return seg, day


def assert_writable(day: MarketDay) -> None:
    """确认与试摆共用的唯一闸门。窗外一律 403，信息点明不在可分配时段，
    不得伪装成没有摊主或空档不足。"""
    if not window.in_window(day.window_start, day.window_end):
        raise HTTPException(403, window.window_message(day))


def compute_result(seg: Segment, db: Session) -> dict:
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == seg.id)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    return result


def status_payload(day: MarketDay, seg: Segment, db: Session) -> dict:
    return {
        "segment_id": seg.id,
        "day_id": day.id,
        "day_name": day.name,
        "window_start": day.window_start.strftime("%H:%M"),
        "window_end": day.window_end.strftime("%H:%M"),
        "server_now": window.now().strftime("%H:%M"),
        "writable": window.in_window(day.window_start, day.window_end),
        "run_count": db.scalar(
            select(func.count()).select_from(AllocationRun)
            .where(AllocationRun.segment_id == seg.id)
        ) or 0,
    }


@router.post("/trial")
def trial_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    """试摆：窗内可算，但绝不落库、不改行数。"""
    seg, day = get_segment_day(segment_id, db)
    assert_writable(day)
    before = db.scalar(select(func.count()).select_from(AllocationRun)) or 0
    result = compute_result(seg, db)
    after = db.scalar(select(func.count()).select_from(AllocationRun)) or 0
    assert after == before, "试摆不得新增运行"
    return {"trial": True, **status_payload(day, seg, db), **result}


@router.post("/run")
def run_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    """确认：窗内才允许新增一条运行。"""
    seg, day = get_segment_day(segment_id, db)
    assert_writable(day)
    result = compute_result(seg, db)
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps(result, ensure_ascii=False))
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, "trial": False, **status_payload(day, seg, db), **result}


@router.get("/status")
def get_status(segment_id: int = 1, db: Session = Depends(get_db)):
    seg, day = get_segment_day(segment_id, db)
    return status_payload(day, seg, db)


def _run_to_dict(run: AllocationRun) -> dict:
    return {"id": run.id, "segment_id": run.segment_id,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            **json.loads(run.result_json)}


@router.get("/runs")
def list_runs(segment_id: int = 1, db: Session = Depends(get_db)):
    """旧运行只读可开：列出该街段全部运行，不做任何写入。"""
    seg, _day = get_segment_day(segment_id, db)
    rows = db.scalars(
        select(AllocationRun).where(AllocationRun.segment_id == seg.id)
        .order_by(AllocationRun.id.desc())
    ).all()
    return [{"id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AllocationRun, run_id)
    if not run:
        raise HTTPException(404, "运行不存在")
    return _run_to_dict(run)


@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    """只读：返回最近一条运行；从未运行过时返回空壳，绝不替用户新建运行。"""
    seg, day = get_segment_day(segment_id, db)
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if not run:
        return {"id": None, **status_payload(day, seg, db),
                "placements": [], "rejected": [], "free_spans": [],
                "segment": {"id": seg.id, "name": seg.name, "width_m": seg.width_m},
                "pillars": [{"position_m": p.position_m, "thickness_m": p.thickness_m}
                            for p in db.scalars(select(Pillar).where(Pillar.segment_id == segment_id)).all()]}
    return {"id": run.id, **status_payload(day, seg, db), **json.loads(run.result_json)}
