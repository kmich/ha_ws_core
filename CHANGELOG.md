# Changelog

## [0.2.0] - 2026-02-17

### Full Restoration - All Original Algorithms from v1.0.0-hotfix17

This release restores all sophisticated meteorological algorithms and sensors
that were missing since the HACS conversion from the original YAML package.

### Added (New Sensors - 29 sensors added)

**Meteorological Algorithms:**
- `ws_feels_like` - Australian Apparent Temperature (BOM standard: AT = Ta + 0.33*vp - 0.70*ws - 4.0)
- `ws_zambretti_forecast` - Zambretti barometric 6-12h forecast with regional wind pattern support
- `ws_wind_beaufort` - Beaufort wind scale (0-12) with description attribute
- `ws_wind_quadrant` - Wind direction quadrant (N/E/S/W)
- `ws_wind_direction_smooth` - Circular exponential smoothing (alpha=0.3, handles 360°/0° wraparound)
- `ws_current_condition` - 30+ weather condition classifier (sunny/cloudy/rainy/thunderstorm/etc.)
- `ws_rain_probability` - Local rain probability from pressure + trend + humidity + wind direction
- `ws_rain_probability_combined` - Time-weighted merge of local sensors + Open-Meteo API
- `ws_rain_display` - Formatted rain rate text (Dry / Drizzle / Light / Moderate / Heavy)
- `ws_pressure_trend` - Human-readable pressure trend (Rising Rapidly / Rising / Steady / Falling / Falling Rapidly)
- `ws_station_health` - Station health status (Online / Degraded / Stale / Offline)
- `ws_forecast_tiles` - 5-day forecast tile data with labels and weather codes

**24h Rolling Statistics:**
- `ws_temperature_high_24h` - 24-hour temperature maximum
- `ws_temperature_low_24h` - 24-hour temperature minimum
- `ws_temperature_avg_24h` - 24-hour temperature average
- `ws_wind_gust_max_24h` - 24-hour maximum wind gust

**Display/Level Sensors:**
- `ws_humidity_level` - Humidity level text (Very Dry / Dry / Comfortable / Humid / Very Humid)
- `ws_uv_level` - UV level text (Low / Moderate / High / Very High / Extreme)
- `ws_temperature_display` - Formatted temperature string

**Activity Optimization (disabled by default, enable in entity registry):**
- `ws_laundry_drying_score` - Score 0-100 with recommendation and estimated dry time
- `ws_stargazing_quality` - Quality rating with moon phase impact
- `ws_fire_weather_index` - Canadian FWI-based fire weather index with danger level

### Changed (Coordinator Enhancements)

- **Kalman filter** replaces simple EMA for rain rate smoothing (process_noise=0.01, measurement_noise=0.5)
- **Least-squares regression** replaces simple delta for pressure trend (12-sample, 15-min intervals = 3h window)
- **Circular wind averaging** for smooth direction tracking (no 360°/0° discontinuities)
- **Moon phase** computed from HA moon integration or astronomical fallback (Conway's algorithm)
- **Pressure history deque** (maxlen=12) samples every 15 minutes for proper 3h trend window
- **Forecast API** now fetches `precipitation_probability_max` for rain probability blending

### Fixed
- Wind Beaufort breakpoints corrected (were off by one scale step at boundary 1.5 m/s)
- Circular wind average now handles all wraparound cases correctly

### Internal (algorithms.py)
New standalone module with all meteorological functions, enabling unit testing:
- `calculate_apparent_temperature()` - BOM standard
- `zambretti_forecast()` - With 8 regional climate presets
- `calculate_rain_probability()` - 4-factor scoring (pressure, trend, humidity, wind)
- `combine_rain_probability()` - Time-weighted merge with morning/afternoon weighting
- `KalmanFilter` class - 1D filter with quality indicators
- `least_squares_pressure_trend()` - Linear regression over configurable window
- `smooth_wind_direction()` - Circular exponential smoothing
- `wind_speed_to_beaufort()`, `beaufort_description()` - Full 0-12 scale
- `determine_current_condition()` - 30+ condition classifier
- `laundry_drying_score()`, `running_score()`, `fire_weather_index()` - Activity scores
- `calculate_moon_phase()` - Astronomical fallback using Julian Day algorithm

---

## [0.1.2] - 2026-02-16

- Fixed deprecation warnings for HA 2026.2 compatibility
- Updated `weather.py` forecast imports

## [0.1.1] - 2026-02-15

- Initial HACS release
