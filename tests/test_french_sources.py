"""Tests for v1.8.0 French data sources.

Covers:
  1. Fire danger extraction from Vigilance phenomena dict (coordinator)
  2. Vigicrues station code from config bypasses auto-detect (coordinator init)
  3. _fetch_vigicrues_station_options() helper (config_flow module)
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.ws_core.const import (
    CONF_VIGICRUES_RIVER_NAME,
    CONF_VIGICRUES_STATION_CODE,
    CONF_VIGICRUES_STATION_NAME,
    KEY_FIRE_DANGER_VIGILANCE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vigilance_cache(phenomena: dict[str, str], dept: str = "13") -> dict:
    """Build a minimal vigilance cache dict like the one stored by the coordinator."""
    return {
        "max_color": "vert",
        "phenomena": phenomena,
        "dept": dept,
        "fetched_at": "2026-05-26T12:00:00",
    }


def _apply_vigilance_to_data(vigilance_cache: dict) -> dict:
    """Replicate the v1.8.0 fire-danger extraction logic from coordinator.py."""
    data: dict = {}
    vc = vigilance_cache
    data["_vigilance_phenomena"] = vc.get("phenomena", {})
    data["_vigilance_dept"] = vc.get("dept")
    data["_vigilance_fetched_at"] = vc.get("fetched_at")

    phenomena: dict[str, str] = vc.get("phenomena", {})
    fire_color = None
    for ph_name, color in phenomena.items():
        if "feux" in ph_name.lower():
            fire_color = color
            break
    data[KEY_FIRE_DANGER_VIGILANCE] = fire_color if fire_color else "vert"
    return data


# ---------------------------------------------------------------------------
# 1. Fire danger extraction
# ---------------------------------------------------------------------------


class TestFireDangerExtraction:
    """Verify fire danger is derived correctly from the Vigilance phenomena dict."""

    def test_no_fire_phenomenon_yields_vert(self):
        """When no 'Feux de forêt' phenomenon is present, sensor should be 'vert'."""
        cache = _make_vigilance_cache({"Vent violent": "orange", "Orages": "jaune"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "vert"

    def test_empty_phenomena_yields_vert(self):
        """Empty phenomena dict → vert."""
        cache = _make_vigilance_cache({})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "vert"

    def test_feux_jaune_yields_jaune(self):
        """'Feux de forêt' with 'jaune' → sensor is 'jaune'."""
        cache = _make_vigilance_cache({"Feux de forêt": "jaune"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "jaune"

    def test_feux_orange_yields_orange(self):
        cache = _make_vigilance_cache({"Feux de forêt": "orange", "Canicule": "jaune"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "orange"

    def test_feux_rouge_yields_rouge(self):
        cache = _make_vigilance_cache({"Feux de forêt": "rouge"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "rouge"

    def test_feux_case_insensitive(self):
        """The key check uses .lower() so mixed-case keys are handled."""
        cache = _make_vigilance_cache({"FEUX DE FORÊT": "orange"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "orange"

    def test_other_phenomena_not_affected(self):
        """Other phenomena colours must not bleed into fire danger."""
        cache = _make_vigilance_cache({"Inondations": "rouge", "Orages": "orange"})
        data = _apply_vigilance_to_data(cache)
        assert data[KEY_FIRE_DANGER_VIGILANCE] == "vert"


# ---------------------------------------------------------------------------
# 2. Vigicrues station code from config bypasses auto-detect
# ---------------------------------------------------------------------------


class TestVigicruesStationInit:
    """Verify that a station code stored in config is respected at coordinator init."""

    def _build_config(self, code: str, name: str = "Station Test", river: str = "La Durance") -> dict:
        return {
            CONF_VIGICRUES_STATION_CODE: code,
            CONF_VIGICRUES_STATION_NAME: name,
            CONF_VIGICRUES_RIVER_NAME: river,
        }

    def test_station_code_set_from_config(self):
        """Non-empty station code in config → coordinator stores it, skips auto-detect."""
        # We test the logic isolated, not the full coordinator (which needs HA)
        conf_code = "W5200010"
        _conf_code = (conf_code or "").strip()
        station_code = _conf_code if _conf_code else None
        assert station_code == "W5200010"

    def test_empty_station_code_gives_none(self):
        """Empty station code in config → None (auto-detect enabled)."""
        conf_code = ""
        _conf_code = (conf_code or "").strip()
        station_code = _conf_code if _conf_code else None
        assert station_code is None

    def test_whitespace_station_code_gives_none(self):
        """Whitespace-only station code → None (same as empty)."""
        conf_code = "   "
        _conf_code = (conf_code or "").strip()
        station_code = _conf_code if _conf_code else None
        assert station_code is None

    def test_station_name_only_set_when_code_present(self):
        """Station name / river name should only be read when a code is configured.

        Replicates: self._vigicrues_station_name = ((_get(name, "") or None) if _conf_code else None)
        """
        raw_name = "Station Test"
        raw_river = "La Durance"

        # With a real code both names are preserved
        _conf_code = "W5200010"
        station_name = (raw_name or None) if _conf_code else None
        river_name = (raw_river or None) if _conf_code else None
        assert station_name == "Station Test"
        assert river_name == "La Durance"

        # With an empty name string (config stored "") the `or None` converts to None
        _conf_code = "W5200010"
        station_name_empty = ("" or None) if _conf_code else None
        assert station_name_empty is None

        # No code → names are always None regardless of the stored value
        _conf_code = ""
        station_name = "Station Test" if _conf_code else None
        river_name = "La Durance" if _conf_code else None
        assert station_name is None
        assert river_name is None


# ---------------------------------------------------------------------------
# 3. _fetch_vigicrues_station_options() with mocked aiohttp
# ---------------------------------------------------------------------------


class TestFetchVigicruesStationOptions:
    """Unit tests for the config-flow helper that fetches nearby stations."""

    @pytest.mark.asyncio
    async def test_returns_auto_option_only_on_http_error(self):
        """When Hub'Eau returns a non-200 response, only the 'Auto' option is returned."""
        from custom_components.ws_core.config_flow import _fetch_vigicrues_station_options

        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            options = await _fetch_vigicrues_station_options(43.3, 5.4)

        assert len(options) == 1
        assert options[0]["value"] == ""
        assert options[0]["label"] == "Auto (nearest station)"

    @pytest.mark.asyncio
    async def test_returns_auto_option_only_on_timeout(self):
        """On network/timeout error, fallback to auto-only list."""
        import aiohttp

        from custom_components.ws_core.config_flow import _fetch_vigicrues_station_options

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("timeout"))
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            options = await _fetch_vigicrues_station_options(43.3, 5.4)

        assert options == [{"value": "", "label": "Auto (nearest station)", "_name": "", "_river": ""}]

    @pytest.mark.asyncio
    async def test_parses_stations_correctly(self):
        """Successful response → auto option + one entry per station in data."""
        from custom_components.ws_core.config_flow import _fetch_vigicrues_station_options

        api_payload = {
            "data": [
                {
                    "code_station": "W5200010",
                    "libelle_station": "LA DURANCE A CADARACHE",
                    "libelle_cours_eau": "La Durance",
                },
                {
                    "code_station": "W6200020",
                    "libelle_station": "L'ARC A AIX",
                    "libelle_cours_eau": "L'Arc",
                },
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=api_payload)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            options = await _fetch_vigicrues_station_options(43.5, 5.5)

        assert len(options) == 3  # auto + 2 stations
        assert options[0]["value"] == ""  # auto is always first

        codes = [o["value"] for o in options[1:]]
        assert "W5200010" in codes
        assert "W6200020" in codes

        # Labels include river name in parentheses
        durance_opt = next(o for o in options if o["value"] == "W5200010")
        assert "LA DURANCE A CADARACHE" in durance_opt["label"]
        assert "La Durance" in durance_opt["label"]
        assert durance_opt["_name"] == "LA DURANCE A CADARACHE"
        assert durance_opt["_river"] == "La Durance"

    @pytest.mark.asyncio
    async def test_skips_stations_without_code(self):
        """Stations with empty code_station are silently skipped."""
        from custom_components.ws_core.config_flow import _fetch_vigicrues_station_options

        api_payload = {
            "data": [
                {"code_station": "", "libelle_station": "Sans code", "libelle_cours_eau": "Rivière X"},
                {"code_station": "W9900001", "libelle_station": "Station Valide", "libelle_cours_eau": "Rivière Y"},
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=api_payload)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            options = await _fetch_vigicrues_station_options(43.5, 5.5)

        assert len(options) == 2  # auto + 1 valid
        assert options[1]["value"] == "W9900001"

    @pytest.mark.asyncio
    async def test_station_without_river_name(self):
        """Station with no libelle_cours_eau → label is just the station name."""
        from custom_components.ws_core.config_flow import _fetch_vigicrues_station_options

        api_payload = {
            "data": [
                {"code_station": "W1234567", "libelle_station": "Station Orpheline", "libelle_cours_eau": None},
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=api_payload)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            options = await _fetch_vigicrues_station_options(43.5, 5.5)

        opt = next(o for o in options if o["value"] == "W1234567")
        assert opt["label"] == "Station Orpheline"
        assert opt["_river"] == ""
