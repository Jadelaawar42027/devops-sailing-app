"""Fixture tests for the pure scoring function (R3), including edge cases."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app import scoring
from app.forecast_client import _hour
from app.geo import distance_nm
from app.scoring import HourConditions, Limits, passage_duration_h, score_windows, worst_of

T0 = datetime(2026, 11, 23, tzinfo=UTC)
LIMITS = Limits(max_wind_kn=20, max_wave_m=2.0, max_gust_kn=28)
FIXTURES = Path(__file__).parent / "fixtures"


def series(wind, wave=None, gust=None, start=T0):
    n = len(wind)
    wave = wave if wave is not None else [1.0] * n
    gust = gust if gust is not None else [w * 1.2 if w is not None else None for w in wind]
    return [HourConditions(start + timedelta(hours=i), wind[i], gust[i], wave[i]) for i in range(n)]


@pytest.fixture(autouse=True)
def no_margin(monkeypatch):
    monkeypatch.setattr(scoring, "SAFETY_MARGIN", 0.0)


def test_calm_forecast_is_all_go():
    windows = score_windows(LIMITS, series([10] * 6), duration_h=2)
    assert len(windows) == 4  # departures 0..3; departure 4 would arrive after the forecast
    assert all(w.go for w in windows)
    assert windows[0].reason.startswith("Within limits: max wind 10.0/20.0 kn")
    assert windows[0].failures == []


def test_exactly_at_limit_is_go():
    windows = score_windows(LIMITS, series([20, 20], wave=[2.0, 2.0], gust=[28, 28]), 1)
    assert windows[0].go


def test_just_above_limit_is_no_go_with_amount():
    (window,) = score_windows(LIMITS, series([20.1, 15]), duration_h=1)
    assert not window.go
    (failure,) = window.failures
    assert failure.limit == "wind"
    assert failure.observed == 20.1
    assert failure.limit_value == 20
    assert failure.exceeded_by == 0.1
    assert failure.at == T0
    assert window.reason == "Wind 20.1 kn exceeds limit 20.0 kn by 0.1 kn at Mon 23 Nov 00:00Z"


def test_spike_only_blocks_departures_whose_passage_overlaps_it():
    wind = [10, 10, 10, 10, 10, 25, 10, 10, 10, 10]
    windows = score_windows(LIMITS, series(wind), duration_h=2)
    verdicts = [w.go for w in windows]
    # Departure at hour h covers hours h..h+2, so hours 3, 4 and 5 see the spike.
    assert verdicts == [True, True, True, False, False, False, True, True]


def test_reports_every_failed_limit_worst_first():
    (window,) = score_windows(LIMITS, series([22], wave=[3.0], gust=[29]), duration_h=0)
    assert [f.limit for f in window.failures] == ["waves", "wind", "gusts"]
    assert window.reason.startswith("Waves 3.00 m exceeds limit 2.00 m by 1.00 m")


def test_missing_data_is_no_go_and_listed_first():
    (window,) = score_windows(LIMITS, series([25], wave=[None]), duration_h=0)
    assert not window.go
    assert window.failures[0].limit == "missing_data"
    assert window.failures[0].message.startswith("No waves forecast at")


def test_gusts_ignored_when_boat_has_no_gust_limit():
    limits = Limits(max_wind_kn=20, max_wave_m=2.0, max_gust_kn=None)
    (window,) = score_windows(limits, series([15], gust=[45]), duration_h=0)
    assert window.go
    assert window.peak["gust_kn"] == 45


def test_passage_longer_than_forecast_has_no_windows():
    assert score_windows(LIMITS, series([10] * 5), duration_h=5) == []


def test_zero_length_passage_scores_each_hour():
    windows = score_windows(LIMITS, series([10, 30, 10]), duration_h=0)
    assert [w.go for w in windows] == [True, False, True]
    assert windows[0].arrival == windows[0].departure


def test_fractional_duration_includes_first_hour_after_arrival():
    windows = score_windows(LIMITS, series([10, 10, 30, 10]), duration_h=1.5)
    assert [w.go for w in windows] == [False, False]
    assert windows[0].arrival == T0 + timedelta(hours=1.5)


def test_departures_before_not_before_are_dropped():
    windows = score_windows(LIMITS, series([10] * 6), 1, not_before=T0 + timedelta(hours=3))
    assert [w.departure for w in windows] == [T0 + timedelta(hours=h) for h in (3, 4)]


def test_safety_margin_lowers_the_threshold(monkeypatch):
    monkeypatch.setattr(scoring, "SAFETY_MARGIN", 0.1)
    (window,) = score_windows(LIMITS, series([19], gust=[20]), duration_h=0)
    assert not window.go  # 19 kn > 90% of 20 kn
    assert window.failures[0].limit_value == 18.0


def test_invalid_inputs():
    with pytest.raises(ValueError):
        score_windows(LIMITS, series([10]), duration_h=-1)
    with pytest.raises(ValueError):
        passage_duration_h(10, 0)


def test_worst_of_takes_highest_value_per_hour():
    a = series([10, 12], wave=[None, 1.0])
    b = series([15, 11], wave=[1.5, None])
    combined = worst_of(a, b)
    assert [h.wind_kn for h in combined] == [15, 12]
    assert [h.wave_m for h in combined] == [1.5, 1.0]


def test_worst_of_keeps_only_common_hours():
    a = series([10, 10, 10])
    b = series([10, 10], start=T0 + timedelta(hours=1))
    assert [h.time for h in worst_of(a, b)] == [T0 + timedelta(hours=1), T0 + timedelta(hours=2)]
    assert worst_of() == []


def test_front_passing_fixture():
    raw = json.loads((FIXTURES / "forecast_front_passing.json").read_text())
    hours = [_hour(h) for h in raw["hours"]]
    windows = score_windows(LIMITS, hours, duration_h=4)
    assert len(windows) == 20
    go_hours = [w.departure.hour for w in windows if w.go]
    # 04:00 covers 04:00-08:00 and peaks at exactly 20 kn / 28 kn gusts: GO (at the limit).
    # 14:00 is NO-GO on waves (2.4 m at 14:00); from 15:00 everything is back within limits.
    assert go_hours == [0, 1, 2, 3, 4, 15, 16, 17, 18, 19]
    late = next(w for w in windows if w.departure.hour == 14)
    assert [f.limit for f in late.failures] == ["waves"]
    blocked = next(w for w in windows if w.departure.hour == 9)
    assert blocked.failures[0].limit == "waves"
    assert "3.10 m exceeds limit 2.00 m by 1.10 m" in blocked.reason


def test_distance_and_duration():
    assert distance_nm(0, 0, 1, 0) == pytest.approx(60.04, abs=0.05)
    bcn_pmi = distance_nm(41.38, 2.18, 39.57, 2.65)
    assert 108 < bcn_pmi < 113
    assert passage_duration_h(bcn_pmi, 6) == pytest.approx(bcn_pmi / 6)
    assert distance_nm(41.38, 2.18, 41.38, 2.18) == 0
