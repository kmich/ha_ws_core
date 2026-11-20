"""Sensors for Weather Station Core -- v1.7.1."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_COMFORT_INDICES,
    CONF_ENABLE_INDOOR,
    CONF_ENABLE_SOLAR_FORECAST,
    CONF_ENABLE_VIGICRUES,
    CONF_ENABLE_WEATHER_WINDOWS,
    CONF_INDOOR_ROOMS,
    CONF_PREFIX,
    CONF_VIGICRUES_RIVER_NAME,
    CONF_VIGICRUES_STATION_CODE,
    CONF_VIGICRUES_STATION_NAME,
    CONF_VIGICRUES_STATIONS,
    DEFAULT_PREFIX,
    DOMAIN,
    KEY_ABSOLUTE_HUMIDITY,
    KEY_AIR_DENSITY,
    KEY_ALERT_MESSAGE,
    KEY_ALERT_STATE,
    KEY_AQI,
    KEY_AUTO_CAL_STATUS,
    KEY_AWEKAS_STATUS,
    KEY_BATTERY_PCT,
    KEY_CDD_SEASON,
    KEY_CDD_TODAY_MM,
    KEY_CHILL_HOURS_SEASON,
    KEY_CHILL_HOURS_TODAY,
    KEY_CLEARNESS_INDEX,
    KEY_CLIMATOLOGY_30D,
    KEY_CLOUD_BASE_M,
    KEY_CLOUD_COVER_PCT,
    KEY_CONDITIONS_SUMMARY,
    KEY_CONSISTENCY_FLAGS,
    KEY_CURRENT_CONDITION,
    KEY_CWOP_STATUS_V2,
    KEY_DATA_QUALITY,
    KEY_DATA_QUALITY_SCORE,
    KEY_DATA_STATUS,
    KEY_DELTA_T,
    KEY_DEW_POINT_C,
    KEY_DOMINANT_WIND_DIR,
    KEY_DRY_STREAK,
    KEY_ET0_DAILY_MM,
    KEY_ET0_HOURLY_MM,
    KEY_ET0_PM_DAILY_MM,
    KEY_FEELS_LIKE_AIR_TEMP,
    KEY_FEELS_LIKE_C,
    KEY_FFDI,
    KEY_FFWI,
    KEY_FIRE_RISK_SCORE,
    KEY_FOG_PROBABILITY,
    KEY_FORECAST,
    KEY_FORECAST_AGREEMENT,
    KEY_FORECAST_BLEND_WEIGHT_LOCAL,
    KEY_FORECAST_BRIER_API,
    KEY_FORECAST_BRIER_LOCAL,
    KEY_FORECAST_SKILL,
    KEY_FORECAST_TILES,
    KEY_FREEZING_LEVEL_M,
    KEY_FROST_POINT_C,
    KEY_FROST_STREAK,
    KEY_FWI,
    KEY_FWI_BUI,
    KEY_FWI_DC,
    KEY_FWI_DMC,
    KEY_FWI_DSR,
    KEY_FWI_FFMC,
    KEY_FWI_ISI,
    KEY_GDD_SEASON_V2,
    KEY_GDD_TODAY_V2,
    KEY_HDD_SEASON,
    KEY_HDD_TODAY_MM,
    KEY_HEALTH_DISPLAY,
    KEY_HEAT_INDEX,
    KEY_HEAT_STREAK,
    KEY_HUMIDEX,
    KEY_HUMIDITY_LEVEL_DISPLAY,
    KEY_INDOOR_CO2_PPM,
    KEY_INDOOR_COMFORT,
    KEY_INDOOR_HUMIDITY,
    KEY_INDOOR_HUMIDITY_DELTA,
    KEY_INDOOR_ROOMS_DATA,
    KEY_INDOOR_TEMP_C,
    KEY_INDOOR_TEMP_DELTA,
    KEY_IRRIGATION_DEFICIT,
    KEY_LEAF_WETNESS,
    KEY_LIGHTNING_CLEARANCE_MIN,
    KEY_LIGHTNING_COUNT_1H,
    KEY_LIGHTNING_DISTANCE_KM,
    KEY_LIGHTNING_PROXIMITY,
    KEY_LIGHTNING_RATE_1H,
    KEY_LUX,
    KEY_MAX_SOLAR_RADIATION,
    KEY_MINUTES_UNTIL_DRY,
    KEY_MINUTES_UNTIL_RAIN,
    KEY_MOON_DISPLAY,
    KEY_MOON_ILLUMINATION_PCT,
    KEY_NEIGHBOR_QC,
    KEY_NET_RADIATION,
    KEY_NO2,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_RAIN_TOTAL_MM,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_NOWCAST_INTENSITY,
    KEY_OWM_STATIONS_STATUS,
    KEY_OZONE,
    KEY_PACKAGE_STATUS,
    KEY_PATTERN_FORECAST_SKILL,
    KEY_PATTERN_FORECAST_STATUS,
    KEY_PATTERN_FROST_12H,
    KEY_PATTERN_GUST_3H,
    KEY_PATTERN_HEAT_24H,
    KEY_PATTERN_RAIN_1H,
    KEY_PATTERN_RAIN_3H,
    KEY_PATTERN_RAIN_6H,
    KEY_PATTERN_STORM_3H,
    KEY_PEAK_SUN_HOURS,
    KEY_PM2_5,
    KEY_PM10,
    KEY_POLLEN_GRASS,
    KEY_POLLEN_OVERALL,
    KEY_POLLEN_TREE,
    KEY_POLLEN_WEED,
    KEY_PRESSURE_CHANGE_WINDOW_HPA,
    KEY_PRESSURE_TREND_DISPLAY,
    KEY_PRESSURE_TREND_HPAH,
    KEY_PWS_STATUS,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_ANOMALY_30D,
    KEY_RAIN_ANOMALY_90D,
    KEY_RAIN_ANOMALY_NORMAL,
    KEY_RAIN_DISPLAY,
    KEY_RAIN_NEXT_60MIN,
    KEY_RAIN_NORMAL_MM,
    KEY_RAIN_PROBABILITY,
    KEY_RAIN_PROBABILITY_COMBINED,
    KEY_RAIN_RATE_FILT,
    KEY_RAIN_RATE_MAX_24H,
    KEY_RAIN_THIS_MONTH_MM,
    KEY_RAIN_THIS_WEEK_MM,
    KEY_RAIN_THIS_YEAR_MM,
    KEY_RAIN_TODAY_MM,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_SEA_SURFACE_TEMP,
    KEY_SENSOR_DRIFT_FLAGS,
    KEY_SENSOR_QUALITY_FLAGS,
    KEY_SENSOR_SPIKE,
    KEY_SENSOR_STUCK,
    KEY_SNOW_PHASE,
    KEY_SNOW_RATE_CM_H,
    KEY_SNOW_RECORD_DAY_CM,
    KEY_SNOW_THIS_MONTH_CM,
    KEY_SNOW_THIS_YEAR_CM,
    KEY_SNOW_TODAY_CM,
    KEY_SOLAR_ENERGY_TODAY_WHM2,
    KEY_SOLAR_FORECAST_TODAY_KWH,
    KEY_SOLAR_FORECAST_TOMORROW_KWH,
    KEY_SOLAR_LOCAL_REMAINING_KWH,
    KEY_SOLAR_LOCAL_TODAY_KWH,
    KEY_SOLAR_LOCAL_TOMORROW_KWH,
    KEY_SOLAR_LUX_FACTOR,
    KEY_SOURCE_PROBLEMS,
    KEY_SPECIFIC_HUMIDITY,
    KEY_TEMP_ANOMALY_30D,
    KEY_TEMP_ANOMALY_90D,
    KEY_TEMP_ANOMALY_NORMAL,
    KEY_TEMP_AVG_24H,
    KEY_TEMP_DISPLAY,
    KEY_TEMP_HIGH_24H,
    KEY_TEMP_HIGH_ALL_TIME,
    KEY_TEMP_HIGH_MONTH,
    KEY_TEMP_HIGH_NORMAL,
    KEY_TEMP_HIGH_WEEK,
    KEY_TEMP_HIGH_YEAR,
    KEY_TEMP_LOW_24H,
    KEY_TEMP_LOW_ALL_TIME,
    KEY_TEMP_LOW_MONTH,
    KEY_TEMP_LOW_NORMAL,
    KEY_TEMP_LOW_WEEK,
    KEY_TEMP_LOW_YEAR,
    KEY_THSW_INDEX,
    KEY_THUNDERSTORM_RISK,
    KEY_THW_INDEX,
    KEY_UTCI,
    KEY_UV,
    KEY_UV_LEVEL_DISPLAY,
    KEY_VIGILANCE_MAX_LEVEL,
    KEY_VPD,
    KEY_WBGT,
    KEY_WC_STATUS,
    KEY_WEATHER_WINDOWS,
    KEY_WET_BULB_C,
    KEY_WIND_BEAUFORT,
    KEY_WIND_CHILL,
    KEY_WIND_DIR_SMOOTH_DEG,
    KEY_WIND_DIR_VARIABILITY,
    KEY_WIND_GUST_FACTOR,
    KEY_WIND_GUST_MAX_24H,
    KEY_WIND_GUST_MAX_ALL_TIME,
    KEY_WIND_GUST_MAX_MONTH,
    KEY_WIND_GUST_MAX_YEAR,
    KEY_WIND_QUADRANT,
    KEY_WIND_RUN_KM,
    KEY_WIND_RUN_MONTH_KM,
    KEY_WINDY_STATUS,
    KEY_WOW_STATUS,
    KEY_WU_STATUS,
    KEY_ZAMBRETTI_FORECAST,
    KEY_ZAMBRETTI_NUMBER,
    PATTERN_SOURCE_INTERNET,
    PROFILE_CUSTOM,
    SRC_LIGHTNING_COUNT,
    SRC_LIGHTNING_DISTANCE,
    SRC_LUX,
    UNIT_TEMP_C,
    normalize_indoor_rooms,
)
from .entity_descriptions import (
    _ALTITUDE_FACTORS,
    _DISTANCE_FACTORS,
    _FEATURE_TOGGLE_MAP,
    _MEASUREMENT_ANGLE_STATE_CLASS,
    _PRESSURE_FACTORS,
    _WIND_DIRECTION_DEVICE_CLASS,
    _WIND_FACTORS,
    SENSORS,
    STATION_DEPENDENT_KEYS,
    WSSensorDescription,
    sensor_selected,
    station_supports,
)
from .sensor_status import unknown_status

_LOGGER = logging.getLogger(__name__)

_HEAT_NOTE = "Below 27 °C or 40% humidity this formula does not apply, so this shows the air temperature."
# Feels-like sensors that show the air temperature when their formula does not apply.
_FEELS_LIKE_NOTES: dict[str, str] = {
    KEY_HEAT_INDEX: _HEAT_NOTE,
    KEY_THW_INDEX: _HEAT_NOTE,
    KEY_THSW_INDEX: _HEAT_NOTE,
    KEY_WIND_CHILL: (
        "Wind chill applies only at 10 °C or below with wind above 4.8 km/h, so this shows the air temperature."
    ),
    KEY_HUMIDEX: "The air is dry enough that humidity adds no discomfort, so this shows the air temperature.",
}
# Reasons meaning "this station or its settings cannot provide the value", as opposed
# to "nothing to report right now".
_NOT_ON_STATION_REASONS = frozenset(("missing_solar_radiation", "missing_lightning_source", "feature_disabled"))
# A Pattern Forecast target whose learning details are known but that has not published
# a forecast since the last restart (it does on its next run, within 15 minutes).
_PATTERN_FIRST_RUN = {
    "reason": "waiting_for_first_run",
    "explanation": "Pattern Forecast has not run since Home Assistant started; it publishes within 15 minutes.",
}
_EVENT_NOTES = (
    ("rain_event", "No rain has started or stopped since this station was set up."),
    ("frost_event", "No frost has started or ended since this station was set up."),
    ("lightning_event", "No lightning strike has been detected since this station was set up."),
)

__all__ = [
    "SENSORS",
    "WSSensorDescription",
    "_FEATURE_TOGGLE_MAP",
    "_WIND_FACTORS",
    "_PRESSURE_FACTORS",
    "_DISTANCE_FACTORS",
    "_ALTITUDE_FACTORS",
    "_WIND_DIRECTION_DEVICE_CLASS",
    "_MEASUREMENT_ANGLE_STATE_CLASS",
    "WSSensor",
    "WSDataStatusSensor",
    "WSRiverSensor",
    "WSRiverFlowSensor",
    "async_setup_entry",
]


def _async_remove_unsupported_solar_entities(
    hass: HomeAssistant, entry: ConfigEntry, opts: Mapping[str, Any], sources: Mapping[str, str]
) -> None:
    """Remove registry entries for solar sensors this station can no longer provide.

    Since 2.13.0 the solar-radiation sensors are only created when a W/m² source is
    mapped (or, for the estimated ones, the illuminance fallback is on); since 3.0.0 the
    THSW index too. Entries created by earlier versions stayed behind as unavailable
    "restored" entities forever. Unlike a feature toggle, this depends on the station's
    hardware, so they are removed; they come back if a solar radiation source is mapped
    later. Matching is by unique_id, so renamed entity ids are covered too.
    """
    stale_uids = {
        f"{entry.entry_id}_{key}"
        for key in STATION_DEPENDENT_KEYS
        if not station_supports(key, dict(opts), dict(sources))
    }
    if not stale_uids:
        return
    registry = er.async_get(hass)
    for ent in list(registry.entities.values()):
        if ent.config_entry_id != entry.entry_id or ent.domain != "sensor":
            continue
        if ent.unique_id in stale_uids:
            _LOGGER.info(
                "Removing solar sensor %s (unique_id=%s): its solar radiation source or PV meter is not mapped",
                ent.entity_id,
                ent.unique_id,
            )
            registry.async_remove(ent.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()

    opts = {**entry.data, **entry.options}
    _async_remove_unsupported_solar_entities(hass, entry, opts, coordinator.sources)

    pattern = getattr(coordinator, "_pattern", None)
    filtered: list[WSSensorDescription] = []
    for desc in SENSORS:
        if not sensor_selected(desc.key, opts, coordinator.sources):
            continue
        if desc.key == KEY_PATTERN_STORM_3H:
            # Pattern Forecast storm target: needs a mapped local lightning detector or
            # the explicit internet-lightning opt-in. With internet data the name says so
            # ("(internet lightning)"); the entity id and unique_id stay the same.
            source = pattern.storm_source if pattern is not None else None
            if source is None:
                continue
            if source == PATTERN_SOURCE_INTERNET:
                desc = dataclasses.replace(desc, translation_key="pattern_storm_3h_internet")
        filtered.append(desc)

    entities: list[SensorEntity] = [WSSensor(coordinator, entry, desc, prefix) for desc in filtered]
    entities.append(WSDataStatusSensor(coordinator, entry, prefix, filtered))

    # Named indoor rooms: per-room temp-delta, relative/absolute humidity, CO2
    # and comfort sensors. Only metrics with the required sources are created.
    # The temp-delta key matches the v2.0.5 scheme so existing
    # temperature-only rooms keep their entity ids across the upgrade.
    if opts.get(CONF_ENABLE_INDOOR, False):
        for room in normalize_indoor_rooms(opts.get(CONF_INDOOR_ROOMS)):
            rid = room["id"]
            name = room["name"]
            temp_eid = room.get("temp")
            hum_eid = room.get("humidity")
            co2_eid = room.get("co2")

            def _room_field(d, _rid=rid, _field=None):
                return (d.get(KEY_INDOOR_ROOMS_DATA) or {}).get(_rid, {}).get(_field)

            if temp_eid:
                entities.append(
                    WSSensor(
                        coordinator,
                        entry,
                        WSSensorDescription(
                            key=f"indoor_room_delta_{rid}",
                            name=f"Temp Delta - {name}",
                            translation_key="indoor_room_delta",
                            translation_placeholders={"room_name": name},
                            icon="mdi:thermometer-lines",
                            device_class=SensorDeviceClass.TEMPERATURE,
                            native_unit=UNIT_TEMP_C,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            value_fn=lambda d, _rid=rid: _room_field(d, _rid, "delta_c"),
                            attrs_fn=lambda d, _rid=rid, _eid=temp_eid: {
                                "indoor_temp_c": _room_field(d, _rid, "temp_c"),
                                "source_entity": _eid,
                            },
                        ),
                        prefix,
                    )
                )
            if hum_eid:
                entities.append(
                    WSSensor(
                        coordinator,
                        entry,
                        WSSensorDescription(
                            key=f"indoor_room_humidity_{rid}",
                            name=f"Humidity - {name}",
                            translation_key="indoor_room_humidity",
                            translation_placeholders={"room_name": name},
                            icon="mdi:water-percent",
                            device_class=SensorDeviceClass.HUMIDITY,
                            native_unit="%",
                            state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d, _rid=rid: _room_field(d, _rid, "humidity_pct"),
                            attrs_fn=lambda d, _rid=rid, _eid=hum_eid: {
                                "delta_pct": _room_field(d, _rid, "humidity_delta_pct"),
                                "source_entity": _eid,
                            },
                        ),
                        prefix,
                    )
                )
            if temp_eid and hum_eid:
                entities.append(
                    WSSensor(
                        coordinator,
                        entry,
                        WSSensorDescription(
                            key=f"indoor_room_absolute_humidity_{rid}",
                            name=f"Absolute Humidity - {name}",
                            translation_key="indoor_room_absolute_humidity",
                            translation_placeholders={"room_name": name},
                            icon="mdi:water",
                            native_unit="g/m³",
                            state_class=SensorStateClass.MEASUREMENT,
                            suggested_display_precision=2,
                            value_fn=lambda d, _rid=rid: _room_field(d, _rid, KEY_ABSOLUTE_HUMIDITY),
                            attrs_fn=lambda d, _rid=rid, _temp=temp_eid, _hum=hum_eid: {
                                "temp_c": _room_field(d, _rid, "temp_c"),
                                "humidity_pct": _room_field(d, _rid, "humidity_pct"),
                                "temperature_source_entity": _temp,
                                "humidity_source_entity": _hum,
                            },
                        ),
                        prefix,
                    )
                )
            if co2_eid:
                entities.append(
                    WSSensor(
                        coordinator,
                        entry,
                        WSSensorDescription(
                            key=f"indoor_room_co2_{rid}",
                            name=f"CO₂ - {name}",
                            translation_key="indoor_room_co2",
                            translation_placeholders={"room_name": name},
                            icon="mdi:molecule-co2",
                            device_class=SensorDeviceClass.CO2,
                            native_unit="ppm",
                            state_class=SensorStateClass.MEASUREMENT,
                            value_fn=lambda d, _rid=rid: _room_field(d, _rid, "co2_ppm"),
                            attrs_fn=lambda d, _rid=rid, _eid=co2_eid: {"source_entity": _eid},
                        ),
                        prefix,
                    )
                )
            if temp_eid or hum_eid or co2_eid:
                entities.append(
                    WSSensor(
                        coordinator,
                        entry,
                        WSSensorDescription(
                            key=f"indoor_room_comfort_{rid}",
                            name=f"Comfort - {name}",
                            translation_key="indoor_room_comfort",
                            translation_placeholders={"room_name": name},
                            icon="mdi:home-heart",
                            native_unit=None,
                            state_class=SensorStateClass.MEASUREMENT,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            value_fn=lambda d, _rid=rid: _room_field(d, _rid, "comfort"),
                            attrs_fn=lambda d, _rid=rid: {
                                "temp_c": _room_field(d, _rid, "temp_c"),
                                "humidity_pct": _room_field(d, _rid, "humidity_pct"),
                                "co2_ppm": _room_field(d, _rid, "co2_ppm"),
                            },
                        ),
                        prefix,
                    )
                )

    # v1.9.0: dynamic Vigicrues river sensors — one per configured station
    if opts.get(CONF_ENABLE_VIGICRUES, False):
        stations: list[dict] = list(opts.get(CONF_VIGICRUES_STATIONS) or [])
        if not stations:
            # Migrate legacy single-station config
            code = (opts.get(CONF_VIGICRUES_STATION_CODE) or "").strip()
            if code:
                stations = [
                    {
                        "code": code,
                        "name": opts.get(CONF_VIGICRUES_STATION_NAME) or code,
                        "river": opts.get(CONF_VIGICRUES_RIVER_NAME) or "",
                    }
                ]
            else:
                # Auto-detect — use a placeholder; the coordinator will fill the name
                stations = [{"code": "", "name": "", "river": ""}]
        for st in stations:
            entities.append(WSRiverSensor(coordinator, entry, prefix, st))
            entities.append(WSRiverFlowSensor(coordinator, entry, prefix, st))

    # v3.0.0: Weather Windows Decision Engine entities (created only when enabled)
    ww_enabled = getattr(coordinator, "weather_windows_enabled", None)
    if not isinstance(ww_enabled, bool):
        ww_enabled = bool(opts.get(CONF_ENABLE_WEATHER_WINDOWS, entry.data.get(CONF_ENABLE_WEATHER_WINDOWS, False)))
    if ww_enabled:
        from homeassistant.util import dt as dt_util

        from .weather_windows import WINDOW_STATUSES, resolve_profiles

        def _parse_ts(val: Any):
            if not val:
                return None
            parsed = dt_util.parse_datetime(str(val))
            if parsed is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
            return parsed

        profiles = getattr(coordinator, "weather_window_profiles", None)
        if not isinstance(profiles, Mapping):
            profiles = resolve_profiles(opts)

        for pid, prof in profiles.items():
            if not prof.enabled:
                continue
            placeholders = {"profile_name": prof.name} if pid == PROFILE_CUSTOM else None

            # 1. Profile Status sensor
            entities.append(
                WSSensor(
                    coordinator,
                    entry,
                    WSSensorDescription(
                        key=f"window_{pid}_status",
                        name=f"{prof.name} Status",
                        translation_key=f"window_{pid}_status",
                        translation_placeholders=placeholders,
                        icon="mdi:calendar-clock",
                        # Fixed states, so automations and the UI can offer them as choices
                        device_class=SensorDeviceClass.ENUM,
                        options=list(WINDOW_STATUSES),
                        value_fn=lambda d, _pid=pid: (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("status"),
                        attrs_fn=lambda d, _pid=pid: {
                            "reasons": (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("reasons_text", []),
                            "reason_codes": (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("reason_codes", []),
                            "not_assessed_by_provider": (d.get(KEY_WEATHER_WINDOWS) or {})
                            .get(_pid, {})
                            .get("not_assessed_by_provider", []),
                            # No remaining-duration attribute: it would change every minute while a
                            # window is open. next_start/next_end carry the window; the action
                            # response still returns duration_h.
                            "is_truncated": (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("is_truncated", False),
                            "horizon_hours": (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("horizon_hours", 0),
                        },
                    ),
                    prefix,
                )
            )

            # 2. Next window start (TIMESTAMP)
            entities.append(
                WSSensor(
                    coordinator,
                    entry,
                    WSSensorDescription(
                        key=f"window_{pid}_next_start",
                        name=f"{prof.name} Next Start",
                        translation_key=f"window_{pid}_next_start",
                        translation_placeholders=placeholders,
                        icon="mdi:play-circle-outline",
                        device_class=SensorDeviceClass.TIMESTAMP,
                        value_fn=lambda d, _pid=pid: _parse_ts(
                            (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("next_start")
                        ),
                    ),
                    prefix,
                )
            )

            # 3. Next window end (TIMESTAMP)
            entities.append(
                WSSensor(
                    coordinator,
                    entry,
                    WSSensorDescription(
                        key=f"window_{pid}_next_end",
                        name=f"{prof.name} Next End",
                        translation_key=f"window_{pid}_next_end",
                        translation_placeholders=placeholders,
                        icon="mdi:stop-circle-outline",
                        device_class=SensorDeviceClass.TIMESTAMP,
                        value_fn=lambda d, _pid=pid: _parse_ts(
                            (d.get(KEY_WEATHER_WINDOWS) or {}).get(_pid, {}).get("next_end")
                        ),
                    ),
                    prefix,
                )
            )

    async_add_entities(entities)


class WSSensor(RestoreEntity, CoordinatorEntity, SensorEntity):
    """A single derived sensor for Weather Station Core.

    Mixes in RestoreEntity so that sensors that warm up slowly (24h stats,
    Kalman filter, degree days, ET₀) report their last-known value on HA
    restart until the coordinator computes a fresh value.
    """

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset(
        {
            "forecast",
            "tiles",
            "watt_hours_day",
            "hourly",
            "raw_times",
            "raw_precip",
            "active_alerts",
            "_climatology_stats",
            # Pattern Forecast: bulky or fast-changing, not worth recording
            "top_factors",
            "per_target",
            "history_learn",
        }
    )

    # Keys that benefit from restore (slow-to-warm-up or accumulating sensors)
    _RESTORE_KEYS = {
        KEY_ET0_DAILY_MM,
        KEY_TEMP_HIGH_24H,
        KEY_TEMP_LOW_24H,
        KEY_TEMP_AVG_24H,
        KEY_WIND_GUST_MAX_24H,
        # v2.7 (issue #124): yearly / all-time temperature extremes
        KEY_TEMP_HIGH_YEAR,
        KEY_TEMP_LOW_YEAR,
        KEY_TEMP_HIGH_ALL_TIME,
        KEY_TEMP_LOW_ALL_TIME,
        # v2.7 (issue #127): weekly / monthly temperature extremes
        KEY_TEMP_HIGH_WEEK,
        KEY_TEMP_LOW_WEEK,
        KEY_TEMP_HIGH_MONTH,
        KEY_TEMP_LOW_MONTH,
        # v2.7 (issue #127): monthly / yearly / all-time gust max
        KEY_WIND_GUST_MAX_MONTH,
        KEY_WIND_GUST_MAX_YEAR,
        KEY_WIND_GUST_MAX_ALL_TIME,
        KEY_RAIN_ACCUM_1H,
        KEY_RAIN_ACCUM_24H,
        # v1.3.0: removed cut keys (HDD/CDD/METAR) from restore set
        # v1.5.0: accumulation sensors
        KEY_WIND_RUN_KM,
        KEY_CHILL_HOURS_TODAY,
        KEY_CHILL_HOURS_SEASON,
        # v2.0 accumulators
        KEY_RAIN_THIS_WEEK_MM,
        KEY_RAIN_THIS_MONTH_MM,
        KEY_RAIN_THIS_YEAR_MM,
        KEY_RAIN_RATE_MAX_24H,
        KEY_SOLAR_ENERGY_TODAY_WHM2,
        KEY_PEAK_SUN_HOURS,
    }

    # Description defaults apply only when HA creates a new registry entry.
    # The entity registry retains existing user enable/disable and rename choices.

    def __init__(self, coordinator, entry: ConfigEntry, desc: WSSensorDescription, prefix: str):
        super().__init__(coordinator)
        self._desc = desc
        self._attr_entity_registry_enabled_default = desc.entity_registry_enabled_default
        self._entry = entry
        self._prefix = prefix
        self._restored_value: Any = None  # populated by async_added_to_hass for restore-capable sensors

        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        # Setting entity_id directly (rather than _attr_suggested_object_id) makes
        # HA use it verbatim as the object_id on first registration. With
        # has_entity_name=True, _attr_suggested_object_id is treated as
        # object_id_base, which HA prefixes with the device name ("Weather
        # Station") instead of the configured prefix -- see issue #134.
        self.entity_id = f"sensor.{prefix}_{self._slug_for_key(desc.key)}"
        if desc.translation_key:
            self._attr_translation_key = desc.translation_key
            if desc.translation_placeholders:
                self._attr_translation_placeholders = desc.translation_placeholders
        else:
            self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_device_class = desc.device_class
        self._unit_group = desc.unit_group
        if desc.unit_group:
            self._attr_native_unit_of_measurement = {
                "wind": coordinator.wind_unit,
                "pressure": coordinator.pressure_unit,
                "rain": coordinator.rain_unit,
                "rain_rate": coordinator.rain_rate_unit,
                "distance": coordinator.distance_unit,
                "altitude": coordinator.altitude_unit,
                "snow": coordinator.snow_unit,
                "snow_rate": coordinator.snow_rate_unit,
                "temp_delta": coordinator.temp_unit,
                "degree_day": f"{coordinator.temp_unit}·d",
            }.get(desc.unit_group, desc.native_unit)
            # Without a suggestion HA converts device-class sensors to the HA
            # unit system's default, so a wind speed set to m/s showed in mph.
            self._attr_suggested_unit_of_measurement = self._attr_native_unit_of_measurement
        else:
            self._attr_native_unit_of_measurement = desc.native_unit
            if desc.device_class == SensorDeviceClass.TEMPERATURE and desc.native_unit == UNIT_TEMP_C:
                # HA converts temperatures itself; this makes it use the unit
                # chosen in ws_core instead of the HA unit system's.
                self._attr_suggested_unit_of_measurement = coordinator.temp_unit
        self._attr_state_class = desc.state_class
        if desc.suggested_display_precision is not None:
            self._attr_suggested_display_precision = desc.suggested_display_precision
        if desc.entity_category is not None:
            self._attr_entity_category = desc.entity_category
        if desc.options is not None:
            self._attr_options = desc.options

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._async_sync_registry_unit()
        # The entity_id is set once at creation from self.entity_id (assigned in
        # __init__), which yields sensor.{prefix}_{key} on a fresh install. We
        # deliberately do NOT force the entity_id back to that value on later
        # startups: once an entity exists in the registry, its entity_id belongs
        # to the user, and rewriting it here would silently revert any manual
        # rename on every restart and split the entity's recorder history.

        # Restore last known value for sensors that are slow to warm up
        if self._desc.key in self._RESTORE_KEYS:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state not in ("unknown", "unavailable", None, ""):
                # If the unit changed (e.g. user switched from mm to in), the
                # stored state value is in the old unit. Discard it to avoid
                # showing a stale value in the wrong unit until the coordinator
                # provides the first real reading.
                last_unit = last_state.attributes.get("unit_of_measurement")
                if self._unit_group and last_unit and last_unit != self._attr_native_unit_of_measurement:
                    self._restored_value = None
                else:
                    try:
                        self._restored_value = float(last_state.state)
                    except (ValueError, TypeError):
                        self._restored_value = last_state.state
            else:
                self._restored_value = None

    @callback
    def _async_sync_registry_unit(self) -> None:
        """Make an already registered entity show the unit chosen in ws_core.

        HA stores the suggested unit in the entity registry only when an entity
        is first created, so a later change to ws_core's unit options kept
        showing the old unit. A unit the user picked in HA's entity settings
        always wins.
        """
        want = getattr(self, "_attr_suggested_unit_of_measurement", None)
        entry = self.registry_entry
        if not want or entry is None or entry.options.get("sensor", {}).get("unit_of_measurement"):
            return
        if self.unit_of_measurement == want:
            return
        private = dict(entry.options.get("sensor.private", {}))
        private["suggested_unit_of_measurement"] = want
        self.registry_entry = er.async_get(self.hass).async_update_entity_options(
            self.entity_id, "sensor.private", private
        )
        self.async_registry_entry_updated()

    @staticmethod
    def _slug_for_key(key: str) -> str:
        overrides = {
            KEY_DATA_QUALITY: "data_quality_banner",
            KEY_FORECAST: "forecast_daily",
            KEY_NORM_TEMP_C: "temperature",
            KEY_DEW_POINT_C: "dew_point",
            KEY_FROST_POINT_C: "frost_point",
            KEY_WET_BULB_C: "wet_bulb",
            KEY_NORM_HUMIDITY: "humidity",
            KEY_NORM_PRESSURE_HPA: "station_pressure",
            KEY_SEA_LEVEL_PRESSURE_HPA: "sea_level_pressure",
            KEY_NORM_WIND_SPEED_MS: "wind_speed",
            KEY_NORM_WIND_GUST_MS: "wind_gust",
            KEY_NORM_WIND_DIR_DEG: "wind_direction",
            KEY_NORM_RAIN_TOTAL_MM: "rain_total",
            KEY_RAIN_RATE_FILT: "rain_rate",
            KEY_BATTERY_PCT: "battery",
            KEY_FEELS_LIKE_C: "feels_like",
            KEY_ZAMBRETTI_FORECAST: "zambretti_forecast",
            KEY_ZAMBRETTI_NUMBER: "zambretti_number",
            KEY_WIND_BEAUFORT: "wind_beaufort",
            KEY_WIND_QUADRANT: "wind_quadrant",
            KEY_WIND_DIR_SMOOTH_DEG: "wind_direction_smooth",
            KEY_CURRENT_CONDITION: "current_condition",
            KEY_RAIN_PROBABILITY: "rain_probability",
            KEY_RAIN_PROBABILITY_COMBINED: "rain_probability_combined",
            KEY_RAIN_DISPLAY: "rain_display",
            KEY_RAIN_ACCUM_1H: "rain_last_1h",
            KEY_RAIN_ACCUM_24H: "rain_last_24h",
            KEY_PRESSURE_TREND_DISPLAY: "pressure_trend",
            KEY_HEALTH_DISPLAY: "station_health",
            KEY_FORECAST_TILES: "forecast_tiles",
            KEY_TEMP_HIGH_24H: "temperature_high_24h",
            KEY_TEMP_LOW_24H: "temperature_low_24h",
            KEY_TEMP_AVG_24H: "temperature_avg_24h",
            KEY_WIND_GUST_MAX_24H: "wind_gust_max_24h",
            KEY_TEMP_HIGH_YEAR: "temperature_high_year",
            KEY_TEMP_LOW_YEAR: "temperature_low_year",
            KEY_TEMP_HIGH_ALL_TIME: "temperature_high_all_time",
            KEY_TEMP_LOW_ALL_TIME: "temperature_low_all_time",
            KEY_TEMP_HIGH_WEEK: "temperature_high_week",
            KEY_TEMP_LOW_WEEK: "temperature_low_week",
            KEY_TEMP_HIGH_MONTH: "temperature_high_month",
            KEY_TEMP_LOW_MONTH: "temperature_low_month",
            KEY_WIND_GUST_MAX_MONTH: "wind_gust_max_month",
            KEY_WIND_GUST_MAX_YEAR: "wind_gust_max_year",
            KEY_WIND_GUST_MAX_ALL_TIME: "wind_gust_max_all_time",
            KEY_HUMIDITY_LEVEL_DISPLAY: "humidity_level",
            KEY_UV_LEVEL_DISPLAY: "uv_level",
            KEY_TEMP_DISPLAY: "temperature_display",
            KEY_FIRE_RISK_SCORE: "fire_risk_score",
            KEY_SENSOR_QUALITY_FLAGS: "sensor_quality_flags",
            KEY_LUX: "illuminance",
            KEY_UV: "uv_index",
            KEY_ALERT_STATE: "alert_state",
            KEY_ALERT_MESSAGE: "alert_message",
            KEY_PACKAGE_STATUS: "package_status",
            KEY_PRESSURE_CHANGE_WINDOW_HPA: "pressure_change_window",
            KEY_PRESSURE_TREND_HPAH: "pressure_trend_raw",
            KEY_SEA_SURFACE_TEMP: "sea_surface_temperature",
            # v0.6.0
            KEY_ET0_DAILY_MM: "et0_daily",
            KEY_ET0_HOURLY_MM: "et0_hourly",
            KEY_WU_STATUS: "wu_upload_status",
            # v0.7.0
            KEY_AQI: "air_quality_index",
            KEY_PM2_5: "pm2_5",
            KEY_PM10: "pm10",
            KEY_NO2: "no2",
            KEY_OZONE: "ozone",
            KEY_POLLEN_OVERALL: "pollen_level",
            KEY_POLLEN_GRASS: "pollen_grass",
            KEY_POLLEN_TREE: "pollen_tree",
            KEY_POLLEN_WEED: "pollen_weed",
            # v0.8.0
            KEY_MOON_DISPLAY: "moon",
            KEY_MOON_ILLUMINATION_PCT: "moon_illumination",
            # v0.9.0
            KEY_SOLAR_FORECAST_TODAY_KWH: "solar_forecast_today",
            KEY_SOLAR_FORECAST_TOMORROW_KWH: "solar_forecast_tomorrow",
            KEY_SOLAR_LOCAL_TODAY_KWH: "solar_local_forecast_today",
            KEY_SOLAR_LOCAL_TOMORROW_KWH: "solar_local_forecast_tomorrow",
            KEY_SOLAR_LOCAL_REMAINING_KWH: "solar_local_forecast_remaining_today",
            KEY_ET0_PM_DAILY_MM: "et0_penman_monteith",
            # v1.2.0
            KEY_FOG_PROBABILITY: "fog_probability",
            KEY_THUNDERSTORM_RISK: "thunderstorm_risk",
            KEY_DRY_STREAK: "dry_streak_days",
            KEY_HEAT_STREAK: "heat_streak_days",
            KEY_FROST_STREAK: "frost_streak_days",
            KEY_SENSOR_DRIFT_FLAGS: "sensor_drift",
            KEY_CONSISTENCY_FLAGS: "sensor_consistency",
            KEY_CLIMATOLOGY_30D: "climatology_30d",
            KEY_TEMP_ANOMALY_30D: "temperature_anomaly_30d",
            KEY_RAIN_ANOMALY_30D: "rain_anomaly_30d",
            KEY_TEMP_ANOMALY_90D: "temp_anomaly_90d",
            KEY_RAIN_ANOMALY_90D: "rain_anomaly_90d",
            KEY_TEMP_HIGH_NORMAL: "temp_high_normal",
            KEY_TEMP_LOW_NORMAL: "temp_low_normal",
            KEY_RAIN_NORMAL_MM: "rain_normal",
            KEY_TEMP_ANOMALY_NORMAL: "temp_anomaly_normal",
            KEY_RAIN_ANOMALY_NORMAL: "rain_anomaly_normal",
            KEY_FORECAST_AGREEMENT: "forecast_agreement",
            KEY_FORECAST_SKILL: "forecast_skill",
            KEY_FORECAST_BRIER_LOCAL: "forecast_brier_local",
            KEY_FORECAST_BRIER_API: "forecast_brier_api",
            KEY_FORECAST_BLEND_WEIGHT_LOCAL: "forecast_blend_weight_local",
            KEY_SOLAR_LUX_FACTOR: "solar_lux_factor",
            KEY_AUTO_CAL_STATUS: "auto_calibration",
            # v1.3.0 - FWI components
            KEY_FWI_FFMC: "fwi_ffmc",
            KEY_FWI_DMC: "fwi_dmc",
            KEY_FWI_DC: "fwi_dc",
            KEY_FWI_ISI: "fwi_isi",
            KEY_FWI_BUI: "fwi_bui",
            KEY_FWI: "fwi",
            KEY_FWI_DSR: "fwi_dsr",
            # v1.5.0 - comfort indices + agrometeorological
            KEY_HEAT_INDEX: "heat_index",
            KEY_WIND_CHILL: "wind_chill",
            KEY_HUMIDEX: "humidex",
            KEY_VPD: "vpd",
            KEY_ABSOLUTE_HUMIDITY: "absolute_humidity",
            KEY_DELTA_T: "delta_t",
            KEY_THW_INDEX: "thw_index",
            KEY_THSW_INDEX: "thsw_index",
            KEY_WIND_RUN_KM: "wind_run",
            KEY_CHILL_HOURS_TODAY: "chill_hours_today",
            KEY_CHILL_HOURS_SEASON: "chill_hours_season",
            KEY_CLEARNESS_INDEX: "clearness_index",
            KEY_CLOUD_COVER_PCT: "cloud_cover",
            KEY_VIGILANCE_MAX_LEVEL: "vigilance",
            # river_level slugs are handled in WSRiverSensor directly
            KEY_RAIN_NEXT_60MIN: "rain_next_60min",
            KEY_MINUTES_UNTIL_RAIN: "minutes_until_rain",
            KEY_MINUTES_UNTIL_DRY: "minutes_until_dry",
            KEY_NOWCAST_INTENSITY: "nowcast_intensity",
            # v2.0
            KEY_CLOUD_BASE_M: "cloud_base",
            KEY_FREEZING_LEVEL_M: "freezing_level",
            KEY_WIND_GUST_FACTOR: "wind_gust_factor",
            KEY_AIR_DENSITY: "air_density",
            KEY_SPECIFIC_HUMIDITY: "specific_humidity",
            KEY_WBGT: "wbgt",
            KEY_RAIN_THIS_WEEK_MM: "rain_this_week",
            KEY_RAIN_THIS_MONTH_MM: "rain_this_month",
            KEY_RAIN_THIS_YEAR_MM: "rain_this_year",
            KEY_RAIN_RATE_MAX_24H: "rain_rate_max_24h",
            KEY_HDD_TODAY_MM: "hdd_today",
            KEY_HDD_SEASON: "hdd_season",
            KEY_CDD_TODAY_MM: "cdd_today",
            KEY_CDD_SEASON: "cdd_season",
            KEY_GDD_TODAY_V2: "gdd_today",
            KEY_GDD_SEASON_V2: "gdd_season",
            KEY_LEAF_WETNESS: "leaf_wetness",
            # v2.0 batch 3
            KEY_DOMINANT_WIND_DIR: "dominant_wind_direction",
            KEY_WIND_DIR_VARIABILITY: "wind_direction_variability",
            KEY_SOLAR_ENERGY_TODAY_WHM2: "solar_energy_today",
            KEY_MAX_SOLAR_RADIATION: "max_solar_radiation",
            KEY_PEAK_SUN_HOURS: "peak_sun_hours",
            KEY_IRRIGATION_DEFICIT: "irrigation_deficit",
            # v2.0 batch 4
            KEY_FFDI: "ffdi",
            KEY_FFWI: "ffwi",
            KEY_UTCI: "utci",
            # v2.0 batch 5 (lightning)
            KEY_LIGHTNING_COUNT_1H: "lightning_count_1h",
            KEY_LIGHTNING_DISTANCE_KM: "lightning_distance",
            KEY_LIGHTNING_RATE_1H: "lightning_rate",
            KEY_LIGHTNING_CLEARANCE_MIN: "lightning_clearance",
            KEY_LIGHTNING_PROXIMITY: "lightning_proximity",
            # v2.0 upload targets
            KEY_WC_STATUS: "wc_upload_status",
            KEY_PWS_STATUS: "pws_upload_status",
            KEY_WOW_STATUS: "wow_upload_status",
            KEY_AWEKAS_STATUS: "awekas_upload_status",
            KEY_CWOP_STATUS_V2: "cwop_upload_status",
            KEY_OWM_STATIONS_STATUS: "owm_stations_upload_status",
            KEY_WINDY_STATUS: "windy_upload_status",
            # v2.0 indoor sensors
            KEY_INDOOR_TEMP_C: "indoor_temperature",
            KEY_INDOOR_HUMIDITY: "indoor_humidity",
            KEY_INDOOR_CO2_PPM: "indoor_co2",
            KEY_INDOOR_TEMP_DELTA: "indoor_temp_delta",
            KEY_INDOOR_HUMIDITY_DELTA: "indoor_humidity_delta",
            KEY_INDOOR_COMFORT: "indoor_comfort",
            # v2.0 data quality
            KEY_SENSOR_STUCK: "sensor_stuck",
            KEY_DATA_QUALITY_SCORE: "data_quality_score",
            KEY_NEIGHBOR_QC: "neighbor_qc",
            KEY_SENSOR_SPIKE: "sensor_spike",
            # v2.0 finishing items
            KEY_WIND_RUN_MONTH_KM: "wind_run_month",
            KEY_NET_RADIATION: "net_radiation",
            KEY_RAIN_TODAY_MM: "rain_today_mm",
            KEY_CONDITIONS_SUMMARY: "conditions_summary",
            # v2.7 - snow (opt-in). Explicit overrides: the generic fallback
            # below only strips a trailing "_c", not "_cm", which would mangle
            # these into e.g. "snow_todaym".
            KEY_SNOW_PHASE: "snow_phase",
            KEY_SNOW_RATE_CM_H: "snow_rate",
            KEY_SNOW_TODAY_CM: "snow_today",
            KEY_SNOW_THIS_MONTH_CM: "snow_this_month",
            KEY_SNOW_THIS_YEAR_CM: "snow_this_year",
            KEY_SNOW_RECORD_DAY_CM: "snow_record_day",
            # v2.11 Pattern Forecast. Same as the fallback slug; listed so the
            # dashboard validator (scripts/validate_dashboard_entities.py) knows them.
            KEY_PATTERN_RAIN_1H: "pattern_rain_1h",
            KEY_PATTERN_RAIN_3H: "pattern_rain_3h",
            KEY_PATTERN_RAIN_6H: "pattern_rain_6h",
            KEY_PATTERN_FROST_12H: "pattern_frost_12h",
            KEY_PATTERN_HEAT_24H: "pattern_heat_24h",
            KEY_PATTERN_GUST_3H: "pattern_gust_3h",
            KEY_PATTERN_STORM_3H: "pattern_storm_3h",
            KEY_PATTERN_FORECAST_STATUS: "pattern_forecast_status",
            KEY_PATTERN_FORECAST_SKILL: "pattern_forecast_skill",
            # v3.0
            KEY_DATA_STATUS: "data_status",
        }
        if key in overrides:
            return overrides[key]
        # Fallback: strip a trailing unit suffix for a clean slug. Anchored to the
        # end on purpose - a bare .replace() also ate mid-string matches, turning
        # e.g. "nowcast_confidence" into "nowcastonfidence".
        for suffix in ("_mmph", "_ms", "_hpa", "_c"):
            if key.endswith(suffix):
                return key[: -len(suffix)]
        return key

    def _apply_unit_conversion(self, val: float) -> float:
        unit = self._attr_native_unit_of_measurement
        group = self._unit_group
        if group == "wind":
            return val * _WIND_FACTORS.get(unit, 1.0)
        if group == "pressure":
            return val * _PRESSURE_FACTORS.get(unit, 1.0)
        if group == "rain":
            return val / 25.4 if unit == "in" else val
        if group == "rain_rate":
            return val / 25.4 if unit == "in/h" else val
        if group == "distance":
            return val * _DISTANCE_FACTORS.get(unit, 1.0)
        if group == "altitude":
            return val * _ALTITUDE_FACTORS.get(unit, 1.0)
        if group == "snow":
            return val / 2.54 if unit == "in" else val
        if group == "snow_rate":
            return val / 2.54 if unit == "in/h" else val
        if group in ("temp_delta", "degree_day"):
            # A difference scales by 9/5 with no +32 offset.
            return round(val * 1.8, 2) if unit.startswith(UnitOfTemperature.FAHRENHEIT) else val
        return val

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        if self._desc.value_fn is not None:
            try:
                val = self._desc.value_fn(d)
            except Exception:
                val = None
        else:
            val = d.get(self._desc.key)

        # Feels-like formula outside its range: show the air temperature instead of unknown
        if val is None and self._desc.key in (d.get(KEY_FEELS_LIKE_AIR_TEMP) or ()):
            val = d.get(KEY_NORM_TEMP_C)

        # Fall back to last-restored value for slow-warm-up sensors during startup
        if val is None and self._restored_value is not None and self._desc.key in self._RESTORE_KEYS:
            return self._restored_value

        # Once the coordinator provides a real value, clear the restore cache
        if val is not None and self._restored_value is not None:
            self._restored_value = None

        if self._unit_group and val is not None:
            with contextlib.suppress(TypeError, ValueError):
                val = self._apply_unit_conversion(float(val))

        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self._value_attributes
        native = self.native_value
        if native is None and "maturity" not in attrs:
            for key, value in unknown_status(self._desc.key, self.coordinator, self.coordinator.data or {}).items():
                attrs.setdefault(key, value)
        elif self._desc.key in _FEELS_LIKE_NOTES:
            out_of_range = self._desc.key in ((self.coordinator.data or {}).get(KEY_FEELS_LIKE_AIR_TEMP) or ())
            attrs["formula_applies"] = not out_of_range
            if out_of_range:
                attrs["explanation"] = _FEELS_LIKE_NOTES[self._desc.key]
        if native is None and "maturity" in attrs and not attrs.get("explanation"):
            attrs.update(_PATTERN_FIRST_RUN)
        return attrs

    @property
    def _value_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        if self._desc.attrs_fn is not None:
            try:
                return {k: v for k, v in (self._desc.attrs_fn(d) or {}).items() if v is not None}
            except Exception:
                return {}
        if self._desc.key == KEY_ALERT_STATE:
            alerts = d.get("_active_alerts", [])
            return {
                "message": d.get(KEY_ALERT_MESSAGE, "All clear"),
                "icon": d.get("_alert_icon", "mdi:check-circle-outline"),
                "color": d.get("_alert_color", "rgba(74,222,128,0.8)"),
                "active_alerts": alerts,
                "alert_count": len(alerts),
            }
        if self._desc.key == KEY_ALERT_MESSAGE:
            return {
                "alert_state": d.get(KEY_ALERT_STATE, "clear"),
                "icon": d.get("_alert_icon", "mdi:check-circle-outline"),
                "color": d.get("_alert_color", "rgba(74,222,128,0.8)"),
            }
        if self._desc.key in (KEY_DATA_QUALITY, KEY_PACKAGE_STATUS):
            return {
                "package_ok": d.get("package_ok"),
                "data_quality": d.get(KEY_DATA_QUALITY),
                "alert_state": d.get(KEY_ALERT_STATE),
            }
        return {}


# ---------------------------------------------------------------------------
# v3.0.0 - Data Status: one place that says which sensors are empty and why
# ---------------------------------------------------------------------------


class WSDataStatusSensor(WSSensor):
    """Say whether anything needs attention, and why other sensors are empty.

    State is ``ok`` or ``attention``. Only lasting source problems (the same ones that
    raise Repairs issues) count as ``attention``; empty values with a normal reason are
    listed under ``waiting``, and sensors this station's hardware or settings cannot
    provide under ``not_on_this_station``.
    """

    _unrecorded_attributes = WSSensor._unrecorded_attributes | frozenset(
        {"summary", "needs_attention", "waiting", "not_on_this_station"}
    )

    def __init__(self, coordinator, entry: ConfigEntry, prefix: str, watched: list[WSSensorDescription]):
        super().__init__(
            coordinator,
            entry,
            WSSensorDescription(
                key=KEY_DATA_STATUS,
                translation_key="data_status",
                name="WS Data Status",
                icon="mdi:list-status",
                device_class=SensorDeviceClass.ENUM,
                options=["ok", "attention"],
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            prefix,
        )
        self._watched = [desc for desc in watched if desc.key != KEY_DATA_STATUS]

    @property
    def native_value(self) -> str:
        return "attention" if (self.coordinator.data or {}).get(KEY_SOURCE_PROBLEMS) else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        problems = list(d.get(KEY_SOURCE_PROBLEMS) or [])
        waiting: dict[str, str] = {}
        not_here = self._station_notes()
        registry = er.async_get(self.hass) if self.hass is not None else None

        for desc in self._watched:
            entity_id = self._live_entity_id(registry, "sensor", desc.key)
            if entity_id is None or self._value_of(desc, d) is not None:
                continue
            state = self.hass.states.get(entity_id) if self.hass is not None else None
            if state is not None and state.state not in ("unknown", "unavailable"):
                continue  # still showing a restored value
            info = self._safe_attrs(desc, d)
            if not info.get("explanation"):
                info = dict(_PATTERN_FIRST_RUN) if "maturity" in info else unknown_status(desc.key, self.coordinator, d)
            if info.get("reason") in _NOT_ON_STATION_REASONS:
                if info.get("reason") == "missing_lightning_source" and "Lightning" in not_here:
                    continue  # already covered by the family note
                not_here[entity_id] = info["explanation"]
            else:
                waiting[entity_id] = info.get("explanation") or "Waiting for data."

        for suffix, note in _EVENT_NOTES:
            entity_id = self._live_entity_id(registry, "event", suffix)
            state = self.hass.states.get(entity_id) if entity_id and self.hass is not None else None
            if state is not None and state.state == "unknown":
                waiting[entity_id] = note

        if problems:
            summary = "Needs attention: " + "; ".join(problems) + "."
        else:
            summary = "Everything is working."
            if waiting:
                summary += f" {len(waiting)} sensors are empty for a normal reason (see waiting)."
            if not_here:
                summary += f" {len(not_here)} are not available with this station's sensors (see not_on_this_station)."
        return {
            "summary": summary,
            "needs_attention": problems,
            "waiting": waiting,
            "not_on_this_station": not_here,
        }

    def _live_entity_id(self, registry: Any, domain: str, key: str) -> str | None:
        """Entity id of an enabled entity of this entry, or None."""
        if registry is None:
            return None
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{self._entry.entry_id}_{key}")
        if entity_id is None:
            return None
        reg_entry = registry.async_get(entity_id)
        if reg_entry is None or reg_entry.disabled_by is not None:
            return None
        return entity_id

    @staticmethod
    def _value_of(desc: WSSensorDescription, d: dict) -> Any:
        if desc.value_fn is not None:
            try:
                val = desc.value_fn(d)
            except Exception:
                val = None
        else:
            val = d.get(desc.key)
        if val is None and desc.key in (d.get(KEY_FEELS_LIKE_AIR_TEMP) or ()):
            val = d.get(KEY_NORM_TEMP_C)
        return val

    @staticmethod
    def _safe_attrs(desc: WSSensorDescription, d: dict) -> dict[str, Any]:
        if desc.attrs_fn is None:
            return {}
        try:
            return dict(desc.attrs_fn(d) or {})
        except Exception:
            return {}

    def _station_notes(self) -> dict[str, str]:
        """Feature families this station's hardware cannot provide, with what would."""
        opts = {**self._entry.data, **self._entry.options}
        sources = dict(getattr(self.coordinator, "sources", None) or {})
        notes: dict[str, str] = {}
        if not station_supports(KEY_CLEARNESS_INDEX, opts, sources):
            notes["Clearness index and cloud cover"] = (
                "Needs a solar radiation sensor (W/m²); illuminance (lux) is not accurate enough for these."
            )
        if opts.get(CONF_ENABLE_COMFORT_INDICES) and not station_supports(KEY_THSW_INDEX, opts, sources):
            notes["THSW index"] = "Needs a solar radiation sensor (W/m²)."
        if not station_supports(KEY_SOLAR_ENERGY_TODAY_WHM2, opts, sources):
            note = "Needs a solar radiation sensor (W/m²)"
            if sources.get(SRC_LUX):
                note += ", or turn on the illuminance fallback to estimate them from your lux sensor"
            notes["Solar energy, peak sun hours, net radiation and Penman-Monteith ET₀"] = note + "."
        if opts.get(CONF_ENABLE_SOLAR_FORECAST) and not station_supports(KEY_SOLAR_LOCAL_TODAY_KWH, opts, sources):
            notes["Local PV forecast"] = (
                "Pick your PV energy meters (kWh) in the Solar Forecast settings to learn a forecast from your real yield."
            )
        if getattr(self.coordinator, "lightning_enabled", False) is True and not (
            sources.get(SRC_LIGHTNING_COUNT)
            or sources.get(SRC_LIGHTNING_DISTANCE)
            or getattr(self.coordinator, "_blitzortung_sources", None)
        ):
            notes["Lightning"] = (
                "No lightning detector is mapped and no Blitzortung integration was found, "
                "so the lightning sensors stay empty."
            )
        return notes


# ---------------------------------------------------------------------------
# v1.9.0 - Dynamic river-level sensor (one per Vigicrues station)
# ---------------------------------------------------------------------------


_RIVER_SLUG_MAP = str.maketrans("éèêëàâäôöùûüîïç", "eeeeaaaoouuuiic")


def _river_slug(name: str) -> str:
    """Return a safe ASCII slug from a river or station name for use in entity IDs."""
    slug = name.lower().translate(_RIVER_SLUG_MAP).replace(" ", "_").replace("-", "_").replace("'", "")
    return "".join(c for c in slug if c.isalnum() or c == "_").strip("_")


class WSRiverSensor(CoordinatorEntity, SensorEntity):
    """Real-time water level for a single Vigicrues hydrometric station.

    One entity is created per configured station.  The station code is used as
    part of the unique_id; the river name (once known) is embedded in the entity
    name so users can tell stations apart at a glance.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:waves"
    _attr_native_unit_of_measurement = "m"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        prefix: str,
        station: dict,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._prefix = prefix
        # station dict: {code, name, river} — code may be "" for auto-detect
        self._station_code: str = (station.get("code") or "").strip()
        self._station_name: str = station.get("name") or self._station_code
        self._river_name: str = station.get("river") or ""

        # Unique ID uses station code; fall back to "auto" for auto-detect mode
        uid_suffix = self._station_code if self._station_code else "auto"
        self._attr_unique_id = f"{entry.entry_id}_river_level_{uid_suffix}"
        name_slug = _river_slug(self._river_name or self._station_name)
        slug = (
            f"river_level_{name_slug}"
            if name_slug
            else (f"river_level_{uid_suffix}" if uid_suffix != "auto" else "river_level")
        )
        self.entity_id = f"sensor.{prefix}_{slug}"

    @property
    def _cache_key(self) -> str:
        """Coordinator data key prefix for this station."""
        code = self._station_code
        if not code:
            # Auto-detect: use whatever code the coordinator resolved
            code = (self.coordinator.data or {}).get("_vigicrues_auto_code", "")
        return code

    def _resolved_code(self) -> str:
        """Return the actual station code (resolved for auto-detect)."""
        if self._station_code:
            return self._station_code
        return (self.coordinator.data or {}).get("_vigicrues_auto_code", "")

    @property
    def translation_key(self) -> str:
        return "vigicrues_river_level"

    @property
    def translation_placeholders(self) -> dict[str, str]:
        d = self.coordinator.data or {}
        code = self._resolved_code()
        river = d.get(f"_river_name_{code}") or self._river_name
        station = d.get(f"_river_station_name_{code}") or self._station_name
        return {"river": river or station or "Unknown"}

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        code = self._resolved_code()
        return d.get(f"river_level_m_{code}")

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        code = self._resolved_code()
        return {
            "station": d.get(f"_river_station_name_{code}") or self._station_name,
            "river": d.get(f"_river_name_{code}") or self._river_name,
            "station_code": d.get(f"_river_station_code_{code}") or code,
            "observed_at": d.get(f"_river_obs_time_{code}"),
        }

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}


class WSRiverFlowSensor(CoordinatorEntity, SensorEntity):
    """Real-time river flow (discharge) for a single Vigicrues hydrometric station.

    Flow data (grandeur_hydro=Q) is optional — not all stations provide it.
    The sensor is always created but returns None when the API has no Q data.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:water-sync"
    _attr_native_unit_of_measurement = "m³/s"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        prefix: str,
        station: dict,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._prefix = prefix
        self._station_code: str = (station.get("code") or "").strip()
        self._station_name: str = station.get("name") or self._station_code
        self._river_name: str = station.get("river") or ""

        uid_suffix = self._station_code if self._station_code else "auto"
        self._attr_unique_id = f"{entry.entry_id}_river_flow_{uid_suffix}"
        name_slug = _river_slug(self._river_name or self._station_name)
        slug = (
            f"river_flow_{name_slug}"
            if name_slug
            else (f"river_flow_{uid_suffix}" if uid_suffix != "auto" else "river_flow")
        )
        self.entity_id = f"sensor.{prefix}_{slug}"

    @property
    def _resolved_code(self) -> str:
        if self._station_code:
            return self._station_code
        return (self.coordinator.data or {}).get("_vigicrues_auto_code", "")

    @property
    def translation_key(self) -> str:
        return "vigicrues_river_flow"

    @property
    def translation_placeholders(self) -> dict[str, str]:
        d = self.coordinator.data or {}
        code = self._resolved_code
        river = d.get(f"_river_name_{code}") or self._river_name
        station = d.get(f"_river_station_name_{code}") or self._station_name
        return {"river": river or station or "Unknown"}

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        return d.get(f"river_flow_m3s_{self._resolved_code}")

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        code = self._resolved_code
        return {
            "station": d.get(f"_river_station_name_{code}") or self._station_name,
            "river": d.get(f"_river_name_{code}") or self._river_name,
            "station_code": d.get(f"_river_station_code_{code}") or code,
            "observed_at": d.get(f"_river_flow_obs_time_{code}"),
        }

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}
