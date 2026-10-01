from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_alloc_window_columns() -> None:
    """旧库补列（create_all 不会给已存在的表加列）；幂等，仅 Postgres 需要。"""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE market_days ADD COLUMN IF NOT EXISTS alloc_start TIME"))
        conn.execute(text("ALTER TABLE market_days ADD COLUMN IF NOT EXISTS alloc_end TIME"))
        conn.execute(text("UPDATE market_days SET alloc_start = TIME '00:00' WHERE alloc_start IS NULL"))
        conn.execute(text("UPDATE market_days SET alloc_end = TIME '23:59:59' WHERE alloc_end IS NULL"))
        conn.execute(text("ALTER TABLE market_days ALTER COLUMN alloc_start SET NOT NULL"))
        conn.execute(text("ALTER TABLE market_days ALTER COLUMN alloc_end SET NOT NULL"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_alloc_window_columns()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="StallSpan", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
