# Weather Station Core — Example Blueprints

These are Home Assistant Blueprint automations that work with Weather Station Core sensors.

## Installation

1. Copy the desired `.yaml` file to your HA `config/blueprints/automation/ws_core/` directory
2. Restart Home Assistant (or reload automations)
3. Settings → Automations → Create Automation → Use Blueprint → select the blueprint
4. Fill in the options and save

## Available Blueprints

| Blueprint | Trigger | Description |
|---|---|---|
| `frost_alert.yaml` | Temperature below threshold | Notify when frost risk is detected |
| `rain_notification.yaml` | Rain rate or probability | Notify when rain starts or is imminent |
| `laundry_reminder.yaml` | Daily time check | Morning notification when drying conditions are excellent |
| `storm_warning.yaml` | Rapid pressure drop + high wind | Alert when a storm front approaches |

## Notes

- The **laundry reminder** requires activity scores to be enabled in the integration options.
- All blueprints default to `notify.persistent_notification`. Change to your mobile app notification service for push alerts.
- Entity IDs assume the default `ws` prefix. Adjust if you used a different prefix.
