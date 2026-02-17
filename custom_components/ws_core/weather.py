"""Weather platform for Weather Station Core (weather.* entity)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import WeatherEntity

try:
    from homeassistant.components.weather import WeatherEntityFeature
except Exception:  # pragma: no cover
    WeatherEntityFeature = None  # type: ignore
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
    KEY_CURRENT_CONDITION,
    KEY_FORECAST,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_SPEED_MS,
    KEY_PACKAGE_OK,
    KEY_SEA_LEVEL_PRESSURE_HPA,
)


def _weathercode_to_condition(code: int | None) -> str | None:
    # Open-Meteo weather codes (WMO) to HA conditions (best-effort).
    if code is None:
        return None
    c = int(code)
    if c == 0:
        return "sunny"
    if c in (1, 2, 3):
        return "partlycloudy" if c != 3 else "cloudy"
    if c in (45, 48):
        return "fog"
    if c in (51, 53, 55, 56, 57):
        return "rainy"
    if c in (61, 63, 65, 66, 67):
        return "rainy"
    if c in (71, 73, 75, 77):
        return "snowy"
    if c in (80, 81, 82):
        return "pouring"
    if c in (85, 86):
        return "snowy-rainy"
    if c in (95, 96, 99):
        return "lightning-rainy"
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = (entry.options.get(CONF_PREFIX) or entry.data.get(CONF_PREFIX) or DEFAULT_PREFIX).strip().lower()
    async_add_entities([WSStationWeather(coordinator, entry, prefix)])


class WSStationWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity derived from the coordinator."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, coordinator, entry: ConfigEntry, prefix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._prefix = prefix

        self._attr_unique_id = f"{entry.entry_id}_weather"
        self._attr_suggested_object_id = f"{prefix}"
        self._attr_name = "Weather Station Core"

        if WeatherEntityFeature is not None:
            self._attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        desired = f"weather.{self._prefix}"
        if self.entity_id and self.entity_id != desired:
            reg = er.async_get(self.hass)
            current = reg.async_get(self.entity_id)
            if current and current.unique_id == self.unique_id and reg.async_get(desired) is None:
                reg.async_update_entity(self.entity_id, new_entity_id=desired)

    @property
    def available(self) -> bool:
        d = self.coordinator.data or {}
        return bool(d.get(KEY_PACKAGE_OK))

    @property
    def native_temperature(self) -> float | None:
        d = self.coordinator.data or {}
        return d.get(KEY_NORM_TEMP_C)

    @property
    def humidity(self) -> float | None:
        d = self.coordinator.data or {}
        return d.get(KEY_NORM_HUMIDITY)

    @property
    def native_pressure(self) -> float | None:
        d = self.coordinator.data or {}
        return d.get(KEY_SEA_LEVEL_PRESSURE_HPA) or d.get(KEY_NORM_PRESSURE_HPA)

    @property
    def native_wind_speed(self) -> float | None:
        d = self.coordinator.data or {}
        return d.get(KEY_NORM_WIND_SPEED_MS)

    @property
    def wind_bearing(self) -> float | None:
        d = self.coordinator.data or {}
        return d.get(KEY_NORM_WIND_DIR_DEG)

    @property
    def attribution(self) -> str | None:
        # Surface attribution when forecast is enabled and available
        d = self.coordinator.data or {}
        fc = d.get(KEY_FORECAST) or {}
        if fc.get("provider") == "open-meteo":
            return "Forecast by Open-Meteo"
        return None

    # Map local condition keys to HA WeatherEntity condition strings
    _LOCAL_CONDITION_MAP = {
        "sunny": "sunny",
        "partly-cloudy": "partlycloudy",
        "cloudy": "cloudy",
        "overcast": "cloudy",
        "overcast-night": "cloudy",
        "clear-night": "clear-night",
        "rainy": "rainy",
        "drizzle": "rainy",
        "heavy-rain": "pouring",
        "thunderstorm": "lightning-rainy",
        "pre-storm": "lightning-rainy",
        "severe-storm": "lightning-rainy",
        "hurricane": "lightning-rainy",
        "snowy": "snowy",
        "snow-accumulation": "snowy",
        "sleet": "snowy-rainy",
        "fog": "fog",
        "misty-morning": "fog",
        "windy": "windy",
        "windy-night": "windy",
        "hot": "sunny",
        "cold": "clear-night",
        "sunrise": "sunny",
        "sunset": "sunny",
        "golden-hour": "sunny",
        "clearing-after-rain": "partlycloudy",
    }

    @property
    def condition(self) -> str | None:
        d = self.coordinator.data or {}
        # Prefer forecast API weathercode
        fc = d.get(KEY_FORECAST) or {}
        daily = fc.get("daily") or []
        if daily:
            api_cond = _weathercode_to_condition(daily[0].get("weathercode"))
            if api_cond:
                return api_cond
        # Fall back to local real-time condition
        local = d.get(KEY_CURRENT_CONDITION)
        if local:
            return self._LOCAL_CONDITION_MAP.get(local, "partlycloudy")
        return None

    def _build_daily_forecast(self) -> list[dict[str, Any]] | None:
        d = self.coordinator.data or {}
        fc = d.get(KEY_FORECAST) or {}
        daily = fc.get("daily") or []
        if not daily:
            return None

        out: list[dict[str, Any]] = []
        for item in daily:
            date_s = item.get("date")
            if not date_s:
                continue
            # Build a naive midday timestamp string to satisfy HA parsers.
            dt = f"{date_s}T12:00:00"
            wind_kmh = item.get("wind_kmh")
            wind_ms = (float(wind_kmh) / 3.6) if wind_kmh is not None else None
            out.append(
                {
                    "datetime": dt,
                    "temperature": item.get("tmax_c"),
                    "templow": item.get("tmin_c"),
                    "precipitation": item.get("precip_mm"),
                    "wind_speed": wind_ms,
                    "condition": _weathercode_to_condition(item.get("weathercode")),
                    ATTR_ATTRIBUTION: self.attribution,
                }
            )
        return out

    @property
    def forecast(self) -> list[dict[str, Any]] | None:
        return self._build_daily_forecast()

    async def async_forecast_daily(self) -> list[dict[str, Any]] | None:
        return self._build_daily_forecast()
