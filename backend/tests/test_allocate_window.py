from datetime import date, time

from app.models.models import AllocationRun, MarketDay, Pillar, Segment, Vendor
from app.services import window


def _make_market(db, start=time(3, 0), end=time(4, 0)):
    day = MarketDay(name="周末夜市", day=date(2026, 9, 20),
                    window_start=start, window_end=end)
    db.add(day)
    db.flush()
    seg = Segment(market_day_id=day.id, name="东街段", width_m=30.0)
    db.add(seg)
    db.flush()
    db.add(Pillar(segment_id=seg.id, position_m=10.0, thickness_m=0.5, label="灯柱A"))
    db.add(Pillar(segment_id=seg.id, position_m=20.0, thickness_m=0.5, label="灯柱B"))
    for name, wdt, pri in [("阿强烧烤", 4.0, 1), ("林记糖水", 3.0, 1), ("巨型舞台车", 12.0, 9)]:
        db.add(Vendor(market_day_id=day.id, name=name, stall_width_m=wdt, priority=pri))
    db.commit()
    return day, seg


def _run_count(db, seg_id):
    return db.query(AllocationRun).filter(AllocationRun.segment_id == seg_id).count()


def test_days_report_window_status(client, db_session):
    day, seg = _make_market(db_session)  # 03:00–04:00，现在 10:00 → 窗外
    rows = client.get("/api/days").json()
    assert rows[0]["writable"] is False
    assert rows[0]["window_start"] == "03:00"
    assert rows[0]["window_end"] == "04:00"
    assert rows[0]["server_now"] == "10:00"


def test_outside_window_blocks_confirm_and_trial_with_actual_reason(client, db_session):
    day, seg = _make_market(db_session)

    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert "可分配时段" in detail
    # 不得伪装成没有摊主或空档不足
    assert "摊主" not in detail and "空档" not in detail
    assert _run_count(db_session, seg.id) == 0

    r = client.post(f"/api/allocate/trial?segment_id={seg.id}")
    assert r.status_code == 403
    assert "可分配时段" in r.json()["detail"]
    assert _run_count(db_session, seg.id) == 0


def test_outside_window_every_segment_of_day_blocked(client, db_session):
    day, seg1 = _make_market(db_session)
    seg2 = Segment(market_day_id=day.id, name="西街段", width_m=20.0)
    db_session.add(seg2)
    db_session.commit()
    for seg in (seg1, seg2):
        assert client.post(f"/api/allocate/run?segment_id={seg.id}").status_code == 403
        assert client.post(f"/api/allocate/trial?segment_id={seg.id}").status_code == 403
        assert _run_count(db_session, seg.id) == 0


def test_latest_is_readonly_and_creates_no_run(client, db_session):
    day, seg = _make_market(db_session)
    r = client.get(f"/api/allocate/latest?segment_id={seg.id}")
    assert r.status_code == 200
    assert r.json()["id"] is None
    assert r.json()["run_count"] == 0
    assert _run_count(db_session, seg.id) == 0


def test_patch_window_takes_effect_immediately(client, db_session):
    day, seg = _make_market(db_session)  # 窗外
    r = client.patch(f"/api/days/{day.id}",
                     json={"window_start": "09:00", "window_end": "11:00"})
    assert r.status_code == 200
    body = r.json()
    # 改时段后必须按刚改的窗判定，不沿用旧窗结果
    assert body["window_start"] == "09:00"
    assert body["writable"] is True

    # 同一套口径：试摆窗内可算但不落库
    r = client.post(f"/api/allocate/trial?segment_id={seg.id}")
    assert r.status_code == 200
    assert r.json()["trial"] is True
    assert len(r.json()["placements"]) >= 1
    assert r.json()["run_count"] == 0
    assert _run_count(db_session, seg.id) == 0

    # 恢复可写后，确认一次行数才加一（且只加一）
    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    assert r.status_code == 200
    run_id = r.json()["id"]
    assert r.json()["run_count"] == 1
    assert _run_count(db_session, seg.id) == 1

    # 再次确认才加第二条
    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    assert r.json()["run_count"] == 2
    assert _run_count(db_session, seg.id) == 2
    assert run_id  # 第一条运行确实落库


def test_close_window_again_reblocks_without_touching_old_runs(client, db_session):
    day, seg = _make_market(db_session)
    client.patch(f"/api/days/{day.id}",
                 json={"window_start": "09:00", "window_end": "11:00"})
    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    old_id = r.json()["id"]
    assert _run_count(db_session, seg.id) == 1

    # 时钟走到窗外
    window.set_now(time(15, 0))

    # 确认/试摆再被拦，行数不变
    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    assert r.status_code == 403
    assert _run_count(db_session, seg.id) == 1
    assert client.post(f"/api/allocate/trial?segment_id={seg.id}").status_code == 403
    assert _run_count(db_session, seg.id) == 1

    # 旧运行只读可开、主图可看旧色块
    latest = client.get(f"/api/allocate/latest?segment_id={seg.id}").json()
    assert latest["id"] == old_id
    assert latest["writable"] is False
    assert len(latest["placements"]) >= 1

    runs = client.get(f"/api/allocate/runs?segment_id={seg.id}").json()
    assert [x["id"] for x in runs] == [old_id]
    one = client.get(f"/api/allocate/runs/{old_id}").json()
    assert one["id"] == old_id
    assert one["segment"]["name"] == "东街段"


def test_backend_blocks_even_if_frontend_would_allow(client, db_session):
    # 服务端始终重算窗状态：即便调用方照旧直发确认，窗外也无半成功（库不增行）
    day, seg = _make_market(db_session)
    status = client.get(f"/api/allocate/status?segment_id={seg.id}").json()
    assert status["writable"] is False
    r = client.post(f"/api/allocate/run?segment_id={seg.id}")
    assert r.status_code == 403
    assert client.get(f"/api/allocate/status?segment_id={seg.id}").json()["run_count"] == 0
