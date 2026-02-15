"""Constants for Weather Station Core."""

DOMAIN = "ws_core"

PLATFORMS = ["sensor", "binary_sensor", "weather"]

CONF_NAME = "name"
CONF_PREFIX = "prefix"
CONF_SOURCES = "sources"
CONF_UNITS_MODE = "units_mode"  # auto|metric|imperial
CONF_ELEVATION_M = "elevation_m"
CONF_STALENESS_S = "staleness_s"
CONF_FORECAST_ENABLED = "forecast_enabled"
CONF_FORECAST_LAT = "forecast_lat"
CONF_FORECAST_LON = "forecast_lon"
CONF_FORECAST_INTERVAL_MIN = "forecast_interval_min"

# Alert & heuristic options (stored in canonical metric units)
CONF_THRESH_WIND_GUST_MS = "thresh_wind_gust_ms"
CONF_THRESH_RAIN_RATE_MMPH = "thresh_rain_rate_mmph"
CONF_THRESH_FREEZE_C = "thresh_freeze_c"
CONF_RAIN_FILTER_ALPHA = "rain_filter_alpha"
CONF_PRESSURE_TREND_WINDOW_H = "pressure_trend_window_h"
CONF_ENABLE_ACTIVITY_SCORES = "enable_activity_scores"
CONF_RAIN_PENALTY_LIGHT_MMPH = "rain_penalty_light_mmph"
CONF_RAIN_PENALTY_HEAVY_MMPH = "rain_penalty_heavy_mmph"


DEFAULT_NAME = "Weather Station"
DEFAULT_PREFIX = "ws"
DEFAULT_UNITS_MODE = "auto"
DEFAULT_ELEVATION_M = 0.0
DEFAULT_STALENESS_S = 900
DEFAULT_FORECAST_ENABLED = True
DEFAULT_FORECAST_INTERVAL_MIN = 30

# Defaults for alert/heuristic options
DEFAULT_THRESH_WIND_GUST_MS = 17.0
DEFAULT_THRESH_RAIN_RATE_MMPH = 20.0
DEFAULT_THRESH_FREEZE_C = 0.0
DEFAULT_RAIN_FILTER_ALPHA = 0.7
DEFAULT_PRESSURE_TREND_WINDOW_H = 3
DEFAULT_ENABLE_ACTIVITY_SCORES = False
DEFAULT_RAIN_PENALTY_LIGHT_MMPH = 0.2
DEFAULT_RAIN_PENALTY_HEAVY_MMPH = 5.0


# Canonical internal units
UNIT_TEMP_C = "°C"
UNIT_WIND_MS = "m/s"
UNIT_PRESSURE_HPA = "hPa"
UNIT_RAIN_MM = "mm"

# Keys used in coordinator.data
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
KEY_RAIN_RATE_RAW = "rain_rate_mmph_raw"
KEY_RAIN_RATE_FILT = "rain_rate_mmph_filtered"
KEY_ALERT_STATE = "alert_state"
KEY_ALERT_MESSAGE = "alert_message"
KEY_DATA_QUALITY = "data_quality"
KEY_PACKAGE_STATUS = "package_status"
KEY_PACKAGE_OK = "package_ok"
KEY_FORECAST = "forecast"

# Source mapping keys
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

REQUIRED_SOURCES = [SRC_TEMP, SRC_HUM, SRC_PRESS, SRC_WIND, SRC_GUST, SRC_WIND_DIR, SRC_RAIN_TOTAL]
OPTIONAL_SOURCES = [SRC_LUX, SRC_UV, SRC_DEW_POINT, SRC_BATTERY]

# Activity / derived heuristics (optional but included)
KEY_LAUNDRY_SCORE = "laundry_drying_score"
KEY_STARGAZE_SCORE = "stargazing_quality"
KEY_FIRE_SCORE = "fire_weather_score"
KEY_PRESSURE_TREND_HPAH = "pressure_trend_hpah"