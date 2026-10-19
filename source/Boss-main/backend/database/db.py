"""Database connection and session management."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "boss_recruiter.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist."""
    from database.models import (  # noqa: F401 – ensure models are registered
        Position,
        RecruitTask,
        Candidate,
        Resume,
        ChatMessage,
        ContactInfo,
        BossAccount,
        MarketCompany,
        MarketCompanySnapshot,
    )
    Base.metadata.create_all(bind=engine)
    migrate_browser_accounts(engine)


def get_db() -> Session:  # type: ignore[misc]
    """Dependency-injection helper for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


def migrate_browser_accounts(db_engine):
    """Add connection fields without discarding existing data; back up first."""
    from sqlalchemy import inspect, text
    import sqlite3
    from datetime import datetime
    columns = {c['name'] for c in inspect(db_engine).get_columns('boss_accounts')}
    additions = {'connection_type': "VARCHAR(20) DEFAULT 'managed'",
                 'cdp_url': "VARCHAR(200) DEFAULT ''",
                 'target_id': "VARCHAR(200) DEFAULT ''",
                 'last_error': "TEXT DEFAULT ''"}
    missing = {k: v for k, v in additions.items() if k not in columns}
    if missing and db_engine.url.database and db_engine.url.database != ':memory:':
        source = Path(db_engine.url.database)
        backup = source.with_suffix('.before-chrome-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.db')
        with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    with db_engine.begin() as conn:
        for name, declaration in missing.items():
            conn.execute(text(f'ALTER TABLE boss_accounts ADD COLUMN {name} {declaration}'))
