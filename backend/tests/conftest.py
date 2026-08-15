"""
Test configuration.

The app's global SQLAlchemy engine (app.core.database.engine) pools
connections, and pooled asyncpg connections are bound to the event loop
that created them. pytest-asyncio gives each test function its own
event loop, so a pooled connection opened during test A becomes unusable
during test B ("attached to a different loop").

Fix: for the test session only, swap the engine's pool for a NullPool,
which opens a fresh connection per checkout and closes it right after —
nothing outlives a single test's event loop. Production code is
untouched; this file only runs under pytest.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.database as db_module
from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def _use_nullpool_engine():
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        poolclass=NullPool,
        future=True,
    )
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=db_module.AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    original_engine = db_module.engine
    original_session_factory = db_module.AsyncSessionLocal

    db_module.engine = test_engine
    db_module.AsyncSessionLocal = test_session_factory

    yield

    db_module.engine = original_engine
    db_module.AsyncSessionLocal = original_session_factory
