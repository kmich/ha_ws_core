"""Per-sample state advances only on the 60 s tick, not on every recompute."""

from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ws_core import coordinator as cmod
from custom_components.ws_core.const import (
    DRIFT_WINDOW_SAMPLES,
    KEY_ALERT_STATE,
    KEY_HDD_TODAY_MM,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_GUST_MS,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_RATE_FILT,
    KEY_SENSOR_DRIFT_FLAGS,
    KEY_TEMP_HIGH_24H,
    KEY_WIND_DIR_SMOOTH_DEG,
)
from tests.test_coordinator import _make_coordinator

NOW = datetime(2026, 6, 1, 12, tzinfo=UTC)


def _at(when: datetime):
    return patch.object(cmod.dt_util, "now", return_value=when)


def test_recompute_shows_current_reading_without_storing_it():
    coord = _make_coordinator()
    data: dict = {}
    coord._compute_derived_temperature(data, NOW, 25.0, 50.0, 2.0, sample=False)
    assert data[KEY_TEMP_HIGH_24H] == 25.0
    assert len(coord.runtime.temp_history_24h) == 0

    coord._compute_derived_temperature({}, NOW, 25.0, 50.0, 2.0, sample=True)
    assert len(coord.runtime.temp_history_24h) == 1


def test_wind_smoothing_advances_only_on_tick():
    coord = _make_coordinator()
    coord.runtime.smoothed_wind_dir = 0.0
    data: dict = {}
    for _ in range(10):
        coord._compute_derived_wind(data, NOW, 3.0, 5.0, 90.0, sample=False)
    assert coord.runtime.smoothed_wind_dir == 0.0
    assert data[KEY_WIND_DIR_SMOOTH_DEG] > 0.0

    coord._compute_derived_wind({}, NOW, 3.0, 5.0, 90.0, sample=True)
    assert coord.runtime.smoothed_wind_dir > 0.0


def _rain_coord():
    coord = _make_coordinator()
    coord._rain_today_date = "2026-06-01"
    coord._rain_today_mm = 0.0
    coord._rain_today_last_total = 10.0
    coord._rain_prev_day_mm = 0.0
    coord._rain_prev_day_date = ""
    coord.runtime.last_rain_total_mm = 10.0
    coord.runtime.last_rain_ts = NOW - timedelta(minutes=10)
    coord.runtime.rain_total_history_24h.append((NOW - timedelta(minutes=10), 10.0))
    return coord


def test_kalman_filter_advances_only_on_tick():
    coord = _rain_coord()
    coord.runtime.kalman.estimate = 2.0
    for _ in range(5):
        data = {KEY_NORM_RAIN_TOTAL_MM: 11.0}
        with _at(NOW):
            coord._compute_derived_precipitation(data, NOW, 11.0, sample=False)
        assert data[KEY_RAIN_RATE_FILT] == pytest.approx(2.0)
        # The 1h accumulation still sees the new reading.
        assert data[KEY_RAIN_ACCUM_1H] == pytest.approx(1.0)
    assert coord.runtime.kalman.estimate == pytest.approx(2.0)
    assert len(coord.runtime.rain_total_history_24h) == 1

    with _at(NOW):
        coord._compute_derived_precipitation({KEY_NORM_RAIN_TOTAL_MM: 11.0}, NOW, 11.0, sample=True)
    assert coord.runtime.kalman.estimate != pytest.approx(2.0)
    assert len(coord.runtime.rain_total_history_24h) == 2


def test_degree_day_mean_counts_ticks_not_updates():
    coord = _make_coordinator()
    coord.degree_days_enabled = True
    data: dict = {}
    with _at(NOW):
        coord._compute_degree_days(data, NOW, 8.0, None, None, sample=True)
        for _ in range(20):  # a burst of source updates at 0 °C between ticks
            coord._compute_degree_days(data, NOW, 0.0, None, None, sample=False)
    assert data[KEY_HDD_TODAY_MM] == pytest.approx(10.0)


def test_alert_debounce_counts_ticks_not_updates():
    coord = _make_coordinator()
    with (
        patch.object(cmod.ir, "async_create_issue"),
        patch.object(cmod.ir, "async_delete_issue"),
    ):
        for _ in range(10):
            data = {KEY_NORM_WIND_GUST_MS: 50.0}
            coord._compute_health(data, NOW, [], [], sample=False)
        assert data[KEY_ALERT_STATE] == "clear"
        for _ in range(2):
            data = {KEY_NORM_WIND_GUST_MS: 50.0}
            coord._compute_health(data, NOW, [], [], sample=True)
        assert data[KEY_ALERT_STATE] == "warning"


def test_drift_needs_a_day_of_samples_and_ignores_recomputes():
    coord = _make_coordinator()
    for name in ("_drift_temp", "_drift_humidity", "_drift_pressure", "_drift_rain_rate"):
        setattr(coord, name, deque(maxlen=DRIFT_WINDOW_SAMPLES))
    coord._drift_result = ("ok", [])

    # A steady 2 °C/h morning warm-up over 6 h is not drift.
    for i in range(6 * 60):
        data = {KEY_NORM_TEMP_C: 10.0 + i / 30.0, KEY_NORM_HUMIDITY: 50.0, KEY_NORM_PRESSURE_HPA: 1013.0}
        coord._compute_drift_detection(data, NOW + timedelta(minutes=i), sample=True)
    assert data[KEY_SENSOR_DRIFT_FLAGS] == "ok"

    before = len(coord._drift_temp)
    data = {KEY_NORM_TEMP_C: 99.0}
    coord._compute_drift_detection(data, NOW, sample=False)
    assert len(coord._drift_temp) == before
    assert data[KEY_SENSOR_DRIFT_FLAGS] == "ok"


def test_only_the_tick_samples():
    coord = _make_coordinator()
    coord._compute = MagicMock(return_value={})
    coord.async_set_updated_data = MagicMock()

    coord._handle_source_change(None)
    coord._compute.assert_called_with(sample=False)
    coord._handle_tick(None)
    coord._compute.assert_called_with(sample=True)
