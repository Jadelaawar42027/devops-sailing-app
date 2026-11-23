"""Cache-first forecast lookups with graceful degradation.

fresh cache -> serve it ("hit")
otherwise   -> call Open-Meteo and store it ("miss")
upstream down -> serve the last cached copy, marked stale ("stale")
upstream down and nothing cached -> ForecastUnavailable (HTTP 503 with a clear message)
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app import cache
from app.openmeteo import UpstreamError

log = logging.getLogger(__name__)


class ForecastUnavailable(Exception):
    pass


def cached_fetch(
    session: Session, key: str, ttl_s: int, fetch: Callable[[], dict | list]
) -> tuple[dict | list, str, float]:
    """Return (data, cache_status, age_seconds)."""
    hit = cache.get(session, key)
    if hit and hit[1] <= ttl_s:
        return hit[0]["data"], "hit", hit[1]
    try:
        data = fetch()
    except UpstreamError as exc:
        if hit:
            log.warning("serving stale forecast", extra={"fields": {"reason": str(exc)}})
            return hit[0]["data"], "stale", hit[1]
        raise ForecastUnavailable(f"{exc}; no cached data for this location") from exc
    cache.put(session, key, {"data": data})
    return data, "miss", 0.0
