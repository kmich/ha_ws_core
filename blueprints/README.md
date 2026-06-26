# Weather Station Core - Example Blueprints

These are Home Assistant Blueprint automations that work with Weather Station Core sensors.

## Installation

1. Copy the desired `.yaml` file to your HA `config/blueprints/automation/ws_core/` directory
2. Restart Home Assistant (or reload automations)
3. Settings → Automations → Create Automation → Use Blueprint → select the blueprint
4. Fill in the options and save

## Available Blueprints

| Blueprint | Trigger | Description |
|---|---|---|
| `rain_start.yaml` | Rain rate or rain probability above threshold | Notify when rain starts (live gauge) or when forecast probability crosses a configurable level |
| `frost_alert.yaml` | `ws_frost_risk` reaches a configured level | Notify when frost/freeze risk is detected, with frost-point context and a cooldown |
| `freeze_alert.yaml` | Temperature drops below threshold | Simple temperature threshold alert - no optional sensors required |
| `storm_alert.yaml` | Rapid pressure drop (>1.6 hPa/h) | Alert when a storm front approaches, with rain probability + gust context |
| `high_wind.yaml` | Rapid pressure drop + wind gust above threshold | Storm warning combining pressure trend and measured gust speed |
| `irrigation_rain_skip.yaml` | Scheduled time | Run an irrigation zone on schedule, skipping if rain today or high rain probability |
| `lightning_safety.yaml` | Lightning proximity / clearance | "Near" and "all-clear" alerts; can switch off pool/outdoor equipment (needs `enable_lightning`) |
| `fire_danger_alert.yaml` | Fire Risk Score or FFDI above threshold | Alert on high fire danger; optional precautionary garden irrigation (needs `enable_fire_risk_score`) |
| `heat_stress.yaml` | UTCI above threshold | Alert when outdoor heat stress (Universal Thermal Climate Index) reaches a dangerous level |
| `poor_aqi.yaml` | AQI above threshold | Alert when air quality exceeds healthy levels; run actions like turning on air purifiers (needs `enable_air_quality`) |

## Notes

- Most blueprints take a `notify_target` (e.g. `notify.mobile_app_phone`); some default to a persistent notification. Set it to your mobile app notification service for push alerts.
- Entity IDs assume the default `ws` prefix. Adjust if you used a different prefix.
- Blueprints that depend on optional feature groups (lightning, fire risk) require that group to be enabled in the integration's Configure → Features step.
