"""GO / NO-GO scoring for departure windows (R3). Pure functions: no I/O, no clock.

A departure at hour H is GO when every forecast hour from H up to the first hour at or
after arrival is within the boat's limits at every sampled point (start and end of the
passage, worst value wins). Otherwise it is NO-GO, with the limit that failed and by how much.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import ceil

# TODO(team): decide the safety margin. 0.0 = NO-GO only when a value is strictly above the
# boat's limit (exactly at the limit is GO). 0.1 would turn NO-GO above 90% of each limit.
SAFETY_MARGIN = 0.0

VARIABLES = (
    # (key in HourConditions, key in Limits, label, unit, decimals)
    ("wind_kn", "max_wind_kn", "Wind", "kn", 1),
    ("gust_kn", "max_gust_kn", "Gusts", "kn", 1),
    ("wave_m", "max_wave_m", "Waves", "m", 2),
)


@dataclass(frozen=True)
class Limits:
    max_wind_kn: float
    max_wave_m: float
    max_gust_kn: float | None = None  # None = gusts not checked


@dataclass(frozen=True)
class HourConditions:
    time: datetime
    wind_kn: float | None
    gust_kn: float | None
    wave_m: float | None


@dataclass(frozen=True)
class Failure:
    limit: str  # "wind" | "gusts" | "waves" | "missing_data"
    observed: float | None
    limit_value: float | None
    exceeded_by: float | None
    at: datetime
    message: str


@dataclass(frozen=True)
class Window:
    departure: datetime
    arrival: datetime
    go: bool
    reason: str
    failures: list[Failure] = field(default_factory=list)
    peak: dict[str, float | None] = field(default_factory=dict)


def passage_duration_h(distance_nm: float, speed_kn: float) -> float:
    if speed_kn <= 0:
        raise ValueError("speed_kn must be positive")
    return distance_nm / speed_kn


def worst_of(*series: list[HourConditions]) -> list[HourConditions]:
    """Combine several points' hourly series: per hour, the highest value of each variable.

    Hours missing from any series are dropped. A value missing at one point is ignored if
    another point has it; it stays None only when no point has it.
    """
    if not series:
        return []
    by_time = [{h.time: h for h in s} for s in series]
    common = sorted(set(by_time[0]).intersection(*by_time[1:]))
    combined = []
    for t in common:
        hours = [m[t] for m in by_time]
        combined.append(
            HourConditions(
                time=t,
                wind_kn=_max(h.wind_kn for h in hours),
                gust_kn=_max(h.gust_kn for h in hours),
                wave_m=_max(h.wave_m for h in hours),
            )
        )
    return combined


def score_windows(
    limits: Limits,
    hours: list[HourConditions],
    duration_h: float,
    not_before: datetime | None = None,
) -> list[Window]:
    """One Window per hourly departure whose whole passage fits inside the forecast.

    not_before drops departures in the past (the caller passes "now"; this stays pure).
    """
    if duration_h < 0:
        raise ValueError("duration_h must not be negative")
    steps = ceil(duration_h)  # forecast hours after departure that the passage touches
    windows = []
    for i in range(len(hours) - steps):
        span = hours[i : i + steps + 1]
        departure = span[0].time
        if not_before is not None and departure < not_before:
            continue
        windows.append(_score(limits, span, departure, departure + timedelta(hours=duration_h)))
    return windows


def _score(
    limits: Limits, span: list[HourConditions], departure: datetime, arrival: datetime
) -> Window:
    failures: list[Failure] = []
    peak: dict[str, float | None] = {}
    for attr, limit_attr, label, unit, nd in VARIABLES:
        limit = getattr(limits, limit_attr)
        values = [(h.time, getattr(h, attr)) for h in span]
        known = [(t, v) for t, v in values if v is not None]
        peak[attr] = round(max(v for _, v in known), nd) if known else None
        if limit is None:
            continue
        missing = [t for t, v in values if v is None]
        if missing:
            failures.append(
                Failure(
                    "missing_data",
                    None,
                    limit,
                    None,
                    missing[0],
                    f"No {label.lower()} forecast at {_hhmm(missing[0])}",
                )
            )
            continue
        threshold = limit * (1 - SAFETY_MARGIN)
        t_worst, worst = max(known, key=lambda tv: tv[1])
        if worst > threshold:
            over = round(worst - threshold, nd)
            failures.append(
                Failure(
                    label.lower(),
                    round(worst, nd),
                    round(threshold, nd),
                    over,
                    t_worst,
                    f"{label} {worst:.{nd}f} {unit} exceeds limit {threshold:.{nd}f} {unit} "
                    f"by {over:.{nd}f} {unit} at {_hhmm(t_worst)}",
                )
            )
    failures.sort(key=_severity, reverse=True)
    if failures:
        reason = "; ".join(f.message for f in failures)
    else:
        reason = "Within limits: " + ", ".join(
            f"max {label.lower()} {peak[attr]:.{nd}f}/{getattr(limits, lim):.{nd}f} {unit}"
            for attr, lim, label, unit, nd in VARIABLES
            if getattr(limits, lim) is not None and peak[attr] is not None
        )
    return Window(departure, arrival, not failures, reason, failures, peak)


def _severity(f: Failure) -> float:
    """Missing data first, then the largest exceedance relative to its limit."""
    if f.exceeded_by is None or not f.limit_value:
        return float("inf")
    return f.exceeded_by / f.limit_value


def _max(values) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _hhmm(t: datetime) -> str:
    return t.strftime("%a %d %b %H:%MZ")
