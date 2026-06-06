"""Mocked network tests for the v2.0 upload targets + MQTT publishing.

These tests exercise the coordinator's uploader methods without touching the
real internet.  The aiohttp client session is replaced with a fake that records
the outgoing request (URL + params/payload) and returns a canned response, so we
can assert:

  1. The integration builds the correct request (URL, units conversion).
  2. The integration maps HTTP results onto the right status string
     (ok / error_http / error_auth / error_network).

CWOP (raw APRS over TCP) mocks ``asyncio.open_connection`` instead, and the
MQTT helpers mock ``homeassistant.components.mqtt``.

No live services (Weathercloud / WU / PWSWeather / WOW / AWEKAS / OWM / Windy /
CWOP) are contacted.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core import coordinator as coord_mod
from custom_components.ws_core.const import (
    KEY_DEW_POINT_C,
    KEY_NORM_HUMIDITY,
    KEY_NORM_PRESSURE_HPA,
    KEY_NORM_TEMP_C,
    KEY_NORM_WIND_DIR_DEG,
    KEY_NORM_WIND_GUST_MS,
    KEY_NORM_WIND_SPEED_MS,
    KEY_RAIN_ACCUM_1H,
    KEY_RAIN_ACCUM_24H,
    KEY_SEA_LEVEL_PRESSURE_HPA,
    KEY_UV,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fake aiohttp session
# ---------------------------------------------------------------------------


class _FakeResp:
    """Async context manager standing in for an aiohttp response."""

    def __init__(self, status: int, body: str):
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Records requests and returns a canned response (or raises)."""

    def __init__(self, status: int = 200, body: str = "success", raise_exc=None):
        self.status = status
        self.body = body
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def _record(self, method: str, url: str, kwargs: dict):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.raise_exc is not None:
            raise self.raise_exc
        return _FakeResp(self.status, self.body)

    def get(self, url, **kwargs):
        return self._record("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._record("POST", url, kwargs)

    @property
    def last(self) -> dict:
        return self.calls[-1]


def _data() -> dict:
    """A representative normalized observation."""
    return {
        KEY_NORM_TEMP_C: 20.0,
        KEY_DEW_POINT_C: 10.0,
        KEY_NORM_HUMIDITY: 55.0,
        KEY_SEA_LEVEL_PRESSURE_HPA: 1013.0,
        KEY_NORM_PRESSURE_HPA: 1010.0,
        KEY_NORM_WIND_DIR_DEG: 180.0,
        KEY_NORM_WIND_SPEED_MS: 5.0,
        KEY_NORM_WIND_GUST_MS: 8.0,
        KEY_RAIN_ACCUM_1H: 2.54,  # = 0.1 in
        KEY_RAIN_ACCUM_24H: 25.4,  # = 1.0 in
        KEY_UV: 4.0,
    }


def _coord(session: _FakeSession | None = None) -> "coord_mod.WSStationCoordinator":
    """Build a coordinator with every uploader credential populated."""
    from custom_components.ws_core.coordinator import WSStationCoordinator

    with patch.object(WSStationCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = WSStationCoordinator.__new__(WSStationCoordinator)

    coord.hass = MagicMock()
    coord.entry_data = {}
    coord.entry_options = {}
    coord.data = _data()
    coord.forecast_lat = 37.9
    coord.forecast_lon = 23.7

    # Weather Underground
    coord.wu_station_id = "KWU123"
    coord.wu_api_key = "wukey"
    coord.wu_interval_min = 5
    coord._wu_status = "disabled"
    coord._wu_last_upload = None
    # Weathercloud
    coord.wc_station_id = "12345"
    coord.wc_api_key = "wckey"
    coord.wc_interval_min = 10
    coord._wc_status = "disabled"
    coord._wc_last_upload = None
    # PWSWeather
    coord.pws_station_id = "PWS1"
    coord.pws_api_key = "pwskey"
    coord._pws_status = "disabled"
    coord._pws_last_upload = None
    # WOW
    coord.wow_site_id = "wowsite"
    coord.wow_auth_key = "123456"
    coord._wow_status = "disabled"
    coord._wow_last_upload = None
    # AWEKAS
    coord.awekas_username = "awuser"
    coord.awekas_password = "awpass"
    coord._awekas_status = "disabled"
    coord._awekas_last_upload = None
    # OWM Stations
    coord.owm_stations_api_key = "owmkey"
    coord.owm_stations_station_id = "owmstation"
    coord._owm_stations_status = "disabled"
    coord._owm_stations_last_upload = None
    # Windy
    coord.windy_api_key = "windykey"
    coord.windy_station_id = "0"
    coord._windy_status = "disabled"
    coord._windy_last_upload = None
    # CWOP
    coord.cwop_callsign = "FW1234"
    coord.cwop_passcode = "-1"
    coord.cwop_server = "cwop.aprs.net"
    coord.cwop_port = 14580
    coord._cwop_status = "disabled"
    coord._cwop_last_upload = None

    coord._patched_session = session
    return coord


def _patch_session(session: _FakeSession):
    return patch.object(coord_mod, "async_get_clientsession", lambda hass: session)


# ---------------------------------------------------------------------------
# Weather Underground
# ---------------------------------------------------------------------------


class TestWUnderground:
    async def test_happy_path_units(self):
        sess = _FakeSession(status=200, body="success\n")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wunderground()

        assert coord._wu_status == "ok"
        assert coord._wu_last_upload is not None
        c = sess.last
        assert c["url"].startswith("https://weatherstation.wunderground.com")
        p = c["params"]
        assert p["ID"] == "KWU123"
        assert p["PASSWORD"] == "wukey"
        assert p["tempf"] == pytest.approx(68.0)  # 20°C
        assert p["humidity"] == 55
        assert p["windspeedmph"] == pytest.approx(11.2, abs=0.1)  # 5 m/s
        assert p["rainin"] == pytest.approx(0.1, abs=0.001)  # 2.54 mm
        assert p["dailyrainin"] == pytest.approx(1.0, abs=0.001)  # 25.4 mm
        assert p["baromin"] == pytest.approx(29.92, abs=0.02)  # 1013 hPa

    async def test_http_500_is_error_http(self):
        sess = _FakeSession(status=500, body="boom")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wunderground()
        assert coord._wu_status == "error_http"

    async def test_200_without_success_token_is_error_http(self):
        sess = _FakeSession(status=200, body="INVALIDPASSWORDID")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wunderground()
        assert coord._wu_status == "error_http"

    async def test_network_error(self):
        sess = _FakeSession(raise_exc=aiohttp.ClientError("dns"))
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wunderground()
        assert coord._wu_status == "error_network"

    async def test_skips_when_unconfigured(self):
        sess = _FakeSession()
        coord = _coord()
        coord.wu_station_id = ""
        with _patch_session(sess):
            await coord._async_upload_wunderground()
        assert sess.calls == []
        assert coord._wu_status == "disabled"


# ---------------------------------------------------------------------------
# Weathercloud
# ---------------------------------------------------------------------------


class TestWeathercloud:
    async def test_happy_path_tenths(self):
        sess = _FakeSession(status=200, body="200")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_weathercloud()

        assert coord._wc_status == "ok"
        c = sess.last
        assert c["url"] == "https://api.weathercloud.net/v01/set"
        p = c["params"]
        assert p["wid"] == "12345"
        assert p["key"] == "wckey"
        assert p["per"] == 10
        assert p["temp"] == 200  # 20.0 °C -> tenths
        assert p["dew"] == 100  # 10.0 °C -> tenths
        assert p["hum"] == 55
        assert p["bar"] == 10130  # 1013 hPa -> tenths
        assert p["wdir"] == 180

    async def test_http_error(self):
        sess = _FakeSession(status=503, body="busy")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_weathercloud()
        assert coord._wc_status == "error_http"

    async def test_network_error(self):
        sess = _FakeSession(raise_exc=TimeoutError())
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_weathercloud()
        assert coord._wc_status == "error_network"


# ---------------------------------------------------------------------------
# PWSWeather
# ---------------------------------------------------------------------------


class TestPWSWeather:
    async def test_happy_path(self):
        sess = _FakeSession(status=200, body="success")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_pwsweather()

        assert coord._pws_status == "ok"
        c = sess.last
        assert c["url"].startswith("https://www.pwsweather.com")
        p = c["params"]
        assert p["ID"] == "PWS1"
        assert p["tempf"] == pytest.approx(68.0)
        assert p["action"] == "updateraw"

    async def test_error_http(self):
        sess = _FakeSession(status=200, body="ERROR")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_pwsweather()
        assert coord._pws_status == "error_http"


# ---------------------------------------------------------------------------
# WOW (UK Met Office)
# ---------------------------------------------------------------------------


class TestWOW:
    async def test_happy_path(self):
        sess = _FakeSession(status=200, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wow()

        assert coord._wow_status == "ok"
        c = sess.last
        assert c["url"] == "https://wow.metoffice.gov.uk/automaticreading"
        p = c["params"]
        assert p["siteid"] == "wowsite"
        assert p["siteAuthenticationKey"] == "123456"
        assert p["tempf"] == pytest.approx(68.0)
        assert p["winddir"] == 180

    async def test_201_is_ok(self):
        sess = _FakeSession(status=201, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wow()
        assert coord._wow_status == "ok"

    async def test_error(self):
        sess = _FakeSession(status=429, body="rate")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_wow()
        assert coord._wow_status == "error_http"


# ---------------------------------------------------------------------------
# AWEKAS
# ---------------------------------------------------------------------------


class TestAWEKAS:
    async def test_happy_path_payload(self):
        sess = _FakeSession(status=200, body="OK")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_awekas()

        assert coord._awekas_status == "ok"
        c = sess.last
        assert c["method"] == "POST"
        assert c["url"] == "https://data.awekas.at/eingabe_pruefung.php"
        payload = c["data"]["val"]
        fields = payload.split(";")
        assert fields[0] == "awuser"
        assert fields[1] == "awpass"
        assert fields[4] == "20.0"  # temp
        assert fields[5] == "55"  # humidity

    async def test_error(self):
        sess = _FakeSession(status=500, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_awekas()
        assert coord._awekas_status == "error_http"


# ---------------------------------------------------------------------------
# OpenWeatherMap Stations
# ---------------------------------------------------------------------------


class TestOWMStations:
    async def test_happy_path_json(self):
        sess = _FakeSession(status=204, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_owm_stations()

        assert coord._owm_stations_status == "ok"
        c = sess.last
        assert c["method"] == "POST"
        assert c["url"].startswith("https://api.openweathermap.org/data/3.0/measurements")
        assert "appid=owmkey" in c["url"]
        body = c["json"]
        assert isinstance(body, list) and len(body) == 1
        m = body[0]
        assert m["station_id"] == "owmstation"
        assert m["temperature"] == 20.0
        assert m["wind_speed"] == 5.0  # m/s, unconverted
        assert m["wind_deg"] == 180

    async def test_auth_error(self):
        sess = _FakeSession(status=401, body="bad key")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_owm_stations()
        assert coord._owm_stations_status == "error_auth"

    async def test_generic_http_error(self):
        sess = _FakeSession(status=500, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_owm_stations()
        assert coord._owm_stations_status == "error_http"


# ---------------------------------------------------------------------------
# Windy
# ---------------------------------------------------------------------------


class TestWindy:
    async def test_happy_path_units(self):
        sess = _FakeSession(status=200, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_windy()

        assert coord._windy_status == "ok"
        c = sess.last
        assert c["method"] == "POST"
        assert c["url"] == "https://stations.windy.com/pws/update/windykey"
        obs = c["json"]["observations"][0]
        assert obs["temp"] == 20.0  # °C
        assert obs["pressure"] == 101300  # Pa = hPa * 100
        assert obs["wind"] == 5.0  # m/s
        assert obs["winddir"] == 180

    async def test_auth_error(self):
        sess = _FakeSession(status=403, body="")
        coord = _coord()
        with _patch_session(sess):
            await coord._async_upload_windy()
        assert coord._windy_status == "error_auth"


# ---------------------------------------------------------------------------
# CWOP (APRS over TCP)
# ---------------------------------------------------------------------------


class _FakeReader:
    async def read(self, n: int) -> bytes:
        return b"# javAPRSSrvr\r\n"


class _FakeWriter:
    def __init__(self):
        self.written: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


class TestCWOP:
    async def test_happy_path_packet(self):
        writer = _FakeWriter()

        async def fake_open(host, port):
            assert host == "cwop.aprs.net"
            assert port == 14580
            return _FakeReader(), writer

        coord = _coord()
        with patch.object(asyncio, "open_connection", fake_open):
            await coord._async_upload_cwop()

        assert coord._cwop_status == "ok"
        sent = b"".join(writer.written).decode("ascii")
        # login line then APRS packet
        assert "user FW1234 pass -1" in sent
        assert "FW1234>APRS" in sent
        assert "_180/" in sent  # wind dir 180
        assert "t068" in sent  # 20°C -> 68°F

    async def test_connection_refused(self):
        async def fake_open(host, port):
            raise OSError("refused")

        coord = _coord()
        with patch.object(asyncio, "open_connection", fake_open):
            await coord._async_upload_cwop()
        assert coord._cwop_status == "error_network"

    async def test_skips_without_callsign(self):
        called = False

        async def fake_open(host, port):
            nonlocal called
            called = True
            return _FakeReader(), _FakeWriter()

        coord = _coord()
        coord.cwop_callsign = ""
        with patch.object(asyncio, "open_connection", fake_open):
            await coord._async_upload_cwop()
        assert called is False


# ---------------------------------------------------------------------------
# MQTT publishing
# ---------------------------------------------------------------------------


class TestMQTTPublish:
    async def test_discovery_publishes_config_topics(self):
        from custom_components.ws_core import mqtt_publisher

        publish = AsyncMock()
        fake_mqtt = MagicMock()
        fake_mqtt.is_connected.return_value = True
        fake_mqtt.async_publish = publish

        with patch.dict("sys.modules", {"homeassistant.components.mqtt": fake_mqtt}):
            await mqtt_publisher.async_publish_discovery(
                MagicMock(),
                discovery_prefix="homeassistant",
                state_prefix="ws_core",
                entity_prefix="ws",
                station_name="Backyard",
                integration_version="2.0.0",
            )

        assert publish.await_count > 0
        topics = [call.args[1] for call in publish.await_args_list]
        assert all(t.startswith("homeassistant/sensor/ws_core_ws_") for t in topics)
        assert all(t.endswith("/config") for t in topics)

    async def test_states_publishes_values(self):
        from custom_components.ws_core import mqtt_publisher

        publish = AsyncMock()
        fake_mqtt = MagicMock()
        fake_mqtt.is_connected.return_value = True
        fake_mqtt.async_publish = publish

        with patch.dict("sys.modules", {"homeassistant.components.mqtt": fake_mqtt}):
            await mqtt_publisher.async_publish_states(
                MagicMock(),
                state_prefix="ws_core",
                entity_prefix="ws",
                coordinator_data=_data(),
            )

        assert publish.await_count > 0
        topics = [call.args[1] for call in publish.await_args_list]
        assert all(t.startswith("ws_core/ws/") and t.endswith("/state") for t in topics)

    async def test_no_publish_when_broker_disconnected(self):
        from custom_components.ws_core import mqtt_publisher

        publish = AsyncMock()
        fake_mqtt = MagicMock()
        fake_mqtt.is_connected.return_value = False
        fake_mqtt.async_publish = publish

        with patch.dict("sys.modules", {"homeassistant.components.mqtt": fake_mqtt}):
            await mqtt_publisher.async_publish_states(
                MagicMock(),
                state_prefix="ws_core",
                entity_prefix="ws",
                coordinator_data=_data(),
            )
        publish.assert_not_awaited()
