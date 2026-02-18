"""Constants for Weather Station Core."""

DOMAIN = "ws_core"

PLATFORMS = ["sensor", "binary_sensor", "weather", "select", "switch"]

# ---------------------------------------------------------------------------
# Configuration keys
# ---------------------------------------------------------------------------
CONF_NAME = "name"
CONF_PREFIX = "prefix"
CONF_SOURCES = "sources"
CONF_UNITS_MODE = "units_mode"  # auto | metric | imperial
CONF_TEMP_UNIT = "temp_unit"  # auto | C | F
CONF_ELEVATION_M = "elevation_m"
CONF_HEMISPHERE = "hemisphere"  # Northern | Southern
CONF_CLIMATE_REGION = "climate_region"  # for Zambretti wind pattern
CONF_STALENESS_S = "staleness_s"
CONF_FORECAST_ENABLED = "forecast_enabled"
CONF_FORECAST_LAT = "forecast_lat"
CONF_FORECAST_LON = "forecast_lon"
CONF_FORECAST_INTERVAL_MIN = "forecast_interval_min"

# Alert & heuristic options (stored in canonical metric units internally)
CONF_THRESH_WIND_GUST_MS = "thresh_wind_gust_ms"
CONF_THRESH_RAIN_RATE_MMPH = "thresh_rain_rate_mmph"
CONF_THRESH_FREEZE_C = "thresh_freeze_c"
CONF_RAIN_FILTER_ALPHA = "rain_filter_alpha"
CONF_PRESSURE_TREND_WINDOW_H = "pressure_trend_window_h"
CONF_ENABLE_ACTIVITY_SCORES = "enable_activity_scores"
CONF_ENABLE_EXTENDED_SENSORS = "enable_extended_sensors"

# Granular feature toggles (override the coarse group toggles above)
CONF_ENABLE_ZAMBRETTI = "enable_zambretti"
CONF_ENABLE_DISPLAY_SENSORS = "enable_display_sensors"
CONF_ENABLE_LAUNDRY = "enable_laundry_score"
CONF_ENABLE_STARGAZING = "enable_stargazing_score"
CONF_ENABLE_FIRE_RISK = "enable_fire_risk_score"
CONF_ENABLE_RUNNING = "enable_running_score"
CONF_ENABLE_SEA_TEMP = "enable_sea_temp"
CONF_SEA_TEMP_LAT = "sea_temp_lat"
CONF_SEA_TEMP_LON = "sea_temp_lon"
CONF_RAIN_PENALTY_LIGHT_MMPH = "rain_penalty_light_mmph"
CONF_RAIN_PENALTY_HEAVY_MMPH = "rain_penalty_heavy_mmph"

# Degree days (v0.5.0)
CONF_ENABLE_DEGREE_DAYS = "enable_degree_days"
CONF_DEGREE_DAY_BASE_C = "degree_day_base_c"

# METAR cross-validation (v0.5.0)
CONF_ENABLE_METAR = "enable_metar"
CONF_METAR_ICAO = "metar_icao"
CONF_METAR_INTERVAL_MIN = "metar_interval_min"

# v0.6.0 CWOP upload
CONF_ENABLE_CWOP = "enable_cwop"
CONF_CWOP_CALLSIGN = "cwop_callsign"
CONF_CWOP_PASSCODE = "cwop_passcode"
CONF_CWOP_INTERVAL_MIN = "cwop_interval_min"

# v0.6.0 Weather Underground upload
CONF_ENABLE_WUNDERGROUND = "enable_wunderground"
CONF_WU_STATION_ID = "wu_station_id"
CONF_WU_API_KEY = "wu_api_key"
CONF_WU_INTERVAL_MIN = "wu_interval_min"

# v0.6.0 CSV/JSON export
CONF_ENABLE_EXPORT = "enable_export"
CONF_EXPORT_PATH = "export_path"
CONF_EXPORT_FORMAT = "export_format"
CONF_EXPORT_INTERVAL_MIN = "export_interval_min"

# Calibration offsets (applied after unit conversion, in canonical metric units)
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
DEFAULT_ENABLE_ACTIVITY_SCORES = False
DEFAULT_ENABLE_EXTENDED_SENSORS = True

DEFAULT_ENABLE_ZAMBRETTI = True
DEFAULT_ENABLE_DISPLAY_SENSORS = True
DEFAULT_ENABLE_LAUNDRY = False
DEFAULT_ENABLE_STARGAZING = False
DEFAULT_ENABLE_FIRE_RISK = False
DEFAULT_ENABLE_RUNNING = False
DEFAULT_ENABLE_SEA_TEMP = False
DEFAULT_RAIN_PENALTY_LIGHT_MMPH = 0.2
DEFAULT_RAIN_PENALTY_HEAVY_MMPH = 5.0

# Degree days defaults
DEFAULT_ENABLE_DEGREE_DAYS = False
DEFAULT_DEGREE_DAY_BASE_C = 18.0

# METAR defaults
DEFAULT_ENABLE_METAR = False
DEFAULT_METAR_INTERVAL_MIN = 60

# v0.6.0 defaults
DEFAULT_ENABLE_CWOP = False
DEFAULT_CWOP_INTERVAL_MIN = 10
DEFAULT_ENABLE_WUNDERGROUND = False
DEFAULT_WU_INTERVAL_MIN = 5
DEFAULT_ENABLE_EXPORT = False
DEFAULT_EXPORT_FORMAT = "csv"
DEFAULT_EXPORT_INTERVAL_MIN = 60

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

# ---------------------------------------------------------------------------
# Coordinator data keys - BASIC SENSORS
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
KEY_RAIN_RATE_RAW = "rain_rate_mmph_raw"
KEY_RAIN_RATE_FILT = "rain_rate_mmph_filtered"
KEY_ALERT_STATE = "alert_state"
KEY_ALERT_MESSAGE = "alert_message"
KEY_DATA_QUALITY = "data_quality"
KEY_PACKAGE_STATUS = "package_status"
KEY_PACKAGE_OK = "package_ok"
KEY_FORECAST = "forecast"

# Keys for ADVANCED METEOROLOGICAL SENSORS
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
KEY_TIME_SINCE_RAIN = "time_since_rain"
KEY_PRESSURE_TREND_DISPLAY = "pressure_trend_display"
KEY_HEALTH_DISPLAY = "health_display"
KEY_FORECAST_TILES = "forecast_tiles"

# Keys for 24H STATISTICS
KEY_TEMP_HIGH_24H = "temp_high_24h"
KEY_TEMP_LOW_24H = "temp_low_24h"
KEY_TEMP_AVG_24H = "temp_avg_24h"
KEY_WIND_GUST_MAX_24H = "wind_gust_max_24h"

# Keys for DISPLAY/FORMAT SENSORS
KEY_UV_LEVEL_DISPLAY = "uv_level_display"
KEY_HUMIDITY_LEVEL_DISPLAY = "humidity_level_display"
KEY_TEMP_DISPLAY = "temp_display"
KEY_BATTERY_DISPLAY = "battery_display"

# Activity / derived heuristics (optional, disabled by default)
KEY_LAUNDRY_SCORE = "laundry_drying_score"
KEY_STARGAZE_SCORE = "stargazing_quality"
KEY_FIRE_RISK_SCORE = "fire_risk_score"
KEY_RUNNING_SCORE = "running_score"
KEY_PRESSURE_TREND_HPAH = "pressure_trend_hpah"

# Sea surface temperature (Open-Meteo Marine API)
KEY_SEA_SURFACE_TEMP = "sea_surface_temperature"

# Sensor quality / validation flags
KEY_SENSOR_QUALITY_FLAGS = "sensor_quality_flags"

# Degree days (v0.5.0)
KEY_HDD_TODAY = "hdd_today"
KEY_CDD_TODAY = "cdd_today"
KEY_HDD_RATE = "hdd_rate"
KEY_CDD_RATE = "cdd_rate"

# METAR cross-validation (v0.5.0)
KEY_METAR_TEMP_C = "metar_temp_c"
KEY_METAR_PRESSURE_HPA = "metar_pressure_hpa"
KEY_METAR_WIND_MS = "metar_wind_ms"
KEY_METAR_WIND_DIR = "metar_wind_dir_deg"
KEY_METAR_CONDITION = "metar_condition"
KEY_METAR_DELTA_TEMP = "metar_delta_temp_c"
KEY_METAR_DELTA_PRESSURE = "metar_delta_pressure_hpa"
KEY_METAR_VALIDATION = "metar_validation"
KEY_METAR_STATION = "metar_station_id"
KEY_METAR_AGE_MIN = "metar_age_min"

# ET₀ irrigation (v0.6.0)
KEY_ET0_DAILY_MM = "et0_daily_mm"
KEY_ET0_HOURLY_MM = "et0_hourly_mm"

# Upload status (v0.6.0)
KEY_CWOP_STATUS = "cwop_upload_status"
KEY_WU_STATUS = "wu_upload_status"
KEY_LAST_EXPORT_TIME = "last_export_time"

# ---------------------------------------------------------------------------
# Source mapping keys
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

REQUIRED_SOURCES = [SRC_TEMP, SRC_HUM, SRC_PRESS, SRC_WIND, SRC_GUST, SRC_WIND_DIR, SRC_RAIN_TOTAL]
OPTIONAL_SOURCES = [SRC_LUX, SRC_UV, SRC_DEW_POINT, SRC_BATTERY]

# Only these sources trigger staleness warnings. Excluded: rain_total (static
# when dry), lux/uv (zero at night), dew_point, battery (slow-reporting).
STALENESS_CHECK_SOURCES = {SRC_TEMP, SRC_HUM, SRC_PRESS, SRC_WIND, SRC_GUST, SRC_WIND_DIR}

# ---------------------------------------------------------------------------
# Named physical / algorithm constants
# ---------------------------------------------------------------------------
SLP_GAS_CONSTANT_RATIO: float = 29.263

MAGNUS_A: float = 17.625
MAGNUS_B: float = 243.04

MAGNUS_A_ICE: float = 22.587
MAGNUS_B_ICE: float = 273.86

BEAUFORT_BOUNDARIES = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]

PRESSURE_HISTORY_SAMPLES = 12
PRESSURE_HISTORY_INTERVAL_MIN = 15

PRESSURE_TREND_RISING_RAPID: float = 1.6
PRESSURE_TREND_RISING: float = 0.8
PRESSURE_TREND_FALLING: float = -0.8
PRESSURE_TREND_FALLING_RAPID: float = -1.6

RAIN_RATE_PHYSICAL_CAP_MMPH: float = 500.0
WIND_SMOOTH_ALPHA: float = 0.3

ZAMBRETTI_UPPER_PRESSURE: float = 1050.0
ZAMBRETTI_LOWER_PRESSURE: float = 950.0

FORECAST_MIN_RETRY_S: int = 300
FORECAST_MAX_RETRY_S: int = 3600

CONFIG_VERSION = 2
