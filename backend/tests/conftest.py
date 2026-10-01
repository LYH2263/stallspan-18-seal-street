import os
from datetime import time

# 必须在导入 app.* 之前：让模块级 engine 走 SQLite，避免依赖 Postgres/psycopg2。
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_stallspan.db")
os.environ.setdefault("SEED_ON_EMPTY", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import window


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    # 每个用例从墙钟 10:00 起步，避免系统时间漂移。
    window.set_now(time(10, 0))
    yield TestClient(app)
    app.dependency_overrides.clear()
    window.set_now(None)
