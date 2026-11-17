"""Provider capability matrix for forecast evaluation and weather windows (v3.0)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities and resolution of a forecast provider."""

    provider_id: str
    display_name: str
    hourly_horizon_h: int
    has_temp: bool = True
    has_dewpoint: bool = True
    has_apparent_temp: bool = True
    has_precip_probability: bool = True
    has_precip_amount: bool = True
    has_cloud_cover: bool = True
    has_wind_gust: bool = True
    update_cadence_min: int = 60


PROVIDER_CAPABILITY_MATRIX: dict[str, ProviderCapabilities] = {
    "open_meteo": ProviderCapabilities(
        provider_id="open_meteo",
        display_name="Open-Meteo",
        hourly_horizon_h=24,
        has_temp=True,
        has_dewpoint=True,
        has_apparent_temp=True,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=True,
        has_wind_gust=True,
        update_cadence_min=60,
    ),
    "met_no": ProviderCapabilities(
        provider_id="met_no",
        display_name="Met.no",
        hourly_horizon_h=24,
        has_temp=True,
        has_dewpoint=True,
        has_apparent_temp=False,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=True,
        has_wind_gust=True,
        update_cadence_min=60,
    ),
    "open_weather_map": ProviderCapabilities(
        provider_id="open_weather_map",
        display_name="OpenWeatherMap",
        hourly_horizon_h=48,
        has_temp=True,
        has_dewpoint=True,
        has_apparent_temp=True,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=True,
        has_wind_gust=True,
        update_cadence_min=30,
    ),
    "pirate_weather": ProviderCapabilities(
        provider_id="pirate_weather",
        display_name="Pirate Weather",
        hourly_horizon_h=48,
        has_temp=True,
        has_dewpoint=True,
        has_apparent_temp=True,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=True,
        has_wind_gust=True,
        update_cadence_min=30,
    ),
    "nws_noaa": ProviderCapabilities(
        provider_id="nws_noaa",
        display_name="NWS / NOAA",
        hourly_horizon_h=24,
        has_temp=True,
        has_dewpoint=True,
        has_apparent_temp=True,
        has_precip_probability=True,
        has_precip_amount=False,
        has_cloud_cover=False,
        has_wind_gust=True,
        update_cadence_min=60,
    ),
    "meteo_france": ProviderCapabilities(
        provider_id="meteo_france",
        display_name="Météo-France",
        hourly_horizon_h=24,
        has_temp=True,
        has_dewpoint=False,
        has_apparent_temp=True,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=True,
        has_wind_gust=True,
        update_cadence_min=60,
    ),
    "ha_weather_entity": ProviderCapabilities(
        provider_id="ha_weather_entity",
        display_name="Home Assistant Weather Entity",
        hourly_horizon_h=24,
        has_temp=True,
        has_dewpoint=False,
        has_apparent_temp=False,
        has_precip_probability=True,
        has_precip_amount=True,
        has_cloud_cover=False,
        has_wind_gust=False,
        update_cadence_min=30,
    ),
}

DEFAULT_CAPABILITIES = ProviderCapabilities(
    provider_id="unknown",
    display_name="Generic Provider",
    hourly_horizon_h=24,
    has_temp=True,
    has_dewpoint=False,
    has_apparent_temp=False,
    has_precip_probability=False,
    has_precip_amount=False,
    has_cloud_cover=False,
    has_wind_gust=False,
    update_cadence_min=60,
)


def get_provider_capabilities(provider_id: str | None) -> ProviderCapabilities:
    """Return declared capabilities for provider_id, or conservative defaults."""
    if not provider_id:
        return DEFAULT_CAPABILITIES
    canonical = provider_id.replace("-", "_").lower()
    return PROVIDER_CAPABILITY_MATRIX.get(canonical, DEFAULT_CAPABILITIES)
