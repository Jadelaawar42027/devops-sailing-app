"""Forecast cache stored in this service's own database (brief §3a: one DB per service)."""

import json
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ForecastCacheEntry, utcnow

KEEP_ROWS_FOR = timedelta(days=7)


def cache_key(kind: str, lat: float, lon: float, days: int | None = None) -> str:
    key = f"{kind}:{lat:.2f}:{lon:.2f}"
    return f"{key}:{days}" if days else key


def get(session: Session, key: str) -> tuple[dict, float] | None:
    """Return (payload, age_seconds) or None."""
    entry = session.scalar(select(ForecastCacheEntry).where(ForecastCacheEntry.cache_key == key))
    if entry is None:
        return None
    age = (utcnow() - entry.fetched_at).total_seconds()
    return json.loads(entry.payload), age


def put(session: Session, key: str, payload: dict) -> None:
    now = utcnow()
    entry = session.scalar(select(ForecastCacheEntry).where(ForecastCacheEntry.cache_key == key))
    if entry is None:
        session.add(ForecastCacheEntry(cache_key=key, payload=json.dumps(payload), fetched_at=now))
    else:
        entry.payload = json.dumps(payload)
        entry.fetched_at = now
    session.execute(
        delete(ForecastCacheEntry).where(ForecastCacheEntry.fetched_at < now - KEEP_ROWS_FOR)
    )
    try:
        session.commit()
    except IntegrityError:  # a concurrent request stored the same key first: fine
        session.rollback()
