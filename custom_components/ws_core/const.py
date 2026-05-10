"""Constants for Weather Station Core."""

DOMAIN = "ws_core"

PLATFORMS = ["sensor", "binary_sensor", "weather", "select", "switch", "number"]

# Config entry version - bump triggers async_migrate_entry
# v1: original
# v2: added hemisphere + climate_region (Claude 4.6 era)
# v3: v0.3.0 cleanup (entity registry purge + cut config keys)
ENTRY_VERSION = 3

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------
CONF_NAME = "name"
CONF_PREFIX = "prefix"
CONF_SOURCES = "sources"
CONF_UNITS_MODE = "units_mode"
CONF_TEMP_UNIT = "temp_unit"
CONF_ELEVATION_M = "elevation_m"
CONF_HEMISPHERE = "hemisphere"
CONF_CLIMATE_REGION = "climate_region"
CONF_STALENESS_S = "staleness_s"
CONF_FORECAST_ENABLED = "forecast_enabled"
CONF_FORECAST_LAT = "forecast_lat"
CONF_FORECAST_LON = "forecast_lon"
CONF_FORECAST_INTERVAL_MIN = "forecast_interval_min"

# Alert & heuristic options
CONF_THRESH_WIND_GUST_MS = "thresh_wind_gust_ms"
CONF_THRESH_RAIN_RATE_MMPH = "thresh_rain_rate_mmph"
CONF_THRESH_FREEZE_C = "thresh_freeze_c"
CONF_RAIN_FILTER_ALPHA = "rain_filter_alpha"
CONF_PRESSURE_TREND_WINDOW_H = "pressure_trend_window_h"

# Granular feature toggles
# v0.3.0 cleanup: removed CONF_ENABLE_LAUNDRY/STARGAZING/RUNNING/DEGREE_DAYS/METAR/CWOP/EXPORT
# v0.3.0 cleanup: removed CONF_ENABLE_ACTIVITY_SCORES, CONF_ENABLE_EXTENDED_SENSORS (coarse toggles)
CONF_ENABLE_ZAMBRETTI = "enable_zambretti"
CONF_ENABLE_DISPLAY_SENSORS = "enable_display_sensors"
CONF_ENABLE_FIRE_RISK = "enable_fire_risk_score"
CONF_RAIN_PENALTY_LIGHT_MMPH = "rain_penalty_light_mmph"
CONF_RAIN_PENALTY_HEAVY_MMPH = "rain_penalty_heavy_mmph"
CONF_ENABLE_THUNDERSTORM = "enable_thunderstorm_risk"
CONF_ENABLE_FOG = "enable_fog_probability"
CONF_ENABLE_SEA_TEMP = "enable_sea_temp"
CONF_SEA_TEMP_LAT = "sea_temp_lat"
CONF_SEA_TEMP_LON = "sea_temp_lon"

# v0.3.0: WeatherUnderground retained as disabled-by-default (v0.6 roadmap)
CONF_ENABLE_WUNDERGROUND = "enable_wunderground"
CONF_WU_STATION_ID = "wu_station_id"
CONF_WU_API_KEY = "wu_api_key"
CONF_WU_INTERVAL_MIN = "wu_interval_min"

# Air Quality + pollen (now both via Open-Meteo Air Quality API)
CONF_ENABLE_AIR_QUALITY = "enable_air_quality"
CONF_ENABLE_POLLEN = "enable_pollen"
CONF_AQI_INTERVAL_MIN = "aqi_interval_min"

# Moon
CONF_ENABLE_MOON = "enable_moon"

# Solar forecast (forecast.solar)
CONF_ENABLE_SOLAR_FORECAST = "enable_solar_forecast"
CONF_SOLAR_PEAK_KW = "solar_peak_kw"
CONF_SOLAR_PANEL_AZIMUTH = "solar_panel_azimuth"
CONF_SOLAR_PANEL_TILT = "solar_panel_tilt"
CONF_SOLAR_INTERVAL_MIN = "solar_interval_min"

# Streak threshold (was previously bundled with degree days; kept for streak features)
CONF_THRESH_HEAT_DAY_C = "thresh_heat_day_c"

# Calibration offsets
CONF_CAL_TEMP_C = "cal_temp_c"
CONF_CAL_HUMIDITY = "cal_humidity"
CONF_CAL_PRESSURE_HPA = "cal_pressure_hpa"
CONF_CAL_WIND_MS = "cal_wind_ms"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_NAME = "Weather Station"
DEFAULT_PREFIX = "ws"
DEFAULT_UNITS_MODE = "auto"
DEFAULT_TEMP_UNIT = "auto"
DEFAULT_ELEVATION_M = 0.0
DEFAULT_HEMISPHERE = "Northern"
DEFAULT_CLIMATE_REGION = "Atlantic Europe"
DEFAULT_STALENESS_S = 900
DEFAULT_FORECAST_ENABLED = True
DEFAULT_FORECAST_INTERVAL_MIN = 30

DEFAULT_THRESH_WIND_GUST_MS = 17.0
DEFAULT_THRESH_RAIN_RATE_MMPH = 20.0
DEFAULT_THRESH_FREEZE_C = 0.0
DEFAULT_RAIN_FILTER_ALPHA = 0.7
DEFAULT_PRESSURE_TREND_WINDOW_H = 3
DEFAULT_RAIN_PENALTY_LIGHT_MMPH = 0.5
DEFAULT_RAIN_PENALTY_HEAVY_MMPH = 5.0

DEFAULT_ENABLE_ZAMBRETTI = True
DEFAULT_ENABLE_DISPLAY_SENSORS = True
DEFAULT_ENABLE_FIRE_RISK = False
DEFAULT_ENABLE_THUNDERSTORM = False
DEFAULT_ENABLE_FOG = False
DEFAULT_ENABLE_SEA_TEMP = False
DEFAULT_ENABLE_WUNDERGROUND = False
DEFAULT_WU_INTERVAL_MIN = 5
DEFAULT_ENABLE_AIR_QUALITY = False
DEFAULT_AQI_INTERVAL_MIN = 60
DEFAULT_ENABLE_POLLEN = False
DEFAULT_ENABLE_MOON = False
DEFAULT_ENABLE_SOLAR_FORECAST = False
DEFAULT_SOLAR_PEAK_KW = 5.0
DEFAULT_SOLAR_PANEL_AZIMUTH = 180.0
DEFAULT_SOLAR_PANEL_TILT = 30.0
DEFAULT_SOLAR_INTERVAL_MIN = 60
DEFAULT_THRESH_HEAT_DAY_C = 30.0

DEFAULT_CAL_TEMP_C = 0.0
DEFAULT_CAL_HUMIDITY = 0.0
DEFAULT_CAL_PRESSURE_HPA = 0.0
DEFAULT_CAL_WIND_MS = 0.0

# ---------------------------------------------------------------------------
# Selectable option lists
# ---------------------------------------------------------------------------
HEMISPHERE_OPTIONS = ["Northern", "Southern"]

CLIMATE_REGION_OPTIONS = [
    "Atlantic Europe",
    "Mediterranean",
    "Continental Europe",
    "Scandinavia",
    "North America East",
    "North America West",
    "Australia",
    "Custom",
]

UNITS_MODE_OPTIONS = ["auto", "metric", "imperial"]
TEMP_UNIT_OPTIONS = ["auto", "C", "F"]

# ---------------------------------------------------------------------------
# Physical validation limits (WMO / ICAO records)
# ---------------------------------------------------------------------------
VALID_TEMP_MIN_C = -60.0
VALID_TEMP_MAX_C = 60.0
VALID_TEMP_WARN_MIN_C = -40.0
VALID_TEMP_WARN_MAX_C = 50.0

VALID_PRESSURE_MIN_HPA = 870.0
VALID_PRESSURE_MAX_HPA = 1085.0
VALID_PRESSURE_WARN_MIN_HPA = 940.0
VALID_PRESSURE_WARN_MAX_HPA = 1060.0

VALID_ELEVATION_MIN_M = -500.0
VALID_ELEVATION_MAX_M = 9000.0

VALID_HUMIDITY_MIN = 0.0
VALID_HUMIDITY_MAX = 100.0

VALID_WIND_GUST_MAX_MS = 113.0
VALID_RAIN_RATE_MAX_MMPH = 500.0

# ---------------------------------------------------------------------------
# Canonical internal units
# ---------------------------------------------------------------------------
UNIT_TEMP_C = "\u00b0C"
UNIT_WIND_MS = "m/s"
UNIT_PRESSURE_HPA = "hPa"
UNIT_RAIN_MM = "mm"
UNIT_RAIN_MMPH = "mm/h"
UNIT_HUMIDITY_PCT = "%"
UNIT_BATTERY_PCT = "%"
UNIT_LUX = "lx"
UNIT_DEG = "\u00b0"
UNIT_KMH = "km/h"
UNIT_HPA_PER_H = "hPa/h"

# ---------------------------------------------------------------------------
# Source roles (kept original SRC_ naming for compat with config_flow/__init__)
# ---------------------------------------------------------------------------
SRC_TEMP = "temperature"
SRC_HUM = "humidity"
SRC_PRESS = "pressure"
SRC_WIND = "wind_speed"
SRC_GUST = "wind_gust"
SRC_WIND_DIR = "wind_direction"
SRC_RAIN_TOTAL = "rain_total"
SRC_LUX = "illuminance"
SRC_UV = "uv_index"
SRC_DEW_POINT = "dew_point"
SRC_BATTERY = "battery"
SRC_SOLAR_RADIATION = "solar_radiation"

REQUIRED_SOURCES = [SRC_TEMP, SRC_HUM, SRC_PRESS, SRC_WIND, SRC_GUST, SRC_WIND_DIR, SRC_RAIN_TOTAL]
OPTIONAL_SOURCES = [SRC_LUX, SRC_UV, SRC_DEW_POINT, SRC_BATTERY, SRC_SOLAR_RADIATION]

# Coordinator tuning constants
PRESSURE_HISTORY_INTERVAL_MIN = 5
PRESSURE_HISTORY_SAMPLES = 36  # 3 h × 60 / 5 min
RAIN_RATE_PHYSICAL_CAP_MMPH = 500.0
WIND_SMOOTH_ALPHA = 0.15
LEARNING_SAVE_INTERVAL_S = 3600
# Sources checked for staleness; excludes rain_total (static when dry), UV/lux (zero at night), battery
STALENESS_CHECK_SOURCES = {SRC_TEMP, SRC_HUM, SRC_PRESS, SRC_WIND, SRC_GUST, SRC_WIND_DIR}

# ROLE_* aliases (mine; coordinator.py uses these names internally now)
ROLE_TEMPERATURE = SRC_TEMP
ROLE_HUMIDITY = SRC_HUM
ROLE_PRESSURE = SRC_PRESS
ROLE_WIND_SPEED = SRC_WIND
ROLE_WIND_GUST = SRC_GUST
ROLE_WIND_DIR = SRC_WIND_DIR
ROLE_RAIN_TOTAL = SRC_RAIN_TOTAL
ROLE_LUX = SRC_LUX
ROLE_UV = SRC_UV
ROLE_BATTERY = SRC_BATTERY
REQUIRED_ROLES = REQUIRED_SOURCES
OPTIONAL_ROLES = OPTIONAL_SOURCES

# CONFIG_VERSION is the canonical name in __init__.py and config_flow.py;
# ENTRY_VERSION is an alias used in this v0.3.0 cleanup.
CONFIG_VERSION = ENTRY_VERSION

# ---------------------------------------------------------------------------
# Data keys (in coordinator.data)
# ---------------------------------------------------------------------------
KEY_NORM_TEMP_C = "norm_temperature_c"
KEY_NORM_HUMIDITY = "norm_humidity"
KEY_NORM_PRESSURE_HPA = "norm_pressure_hpa"
KEY_SEA_LEVEL_PRESSURE_HPA = "sea_level_pressure_hpa"
KEY_PRESSURE_CHANGE_WINDOW_HPA = "pressure_change_window_hpa"
KEY_NORM_WIND_SPEED_MS = "norm_wind_speed_ms"
KEY_NORM_WIND_GUST_MS = "norm_wind_gust_ms"
KEY_NORM_WIND_DIR_DEG = "norm_wind_dir_deg"
KEY_NORM_RAIN_TOTAL_MM = "norm_rain_total_mm"
KEY_DEW_POINT_C = "dew_point_c"
KEY_LUX = "illuminance_lx"
KEY_UV = "uv_index"
KEY_BATTERY_PCT = "battery_pct"
# v0.3.0: removed KEY_RAIN_RATE_RAW (cut - filtered only)
KEY_RAIN_RATE_FILT = "rain_rate_mmph_filtered"
KEY_ALERT_STATE = "alert_state"
KEY_ALERT_MESSAGE = "alert_message"
KEY_DATA_QUALITY = "data_quality"
KEY_PACKAGE_STATUS = "package_status"
KEY_PACKAGE_OK = "package_ok"
KEY_FORECAST = "forecast"

# Derived
KEY_FEELS_LIKE_C = "feels_like_c"
KEY_WET_BULB_C = "wet_bulb_c"
KEY_FROST_POINT_C = "frost_point_c"
KEY_ZAMBRETTI_FORECAST = "zambretti_forecast"
KEY_ZAMBRETTI_NUMBER = "zambretti_number"
KEY_WIND_BEAUFORT = "wind_beaufort"
KEY_WIND_BEAUFORT_DESC = "wind_beaufort_desc"
KEY_WIND_QUADRANT = "wind_quadrant"
KEY_WIND_DIR_SMOOTH_DEG = "wind_dir_smooth_deg"
KEY_CURRENT_CONDITION = "current_condition"
KEY_RAIN_PROBABILITY = "rain_probability"
KEY_RAIN_PROBABILITY_COMBINED = "rain_probability_combined"
KEY_RAIN_DISPLAY = "rain_display"
KEY_RAIN_ACCUM_1H = "rain_accum_1h_mm"
KEY_RAIN_ACCUM_24H = "rain_accum_24h_mm"
# v0.3.0: removed KEY_TIME_SINCE_RAIN (overlaps with dry_streak)
KEY_PRESSURE_TREND_DISPLAY = "pressure_trend_display"
KEY_HEALTH_DISPLAY = "health_display"
KEY_FORECAST_TILES = "forecast_tiles"

# 24h stats (RestoreSensor-backed in v0.3.0)
KEY_TEMP_HIGH_24H = "temp_high_24h"
KEY_TEMP_LOW_24H = "temp_low_24h"
KEY_TEMP_AVG_24H = "temp_avg_24h"
KEY_WIND_GUST_MAX_24H = "wind_gust_max_24h"

# Display strings
KEY_UV_LEVEL_DISPLAY = "uv_level_display"
KEY_HUMIDITY_LEVEL_DISPLAY = "humidity_level_display"
KEY_TEMP_DISPLAY = "temp_display"
KEY_BATTERY_DISPLAY = "battery_display"

# Risk / activity scores
# v0.3.0: kept fire_risk + thunderstorm_risk + fog_probability
# v0.3.0: cut laundry, stargazing, running
KEY_FIRE_RISK_SCORE = "fire_risk_score"
KEY_FOG_PROBABILITY = "fog_probability"
KEY_THUNDERSTORM_RISK = "thunderstorm_risk"

KEY_PRESSURE_TREND_HPAH = "pressure_trend_hpah"

# Sea surface temperature
KEY_SEA_SURFACE_TEMP = "sea_surface_temperature"

KEY_SENSOR_QUALITY_FLAGS = "sensor_quality_flags"

# v0.3.0 removed: degree-days (HDD, CDD, GDD), METAR family, CWOP_STATUS, LAST_EXPORT_TIME

# v0.3.0: WU status retained but disabled-by-default
KEY_WU_STATUS = "wu_upload_status"

# ET0 daily (Hargreaves-Samani)
KEY_ET0_DAILY_MM = "et0_daily_mm"
KEY_ET0_HOURLY_MM = "et0_hourly_mm"

# Air quality (Open-Meteo Air Quality API)
KEY_AQI = "air_quality_index"
# v0.3.0: removed KEY_AQI_LEVEL (was duplicate; level is attribute)
KEY_PM2_5 = "pm2_5_ug_m3"
KEY_PM10 = "pm10_ug_m3"
KEY_NO2 = "no2_ug_m3"
KEY_OZONE = "ozone_ug_m3"
KEY_CO = "co_ug_m3"

# Pollen (v0.3.0: now via Open-Meteo Air Quality API)
KEY_POLLEN_GRASS = "pollen_grass_index"
KEY_POLLEN_TREE = "pollen_tree_index"
KEY_POLLEN_WEED = "pollen_weed_index"
KEY_POLLEN_OVERALL = "pollen_overall_level"

# Moon (v0.3.0: KEY_MOON_PHASE removed - phase is attribute on KEY_MOON_DISPLAY)
KEY_MOON_ILLUMINATION_PCT = "moon_illumination_pct"
KEY_MOON_DISPLAY = "moon_display"
KEY_MOON_AGE_DAYS = "moon_age_days"
KEY_MOON_NEXT_FULL = "moon_next_full_days"
KEY_MOON_NEXT_NEW = "moon_next_new_days"

# Solar forecast
KEY_SOLAR_FORECAST_TODAY_KWH = "solar_forecast_today_kwh"
KEY_SOLAR_FORECAST_TOMORROW_KWH = "solar_forecast_tomorrow_kwh"
KEY_SOLAR_FORECAST_STATUS = "solar_forecast_status"
KEY_ET0_PM_DAILY_MM = "et0_pm_daily_mm"

# Learning state - v0.3.0: METAR-related fields removed
KEY_FORECAST_SKILL = "forecast_skill"
KEY_SOLAR_LUX_FACTOR = "solar_lux_factor"

# Streaks (RestoreSensor-backed in v0.3.0)
KEY_DRY_STREAK = "dry_streak_days"
KEY_HEAT_STREAK = "heat_streak_days"
KEY_FROST_STREAK = "frost_streak_days"

KEY_SENSOR_DRIFT_FLAGS = "sensor_drift_flags"
KEY_CONSISTENCY_FLAGS = "consistency_flags"

# Anomalies - kept disabled-by-default until climatology baseline implemented
KEY_CLIMATOLOGY_30D = "climatology_30d"
KEY_TEMP_ANOMALY_30D = "temp_anomaly_30d"
KEY_RAIN_ANOMALY_30D = "rain_anomaly_30d"

# ---------------------------------------------------------------------------
# v0.3.0 migration data
# Used by async_migrate_entry to clean up the entity registry.
# ---------------------------------------------------------------------------
DEPRECATED_KEYS_V030 = (
    # METAR family (7 sensors)
    "metar_validation",
    "metar_delta_temp_c",
    "metar_delta_pressure_hpa",
    "learned_temp_bias",
    "cal_suggestion_temp",
    "learned_pressure_bias",
    "cal_suggestion_pressure",
    # Roadmap-but-not-built
    "last_export_time",
    "cwop_upload_status",
    # Lifestyle scores
    "running_score",
    "laundry_drying_score",
    "stargazing_quality",
    # Degree days (4)
    "gdd_today",
    "gdd_season",
    "hdd_today",
    "cdd_today",
    # Redundancies
    "moon_phase",
    "air_quality_level",
    "pressure_trend_hpah_raw",
    "rain_rate_mmph_raw",
    "precipitation_type",
    "time_since_rain",
)

# Deprecated config keys to scrub from entry data on migration
DEPRECATED_CONF_KEYS_V030 = (
    "enable_laundry_score",
    "enable_stargazing_score",
    "enable_running_score",
    "enable_degree_days",
    "degree_day_base_c",
    "enable_metar",
    "metar_icao",
    "metar_interval_min",
    "enable_cwop",
    "cwop_callsign",
    "cwop_passcode",
    "cwop_interval_min",
    "enable_export",
    "export_path",
    "export_format",
    "export_interval_min",
    "enable_activity_scores",
    "enable_extended_sensors",
    "rain_penalty_light_mmph",
    "rain_penalty_heavy_mmph",
)
