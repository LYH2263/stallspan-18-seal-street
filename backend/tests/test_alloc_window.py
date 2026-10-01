"""可分配时段窗：窗外拒写、改窗即生效、运行条数精确、latest 只读。"""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import MarketDay, Segment, Vendor
from app.services.alloc_window import is_within_alloc_window
from app.services.seed import seed_if_empty

engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)  # 不进 lifespan，避免连真实 Postgres


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _window_excluding_now():
    """明显不含现在的窗：当前时刻 3–4 小时之后。"""
    now = datetime.now()
    return ((now + timedelta(hours=3)).time().replace(microsecond=0),
            (now + timedelta(hours=4)).time().replace(microsecond=0))


def _window_covering_now():
    """必含现在的窗：前后各让一小时（跨午夜由判定自身处理）。"""
    now = datetime.now()
    return ((now - timedelta(hours=1)).time().replace(microsecond=0),
            (now + timedelta(hours=1)).time().replace(microsecond=0))


def _seed_day(alloc_start, alloc_end, with_vendor=True):
    db = TestingSessionLocal()
    day = MarketDay(name="周末夜市", day=date(2026, 9, 20),
                    alloc_start=alloc_start, alloc_end=alloc_end)
    db.add(day)
    db.flush()
    seg = Segment(market_day_id=day.id, name="东街段", width_m=30.0)
    db.add(seg)
    db.flush()
    if with_vendor:
        db.add(Vendor(market_day_id=day.id, name="阿强烧烤", stall_width_m=4.0, priority=1))
    db.commit()
    ids = (day.id, seg.id)
    db.close()
    return ids


def _put_window(day_id, start, end):
    return client.put(f"/api/days/{day_id}", json={
        "alloc_start": start.strftime("%H:%M"),
        "alloc_end": end.strftime("%H:%M"),
    })


def _run_count(day_id):
    days = client.get("/api/days").json()
    return next(d["run_count"] for d in days if d["id"] == day_id)


# ---------- 纯判定：同一套窗内可写口径 ----------

def test_window_plain_range_and_boundaries():
    day = MarketDay(name="d", day=date(2026, 9, 20),
                    alloc_start=time(8, 0), alloc_end=time(12, 0))
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 10, 0)) is True
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 8, 0)) is True   # 边界含
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 12, 0)) is True  # 边界含
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 7, 59)) is False
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 12, 1)) is False


def test_window_cross_midnight():
    day = MarketDay(name="d", day=date(2026, 9, 20),
                    alloc_start=time(20, 0), alloc_end=time(2, 0))
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 23, 0)) is True
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 1, 0)) is True
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 12, 0)) is False


def test_window_empty_when_start_equals_end():
    day = MarketDay(name="d", day=date(2026, 9, 20),
                    alloc_start=time(9, 0), alloc_end=time(9, 0))
    assert is_within_alloc_window(day, datetime(2026, 10, 1, 9, 0)) is False


# ---------- 种子：窗明显不含现在 → 确认与试摆皆拒 ----------

def test_seed_window_excludes_now_and_blocks_confirm_and_preview():
    db = TestingSessionLocal()
    seed_if_empty(db)
    day = db.scalars(select(MarketDay)).one()
    seg_id = db.scalars(select(Segment.id)).one()
    assert day.name == "周末夜市"
    assert is_within_alloc_window(day, datetime.now()) is False
    db.close()

    for path in ("/api/allocate/run", "/api/allocate/preview"):
        r = client.post(path, params={"segment_id": seg_id})
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert "不在可分配时段" in detail
        assert "没有摊主" not in detail and "空档" not in detail

    day_view = client.get("/api/days").json()[0]
    assert day_view["writable"] is False
    assert day_view["run_count"] == 0  # 窗外请求不得增行


# ---------- 窗外：确认/试摆 403 且行数不变，latest 只读可开 ----------

def test_outside_window_blocks_writes_and_keeps_rows_unchanged():
    day_id, seg_id = _seed_day(*_window_excluding_now())
    for path in ("/api/allocate/run", "/api/allocate/preview"):
        r = client.post(path, params={"segment_id": seg_id})
        assert r.status_code == 403
        assert "不在可分配时段" in r.json()["detail"]
    assert _run_count(day_id) == 0


def test_outside_window_error_names_window_even_without_vendors():
    _, seg_id = _seed_day(*_window_excluding_now(), with_vendor=False)
    r = client.post("/api/allocate/run", params={"segment_id": seg_id})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert "不在可分配时段" in detail
    assert "没有摊主" not in detail and "空档不足" not in detail


def test_outside_window_latest_is_readonly_and_never_creates():
    start, end = _window_covering_now()
    day_id, seg_id = _seed_day(start, end)
    r = client.post("/api/allocate/run", params={"segment_id": seg_id})
    assert r.status_code == 200
    run_id = r.json()["id"]
    assert _run_count(day_id) == 1

    _put_window(day_id, *_window_excluding_now()).raise_for_status()
    r = client.get("/api/allocate/latest", params={"segment_id": seg_id})
    assert r.status_code == 200          # 旧运行只读可开
    assert r.json()["id"] == run_id
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 403
    assert client.get("/api/allocate/latest", params={"segment_id": seg_id}).json()["id"] == run_id
    assert _run_count(day_id) == 1       # 不新增、不改写


def test_latest_404_when_no_run_and_creates_nothing():
    day_id, seg_id = _seed_day(*_window_covering_now())
    r = client.get("/api/allocate/latest", params={"segment_id": seg_id})
    assert r.status_code == 404
    assert _run_count(day_id) == 0


# ---------- 改窗即生效：恢复可写后确认一次行数才加一 ----------

def test_window_change_takes_effect_immediately_and_count_is_exact():
    day_id, seg_id = _seed_day(*_window_excluding_now())
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 403

    r = _put_window(day_id, *_window_covering_now())
    assert r.status_code == 200
    assert r.json()["writable"] is True  # 判定按刚改的窗，不沿用旧窗结果

    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 200
    assert _run_count(day_id) == 1       # 确认一次只加一
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 200
    assert _run_count(day_id) == 2

    _put_window(day_id, *_window_excluding_now()).raise_for_status()
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 403
    assert client.post("/api/allocate/preview", params={"segment_id": seg_id}).status_code == 403
    assert _run_count(day_id) == 2


def test_preview_never_persists_even_inside_window():
    day_id, seg_id = _seed_day(*_window_covering_now())
    r = client.post("/api/allocate/preview", params={"segment_id": seg_id})
    assert r.status_code == 200
    assert r.json()["preview"] is True
    assert r.json()["placements"]
    assert _run_count(day_id) == 0       # 试摆不落库


def test_days_writable_flag_matches_confirm_gate():
    day_id, seg_id = _seed_day(*_window_excluding_now())
    view = client.get("/api/days").json()[0]
    assert view["writable"] is False
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 403
    _put_window(day_id, *_window_covering_now())
    view = client.get("/api/days").json()[0]
    assert view["writable"] is True
    assert client.post("/api/allocate/run", params={"segment_id": seg_id}).status_code == 200
