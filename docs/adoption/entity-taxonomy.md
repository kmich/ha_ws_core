# Entity Taxonomy

The current integration creates 150+ entities, which is overwhelming for new users. To improve adoption and UX, we must enforce a strict taxonomy where only the most useful "Hero" and "Daily Use" entities are enabled by default. Everything else should be disabled by default or hidden as diagnostic entities.

## 1. Hero Entities (Default: ENABLED)
*These are the entities that sell the integration. They should be featured in the README and used in the main dashboard.*
* `sensor.ws_minutes_until_rain` (The killer feature)
* `sensor.ws_zambretti_forecast` (The offline oracle)
* `sensor.ws_current_condition` (For simple UI states)
* `binary_sensor.ws_rain_expected_1h` (For quick automations)
* `sensor.ws_fire_risk_score` (For safety alerts)
* `sensor.ws_et0_daily` (For smart irrigation)
* `sensor.ws_pollen_level` (If enabled via features)

## 2. Daily Use Entities (Default: ENABLED)
*These are the standard, clean meteorological values that users expect to see.*
* `sensor.ws_feels_like`
* `sensor.ws_wind_gust_max_24h`
* `sensor.ws_rain_today`
* `sensor.ws_rain_probability_combined`
* `sensor.ws_wind_beaufort`

## 3. Automation Entities (Default: ENABLED)
*These are specifically designed for triggering automations rather than viewing.*
* `sensor.ws_dry_streak` / `ws_heat_streak`
* `sensor.ws_pressure_trend` (Rising/Falling/Steady)
* `sensor.ws_lightning_proximity`

## 4. Advanced Scientific Entities (Default: DISABLED)
*These are factually correct and scientifically impressive, but useless to 95% of users. They clutter the UI and cause confusion. They must be disabled by default.*
* `sensor.ws_wet_bulb`
* `sensor.ws_frost_point`
* `sensor.ws_vpd` (Vapour Pressure Deficit)
* `sensor.ws_absolute_humidity`
* `sensor.ws_delta_t`
* `sensor.ws_air_density`
* `sensor.ws_specific_humidity`
* `sensor.ws_zambretti_number` (Keep the text forecast enabled, disable the raw Z-number)
* `sensor.ws_fwi_ffmc`, `ws_fwi_dmc`, etc. (Keep the top-level FWI score, hide the sub-components)

## 5. Diagnostic / Status Entities (Default: ENABLED, Category: Diagnostic)
*These should be hidden from the main dashboard but visible in the device page for troubleshooting.*
* `sensor.ws_forecast_agreement`
* `sensor.ws_sensor_drift`
* `sensor.ws_sensor_consistency`
* `sensor.ws_forecast_provider`
* `binary_sensor.ws_package_ok`

## Action Required
Update `entity_registry_enabled_default` in `sensor.py` and `binary_sensor.py` to `False` for all Category 4 (Advanced) entities. Add `entity_category = EntityCategory.DIAGNOSTIC` for all Category 5 entities.
