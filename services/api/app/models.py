"""ORM models. The schema itself is owned by the migrations in migrations/versions."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Boat(Base):
    __tablename__ = "boats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    max_wind_kn: Mapped[float] = mapped_column(Float)
    max_gust_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_wave_m: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Passage(Base):
    __tablename__ = "passages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boats.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    start_lat: Mapped[float] = mapped_column(Float)
    start_lon: Mapped[float] = mapped_column(Float)
    end_lat: Mapped[float] = mapped_column(Float)
    end_lon: Mapped[float] = mapped_column(Float)
    speed_kn: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
