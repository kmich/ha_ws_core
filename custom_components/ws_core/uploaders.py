"""External weather network upload handlers for Weather Station Core."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    _INTEGRATION_VERSION,
    KEY_DEW_POINT_C,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_RAIN_TODAY_MM,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_UV,
)

_LOGGER = logging.getLogger(__name__)


def _redact_secrets(text: Any, *secrets: str | None) -> str:
    """Return ``str(text)`` with every non-empty secret replaced."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "**REDACTED**")
    return out


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------


def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _ms_to_mph(ms: float) -> float:
    return round(float(ms) * 2.23694, 1)


def _mm_to_in(mm: float) -> float:
    return round(float(mm) / 25.4, 3)


def _hpa_to_inhg(hpa: float) -> float:
    return round(float(hpa) / 33.8639, 2)


def _ms_to_kmh(ms: float) -> float:
    return round(float(ms) * 3.6, 1)


# ---------------------------------------------------------------------------
# Upload implementations
# ---------------------------------------------------------------------------


async def async_upload_wunderground(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload observation to Weather Underground Personal Weather Station API."""
    data = coord.data
    if not data or not coord.wu_station_id or not coord.wu_api_key:
        return

    now_utc = dt_util.utcnow()
    date_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S")

    temp_c = data.get(KEY_NORM_TEMP_C)
    dew_c = data.get(KEY_DEW_POINT_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
    rain_today = data.get(KEY_RAIN_TODAY_MM) or 0

    params = {
        "ID": coord.wu_station_id,
        "PASSWORD": coord.wu_api_key,
        "dateutc": date_utc,
        "winddir": int(wind_dir),
        "windspeedmph": _ms_to_mph(wind_ms),
        "windgustmph": _ms_to_mph(gust_ms),
        "rainin": _mm_to_in(rain_1h),
        "dailyrainin": _mm_to_in(rain_today),
        "action": "updateraw",
        "softwaretype": f"ws_core_{_INTEGRATION_VERSION}",
    }
    if temp_c is not None:
        params["tempf"] = _c_to_f(float(temp_c))
    if dew_c is not None:
        params["dewptf"] = _c_to_f(float(dew_c))
    if humidity is not None:
        params["humidity"] = int(float(humidity))
    if press is not None:
        params["baromin"] = _hpa_to_inhg(float(press))

    url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            body = await resp.text()
            if resp.status == 200 and "success" in body.lower():
                coord._wu_last_upload = now_utc
                coord._wu_status = "ok"
                _LOGGER.debug("WUnderground upload OK")
            else:
                coord._wu_status = "error_http"
                _LOGGER.warning("WUnderground upload failed HTTP %d: %s", resp.status, body[:120])
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._wu_status = "error_network"
        _LOGGER.warning("WUnderground upload error: %s", _redact_secrets(exc, coord.wu_api_key))
    except Exception as exc:  # noqa: BLE001
        coord._wu_status = "error"
        _LOGGER.error("WUnderground upload unexpected error: %s", _redact_secrets(exc, coord.wu_api_key))


async def async_upload_cwop(coord: Any) -> None:
    """Upload observation to CWOP network using APRS protocol over TCP."""
    data = coord.data
    if not data or not coord.cwop_callsign:
        return

    now_utc = dt_util.utcnow()
    lat = coord.forecast_lat
    lon = coord.forecast_lon
    if lat is None or lon is None:
        return

    temp_c = data.get(KEY_NORM_TEMP_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
    rain_24h = data.get(KEY_RAIN_ACCUM_24H) or 0
    rain_today = data.get(KEY_RAIN_TODAY_MM) or 0

    lat_f = float(lat)
    lon_f = float(lon)
    lat_deg = int(abs(lat_f))
    lat_min = (abs(lat_f) - lat_deg) * 60
    lon_deg = int(abs(lon_f))
    lon_min = (abs(lon_f) - lon_deg) * 60
    lat_str = f"{lat_deg:02d}{lat_min:05.2f}{'N' if lat_f >= 0 else 'S'}"
    lon_str = f"{lon_deg:03d}{lon_min:05.2f}{'E' if lon_f >= 0 else 'W'}"

    time_str = now_utc.strftime("%d%H%M")

    def _cwop_ms_to_mph(ms: float) -> int:
        return round(float(ms) * 2.23694)

    def _mm_to_hundredths_in(mm: float) -> int:
        return round(float(mm) / 25.4 * 100)

    def _cwop_c_to_f(c: float) -> int:
        return round(float(c) * 9 / 5 + 32)

    wind_dir_s = f"{int(wind_dir):03d}"
    wind_spd_s = f"{_cwop_ms_to_mph(wind_ms):03d}"
    gust_s = f"g{_cwop_ms_to_mph(gust_ms):03d}"
    temp_s = f"t{_cwop_c_to_f(float(temp_c)):03d}" if temp_c is not None else "t..."
    rain1h_s = f"r{_mm_to_hundredths_in(float(rain_1h)):03d}"
    rain24h_s = f"p{_mm_to_hundredths_in(float(rain_24h)):03d}"
    rain_midnight_s = f"P{_mm_to_hundredths_in(float(rain_today)):03d}"
    hum_s = f"h{round(float(humidity)) % 100:02d}" if humidity is not None else ""
    baro_s = f"b{round(float(press) * 10):05d}" if press is not None else ""

    weather_body = (
        f"_{wind_dir_s}/{wind_spd_s}{gust_s}{temp_s}"
        f"{rain1h_s}{rain24h_s}{rain_midnight_s}{hum_s}{baro_s}"
        f" ws_core/{_INTEGRATION_VERSION}"
    )

    packet = (
        f"{coord.cwop_callsign}>APRS,TCPXX*,qAX,{coord.cwop_callsign}:@{time_str}z{lat_str}/{lon_str}{weather_body}\r\n"
    )
    login = f"user {coord.cwop_callsign} pass {coord.cwop_passcode} vers ws_core {_INTEGRATION_VERSION}\r\n"

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(coord.cwop_server, coord.cwop_port),
            timeout=15,
        )
        try:
            writer.write(login.encode("ascii"))
            await writer.drain()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(reader.read(256), timeout=1.5)
            writer.write(packet.encode("ascii"))
            await writer.drain()
            coord._cwop_last_upload = now_utc
            coord._cwop_status = "ok"
            _LOGGER.debug("CWOP upload OK: %s", packet.strip())
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except (TimeoutError, OSError) as exc:
        coord._cwop_status = "error_network"
        _LOGGER.warning("CWOP upload error: %s", exc)
    except Exception as exc:  # noqa: BLE001
        coord._cwop_status = "error"
        _LOGGER.error("CWOP upload unexpected error: %s", exc)


async def async_upload_weathercloud(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload observation to Weathercloud."""
    data = coord.data
    if not data or not coord.wc_station_id or not coord.wc_api_key:
        return

    now_utc = dt_util.utcnow()
    temp_c = data.get(KEY_NORM_TEMP_C)
    dew_c = data.get(KEY_DEW_POINT_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
    uv = data.get(KEY_UV)

    params: dict = {
        "wid": coord.wc_station_id,
        "key": coord.wc_api_key,
        "per": int(coord.wc_interval_min),
    }
    if temp_c is not None:
        params["temp"] = round(float(temp_c) * 10)
    if dew_c is not None:
        params["dew"] = round(float(dew_c) * 10)
    if humidity is not None:
        params["hum"] = int(float(humidity))
    if press is not None:
        params["bar"] = round(float(press) * 10)
    params["wspdavg"] = round(_ms_to_kmh(wind_ms) * 10)
    params["wgust"] = round(_ms_to_kmh(gust_ms) * 10)
    params["wdir"] = int(wind_dir)
    params["rain"] = round(float(rain_1h) * 10)
    if uv is not None:
        params["uvi"] = round(float(uv) * 10)

    url = "https://api.weathercloud.net/v01/set"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            body = await resp.text()
            if resp.status == 200:
                coord._wc_last_upload = now_utc
                coord._wc_status = "ok"
            else:
                coord._wc_status = "error_http"
                _LOGGER.warning("Weathercloud upload HTTP %d: %s", resp.status, body[:120])
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._wc_status = "error_network"
        _LOGGER.warning("Weathercloud upload error: %s", _redact_secrets(exc, coord.wc_api_key))
    except Exception as exc:  # noqa: BLE001
        coord._wc_status = "error"
        _LOGGER.error("Weathercloud upload unexpected error: %s", _redact_secrets(exc, coord.wc_api_key))


async def async_upload_pwsweather(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload observation to PWSWeather (WU-compatible API)."""
    data = coord.data
    if not data or not coord.pws_station_id or not coord.pws_api_key:
        return

    now_utc = dt_util.utcnow()
    date_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    temp_c = data.get(KEY_NORM_TEMP_C)
    dew_c = data.get(KEY_DEW_POINT_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG) or 0
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS) or 0
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS) or 0
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
    rain_today = data.get(KEY_RAIN_TODAY_MM) or 0

    params: dict = {
        "ID": coord.pws_station_id,
        "PASSWORD": coord.pws_api_key,
        "dateutc": date_utc,
        "winddir": int(wind_dir),
        "windspeedmph": _ms_to_mph(wind_ms),
        "windgustmph": _ms_to_mph(gust_ms),
        "rainin": _mm_to_in(rain_1h),
        "dailyrainin": _mm_to_in(rain_today),
        "action": "updateraw",
        "softwaretype": f"ws_core_{_INTEGRATION_VERSION}",
    }
    if temp_c is not None:
        params["tempf"] = _c_to_f(float(temp_c))
    if dew_c is not None:
        params["dewptf"] = _c_to_f(float(dew_c))
    if humidity is not None:
        params["humidity"] = int(float(humidity))
    if press is not None:
        params["baromin"] = _hpa_to_inhg(float(press))

    url = "https://www.pwsweather.com/weatherstation/updateweatherstation.php"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            body = await resp.text()
            if resp.status == 200 and "success" in body.lower():
                coord._pws_last_upload = now_utc
                coord._pws_status = "ok"
            else:
                coord._pws_status = "error_http"
                _LOGGER.warning("PWSWeather upload HTTP %d: %s", resp.status, body[:120])
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._pws_status = "error_network"
        _LOGGER.warning("PWSWeather upload error: %s", _redact_secrets(exc, coord.pws_api_key))
    except Exception as exc:  # noqa: BLE001
        coord._pws_status = "error"
        _LOGGER.error("PWSWeather upload unexpected error: %s", _redact_secrets(exc, coord.pws_api_key))


async def async_upload_wow(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload observation to UK Met Office WOW."""
    data = coord.data
    if not data or not coord.wow_site_id or not coord.wow_auth_key:
        return

    now_utc = dt_util.utcnow()
    date_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    temp_c = data.get(KEY_NORM_TEMP_C)
    dew_c = data.get(KEY_DEW_POINT_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG)
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0

    params: dict = {
        "siteid": coord.wow_site_id,
        "siteAuthenticationKey": coord.wow_auth_key,
        "dateutc": date_utc,
        "softwaretype": f"ws_core_{_INTEGRATION_VERSION}",
    }
    if temp_c is not None:
        params["tempf"] = round(float(temp_c) * 9 / 5 + 32, 1)
    if dew_c is not None:
        params["dewptf"] = round(float(dew_c) * 9 / 5 + 32, 1)
    if humidity is not None:
        params["humidity"] = int(float(humidity))
    if press is not None:
        params["baromin"] = round(float(press) / 33.8639, 2)
    if wind_dir is not None:
        params["winddir"] = int(float(wind_dir))
    if wind_ms is not None:
        params["windspeedmph"] = round(float(wind_ms) * 2.23694, 1)
    if gust_ms is not None:
        params["windgustmph"] = round(float(gust_ms) * 2.23694, 1)
    params["rainin"] = round(float(rain_1h) / 25.4, 3)

    url = "https://wow.metoffice.gov.uk/automaticreading"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (200, 201):
                coord._wow_last_upload = now_utc
                coord._wow_status = "ok"
            else:
                coord._wow_status = "error_http"
                _LOGGER.warning("WOW upload HTTP %d", resp.status)
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._wow_status = "error_network"
        _LOGGER.warning("WOW upload error: %s", _redact_secrets(exc, coord.wow_auth_key))
    except Exception as exc:  # noqa: BLE001
        coord._wow_status = "error"
        _LOGGER.error("WOW upload unexpected error: %s", _redact_secrets(exc, coord.wow_auth_key))


async def async_upload_awekas(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload observation to AWEKAS."""
    data = coord.data
    if not data or not coord.awekas_username or not coord.awekas_password:
        return

    now_utc = dt_util.utcnow()
    temp_c = data.get(KEY_NORM_TEMP_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG)
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
    rain_1h = data.get(KEY_RAIN_ACCUM_1H) or 0
    snow_mm = None

    date_str = now_utc.strftime("%d.%m.%Y")
    time_str = now_utc.strftime("%H:%M")
    values = [
        coord.awekas_username,
        coord.awekas_password,
        date_str,
        time_str,
        f"{float(temp_c):.1f}" if temp_c is not None else "",
        f"{int(float(humidity))}" if humidity is not None else "",
        f"{float(press):.1f}" if press is not None else "",
        f"{float(rain_1h):.1f}",
        f"{round(float(wind_ms) * 3.6, 1)}" if wind_ms is not None else "",
        f"{int(float(wind_dir))}" if wind_dir is not None else "",
        f"{round(float(gust_ms) * 3.6, 1)}" if gust_ms is not None else "",
        "",
        "" if snow_mm is None else f"{snow_mm:.1f}",
    ]
    payload = ";".join(values)

    url = "https://data.awekas.at/eingabe_pruefung.php"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.post(
            url,
            data={"val": payload},
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            if resp.status == 200:
                coord._awekas_last_upload = now_utc
                coord._awekas_status = "ok"
            else:
                coord._awekas_status = "error_http"
                _LOGGER.warning("AWEKAS upload HTTP %d", resp.status)
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._awekas_status = "error_network"
        _LOGGER.warning("AWEKAS upload error: %s", exc)
    except Exception as exc:  # noqa: BLE001
        coord._awekas_status = "error"
        _LOGGER.error("AWEKAS upload unexpected error: %s", exc)


async def async_upload_owm_stations(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload a measurement to the OpenWeatherMap Stations API (v3)."""
    data = coord.data
    if not data or not coord.owm_stations_api_key or not coord.owm_stations_station_id:
        return

    now_utc = dt_util.utcnow()
    temp_c = data.get(KEY_NORM_TEMP_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG)
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
    rain_1h = data.get(KEY_RAIN_ACCUM_1H)

    measurement: dict[str, Any] = {
        "station_id": coord.owm_stations_station_id,
        "dt": int(now_utc.timestamp()),
    }
    if temp_c is not None:
        measurement["temperature"] = round(float(temp_c), 1)
    if humidity is not None:
        measurement["humidity"] = int(float(humidity))
    if press is not None:
        measurement["pressure"] = round(float(press), 1)
    if wind_ms is not None:
        measurement["wind_speed"] = round(float(wind_ms), 1)
    if gust_ms is not None:
        measurement["wind_gust"] = round(float(gust_ms), 1)
    if wind_dir is not None:
        measurement["wind_deg"] = int(float(wind_dir))
    if rain_1h is not None:
        measurement["rain_1h"] = round(float(rain_1h), 1)

    url = f"https://api.openweathermap.org/data/3.0/measurements?appid={coord.owm_stations_api_key}"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.post(url, json=[measurement], timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (200, 201, 204):
                coord._owm_stations_last_upload = now_utc
                coord._owm_stations_status = "ok"
            elif resp.status in (401, 403):
                coord._owm_stations_status = "error_auth"
                _LOGGER.warning("OWM Stations upload auth error HTTP %d", resp.status)
            else:
                coord._owm_stations_status = "error_http"
                _LOGGER.warning("OWM Stations upload HTTP %d", resp.status)
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._owm_stations_status = "error_network"
        _LOGGER.warning("OWM Stations upload error: %s", _redact_secrets(exc, coord.owm_stations_api_key))
    except Exception as exc:  # noqa: BLE001
        coord._owm_stations_status = "error"
        _LOGGER.error("OWM Stations upload unexpected error: %s", _redact_secrets(exc, coord.owm_stations_api_key))


async def async_upload_windy(coord: Any, session: aiohttp.ClientSession | None = None) -> None:
    """Upload an observation to Windy.com Stations API."""
    data = coord.data
    if not data or not coord.windy_api_key:
        return

    now_utc = dt_util.utcnow()
    temp_c = data.get(KEY_NORM_TEMP_C)
    dew_c = data.get(KEY_DEW_POINT_C)
    humidity = data.get(KEY_NORM_HUMIDITY)
    press = data.get(KEY_SEA_LEVEL_PRESSURE_HPA) or data.get(KEY_NORM_PRESSURE_HPA)
    wind_dir = data.get(KEY_NORM_WIND_DIR_DEG)
    wind_ms = data.get(KEY_NORM_WIND_SPEED_MS)
    gust_ms = data.get(KEY_NORM_WIND_GUST_MS)
    rain_1h = data.get(KEY_RAIN_ACCUM_1H)

    obs: dict[str, Any] = {
        "dateutc": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        obs["station"] = int(coord.windy_station_id) if coord.windy_station_id else 0
    except (TypeError, ValueError):
        obs["station"] = 0
    if temp_c is not None:
        obs["temp"] = round(float(temp_c), 1)
    if dew_c is not None:
        obs["dewpoint"] = round(float(dew_c), 1)
    if humidity is not None:
        obs["rh"] = int(float(humidity))
    if press is not None:
        obs["pressure"] = round(float(press) * 100.0)
    if wind_ms is not None:
        obs["wind"] = round(float(wind_ms), 1)
    if gust_ms is not None:
        obs["gust"] = round(float(gust_ms), 1)
    if wind_dir is not None:
        obs["winddir"] = int(float(wind_dir))
    if rain_1h is not None:
        obs["precip"] = round(float(rain_1h), 1)

    url = f"https://stations.windy.com/pws/update/{coord.windy_api_key}"
    try:
        sess = session or async_get_clientsession(coord.hass)
        async with sess.post(url, json={"observations": [obs]}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status in (200, 201, 204):
                coord._windy_last_upload = now_utc
                coord._windy_status = "ok"
            elif resp.status in (401, 403):
                coord._windy_status = "error_auth"
                _LOGGER.warning("Windy upload auth error HTTP %d", resp.status)
            else:
                coord._windy_status = "error_http"
                _LOGGER.warning("Windy upload HTTP %d", resp.status)
    except (aiohttp.ClientError, TimeoutError) as exc:
        coord._windy_status = "error_network"
        _LOGGER.warning("Windy upload error: %s", _redact_secrets(exc, coord.windy_api_key))
    except Exception as exc:  # noqa: BLE001
        coord._windy_status = "error"
        _LOGGER.error("Windy upload unexpected error: %s", _redact_secrets(exc, coord.windy_api_key))
