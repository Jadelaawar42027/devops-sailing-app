"""ORM models. The schema itself is owned by the migrations in migrations/versions."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, UnicodeText
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ForecastCacheEntry(Base):
    """One cached upstream answer per (kind, rounded lat, rounded lon, days)."""

    __tablename__ = "forecast_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(100), unique=True)
    payload: Mapped[str] = mapped_column(UnicodeText)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
