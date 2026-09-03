# Use Cases

Start here if you installed Weather Station Core and want a useful automation in
the next 10 minutes.

All examples assume the default `ws` entity prefix. If you chose a different
prefix during setup, replace `sensor.ws_...` with your own entity IDs.

---

## Know before rain starts

Best for: laundry outside, skylights, open windows, dog walks, school pickup.

Enable **Precipitation Nowcast** under **Configure -> Features**. This creates
`sensor.ws_minutes_until_rain`.

```yaml
alias: Rain starts soon
description: Notify when Weather Station Core expects rain within 10 minutes.
mode: single
trigger:
  - platform: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    below: 10
condition:
  - condition: numeric_state
    entity_id: sensor.ws_minutes_until_rain
    above: 0
action:
  - service: notify.mobile_app_your_phone
    data:
      title: Rain soon
      message: Rain is expected in {{ states('sensor.ws_minutes_until_rain') }} minutes.
```

Prefer no YAML? Import the bundled
[Rain Start Warning blueprint](blueprints.md) for rain-rate and probability
alerts.

---

## Skip irrigation when nature already helped

Best for: smart irrigation, garden beds, lawns, balconies with drip irrigation.

Use the bundled
[Irrigation Rain Skip blueprint](blueprints.md) when possible. It already
combines recent rain and rain probability.

For Smart Irrigation, map one of these sensors:

| Need | Entity |
|---|---|
| Best ET0 when solar radiation is mapped | `sensor.ws_et0_penman_monteith` |
| ET0 without solar radiation | `sensor.ws_et0_daily` |
| Today's measured rainfall | `sensor.ws_rain_today_mm` |
| Soil-aware demand score | `sensor.ws_irrigation_need_score` |

---

## Protect awnings and blinds from wind

Best for: awnings, exterior blinds, pergolas, shade sails.

Use the bundled
[High Wind Gusts blueprint](blueprints.md) for cover retraction. It is safer
than a raw automation because it already has inputs for covers and thresholds.

Good starting thresholds:

| Hardware | Start with |
|---|---|
| Light fabric awning | `sensor.ws_wind_gust` above 10-12 m/s |
| Exterior venetian blinds | `sensor.ws_wind_gust` above 12-15 m/s |
| Heavy-duty awning | Check the manufacturer rating first |

---

## Warn before frost

Best for: plants, exposed pipes, greenhouses, outdoor taps.

Use the bundled
[Freeze Warning blueprint](blueprints.md) for temperature-triggered alerts.

For a more weather-aware dashboard tile, watch:

| Entity | What it tells you |
|---|---|
| `sensor.ws_frost_risk` | Human-readable frost risk category |
| `sensor.ws_frost_point` | Temperature where frost can form |
| `sensor.ws_frost_streak_days` | Consecutive frost days |

---

## Close windows when air quality gets bad

Best for: smoke, dust, city pollution, pollen-sensitive households.

Enable **Air Quality** under **Configure -> Features**. Then use the bundled
[Poor Air Quality blueprint](blueprints.md) to notify, close covers, or turn on
fans/purifiers.

Core entities:

| Entity | Use |
|---|---|
| `sensor.ws_air_quality_index` | Main AQI decision sensor |
| `sensor.ws_pm2_5` | Smoke and fine particles |
| `sensor.ws_pm10` | Dust and coarse particles |
| `sensor.ws_ozone` | Ozone exposure |

---

## Choose your first feature pack

| You care about | Enable |
|---|---|
| Rain countdown | Precipitation Nowcast |
| Garden watering | Comfort Indices, Soil Sensors, Solar Forecast |
| Fire season | Fire Risk, FWI Components |
| Heat stress | Comfort Indices |
| Storms | Lightning Detection, Thunderstorm Risk |
| Dashboards and TTS summaries | Display Sensors |
| Data confidence | Station Diagnostics |
