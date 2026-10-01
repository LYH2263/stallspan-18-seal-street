from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_schema() -> None:
    """create_all 建新表；既有 Postgres 卷上补齐后加列（幂等）。"""
    Base.metadata.create_all(bind=engine)
    # MarketDay 可分配时段为后增字段，老库需显式补列。
    # ADD COLUMN IF NOT EXISTS 为 Postgres 语法；SQLite 等的全新库
    # 已由 create_all 带上新列，无需补列。
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE market_days ADD COLUMN IF NOT EXISTS "
            "window_start TIME NOT NULL DEFAULT '00:00'"
        ))
        conn.execute(text(
            "ALTER TABLE market_days ADD COLUMN IF NOT EXISTS "
            "window_end TIME NOT NULL DEFAULT '23:59:59'"
        ))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
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
