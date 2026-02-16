# Weather Station Core (ws_core)

Home Assistant integration for comprehensive weather station data normalization and derived metrics.

## Features

- **Unified Data Model**: Normalizes data from various weather station sources
- **Derived Metrics**: Calculates dew point, sea-level pressure, pressure trends, rain rates
- **Weather Entity**: Standard HA weather entity with forecast support
- **Alerts**: Threshold-based alerts for wind, rain, temperature
- **Data Quality**: Monitors stale sensors and package health

## Compatibility

- **Home Assistant**: 2026.2+
- **Python**: 3.12+

## Installation

### Via HACS
1. Add custom repository: `https://github.com/kmich/ha_ws_core`
2. Search for "Weather Station Core"
3. Install and restart Home Assistant

### Manual
1. Copy `custom_components/ws_core` to your HA `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Settings → Devices & Services → Add Integration
2. Search "Weather Station Core"
3. Select source sensors (temperature, humidity, pressure, wind, rain, etc.)
4. Configure elevation and optional settings

## Sensors Created (21 total)

- Temperature, Humidity, Dew Point
- Station Pressure, Sea Level Pressure
- Pressure Trend, Pressure Change Window
- Wind Speed, Gust, Direction
- Rain Total, Rain Rate (raw), Rain Rate (filtered)
- Illuminance, UV Index, Battery
- Data Quality, Package Status
- Alert State, Alert Message
- Forecast Daily

Plus:
- Weather entity: `weather.ws`
- Binary sensor: `binary_sensor.ws_package_ok`

## Dashboard

Sample dashboard available in `dashboards/weather_dashboard.yaml`

To use:
1. Copy the YAML contents
2. Go to your dashboard → Edit → Raw Configuration Editor
3. Paste and save

## Support

GitHub Issues: https://github.com/kmich/ha_ws_core/issues

## License

MIT
