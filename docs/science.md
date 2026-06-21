# Scientific Documentation {#science}

Every derived metric is documented with its algorithm, source reference, valid input
range, and known limitations.

---

### Dew Point — Magnus Formula (Alduchov & Eskridge 1996)

The dew point T_d is the temperature at which air becomes saturated if cooled at
constant pressure and humidity.

```
γ(T, RH) = (a·T) / (b + T) + ln(RH / 100)
T_d = (b · γ) / (a − γ)

Over water (T ≥ 0 °C): a = 17.625, b = 243.04 °C   [Alduchov & Eskridge 1996]
Over ice  (T < 0 °C):  a = 22.587, b = 273.86 °C   [Buck 1981]
```

**Valid range:** −45 °C to +60 °C, 1-100% RH. **Max error:** < 0.1 °C within range.
**Reference:** Alduchov, O.A. & Eskridge, R.E. (1996). *J. Appl. Meteor.*, 35, 601-609.

---

### Frost Point — Magnus Formula with Ice Constants (Buck 1981)

The frost point is the temperature at which ice saturation occurs. Uses Buck's (1981)
ice-phase saturation constants (a = 22.587, b = 273.86). Returns dew point above 0 °C,
frost point below 0 °C.

**Reference:** Buck, A.L. (1981). *J. Appl. Meteor.*, 20, 1527-1532.

---

### Wet-Bulb Temperature — Stull (2011)

```
T_w = T · atan(0.151977 · (RH + 8.313659)^0.5)
    + atan(T + RH)
    − atan(RH − 1.676331)
    + 0.00391838 · RH^1.5 · atan(0.023101 · RH)
    − 4.686035
```

**Valid range:** T −20 to +50 °C, RH 5-99%. **Max error:** ±0.3 °C.
**Reference:** Stull, R. (2011). *J. Appl. Meteor. Climatol.*, 50, 2267-2269.

---

### Sea-Level Pressure — Hypsometric Reduction (WMO No. 8)

```
MSLP = P_station × exp(elevation_m / (T_K × 29.263))
```

**Accuracy:** ±0.3 hPa below 500 m, ±1 hPa at 2000 m.
**Reference:** WMO No. 8 — Guide to Meteorological Instruments and Methods of Observation, Annex 3A.

---

### Apparent Temperature — Australian BOM / Steadman (1994)

```
AT = T_a + 0.33 · e − 0.70 · ws − 4.0

where e = (RH / 100) × 6.105 × exp((17.27 · T) / (237.7 + T))   [vapour pressure, hPa]
      ws = wind speed at 10 m height [m/s]
```

**Reference:** Steadman, R.G. (1994). *Aust. Met. Mag.*, 43, 1-16.

---

### Heat Index — NWS Rothfusz Regression (1990)

```
HI = −42.379 + 2.04901523·T + 10.14333127·RH − 0.22475541·T·RH
     − 0.00683783·T² − 0.05481717·RH² + 0.00122874·T²·RH
     + 0.00085282·T·RH² − 0.00000199·T²·RH²       (T in °F)
```

**Valid range:** T ≥ 27 °C (80 °F) and RH ≥ 40%.
**Reference:** Rothfusz, L.P. (1990). *The Heat Index Equation.* NWS Technical Attachment SR 90-23.

---

### Wind Chill — WMO / NWS Joint Index (2001)

```
WCT = 13.12 + 0.6215·T − 11.37·V^0.16 + 0.3965·T·V^0.16
      (T in °C, V = wind speed in km/h)
```

**Valid range:** T ≤ 10 °C and wind > 1.34 m/s (4.8 km/h).
**Reference:** Environment Canada / NWS (2001). New wind chill equivalent temperature index.

---

### Humidex — Environment Canada (Masterton & Richardson 1979)

```
e = 6.1078 · exp[5417.7530 · (1/273.16 − 1/(273.16 + T_d))]
Humidex = T + 0.5555 · (e − 10)        (T, T_d in °C; e in hPa)
```

**Reference:** Masterton, J.M. & Richardson, F.A. (1979). *Humidex: A method of quantifying human discomfort.* Environment Canada, CLI 1-79.

---

### Davis THW and THSW Indices

```
THW  = HeatIndex − 1.072 · V          (V in mph)
THSW = THW + 0.01 · solar_radiation    (solar in W/m²)
```

**Reference:** Davis Instruments WeatherLink documentation; Steadman (1979).

---

### Vapour Pressure Deficit (VPD)

```
e_s = 0.6108 · exp(17.27·T / (T + 237.3))     (saturation, kPa)
VPD = e_s − e_s · RH/100
```

**Reference:** Allen, R.G. et al. (1998). *FAO Irrigation and Drainage Paper 56.*

---

### Delta-T — Spray Application Index

```
Delta-T = T − T_wetbulb
```

| Delta-T | Suitability |
|---|---|
| < 2 °C | Unsuitable (too humid) |
| 2-8 °C | Ideal spray window |
| > 8 °C | Unsuitable (too dry) |

**Reference:** APVMA spraying guidelines.

---

### Zambretti Barometric Forecaster (Negretti & Zambra, 1915) {#zambretti}

The Zambretti forecaster produces a forecast letter A-Z (Z-number 1-26) from three
observable surface quantities: MSLP, pressure trend, and wind direction. The final
Z-number indexes the authentic 26-entry Negretti & Zambra lookup table.

**Accuracy:** 65-75% for 6-12h forecasts in maritime and Mediterranean climates.

**References:**
- Negretti & Zambra (1915). *A Treatise on Meteorological Instruments.* London.
- Watts, A. (2012). *Instant Wind Forecasting.* Adlard Coles Nautical.

---

### Pressure Trend — Least-Squares Regression (WMO No. 306)

OLS regression fitted to the pressure history buffer (configurable window, default 3h),
slope extrapolated to a standardised 3-hour equivalent rate. Classification follows
WMO synoptic code Table 4680.

**Reference:** WMO No. 306 — Manual on Codes, Vol. I.1, Table 4680.

---

### Canadian Forest Fire Weather Index System (Van Wagner 1987) {#fwi}

Complete Van Wagner (1987) implementation: FFMC, DMC, DC moisture codes with persistent
daily carry-over across HA restarts, ISI, BUI, FWI, DSR.

**Disclaimer:** Not suitable for operational fire weather decisions. Consult official
fire services and national fire weather products.

**Reference:** Van Wagner, C.E. (1987). *Development and structure of the Canadian Forest
Fire Weather Index System.* Forestry Technical Report 35. Canadian Forestry Service.

---

### ET₀ — Reference Evapotranspiration {#et0-science}

**Hargreaves-Samani 1985** (default, always available):

```
ET₀ = 0.0023 · Ra · (T_mean + 17.8) · (T_max − T_min)^0.5
```

**Accuracy:** ±15-20% vs Penman-Monteith.
**Reference:** Hargreaves, G.H. & Samani, Z.A. (1985). *Appl. Eng. Agric.*, 1, 96-99.

**FAO-56 Penman-Monteith** (activates when a `solar_radiation` W/m² source is mapped):

```
ET₀ = [0.408·Δ·(Rn − G) + γ·(900/(T+273))·u₂·(eₛ − eₐ)] / [Δ + γ·(1 + 0.34·u₂)]
```

**Accuracy:** ±5-10% vs lysimeter under standard conditions.
**Reference:** Allen, R.G. et al. (1998). *FAO Irrigation and Drainage Paper 56.* FAO, Rome.

---

### Moon Phase — Meeus Astronomical Algorithms (1998)

Computed from Julian Date using simplified lunar orbital equations without external API calls.
**Accuracy:** ±1% illumination, ±0.5 day phase timing.
**Reference:** Meeus, J. (1998). *Astronomical Algorithms*, 2nd ed. Willmann-Bell. Chapter 48.

---

### Rain Rate — 1D Kalman Filter

Optimal recursive smoothing eliminates tipping-bucket spike-and-drop artefacts.
Configurable measurement noise (`number.ws_rain_filter_alpha`).

---

### 30-Day Rolling Climatology

After approximately 14 days of operation, the integration builds a local climate baseline
from the station's own history. Temperature and rain anomaly sensors are meaningful after
30+ days of continuous operation.

---

### Sensor Drift Detection — Linear Regression (72h)

OLS regression over 72h flagging monotonic drift (slope magnitude + R² ≥ 0.85) in
temperature, humidity, pressure, and rain rate.

---

### Cross-Sensor Consistency Checks

Six physical-impossibility checks per coordinator update:

| Check | Violation condition |
|---|---|
| Gust vs wind | Gust speed < sustained wind speed |
| Dew point vs temperature | Dew point > air temperature |
| UV vs illuminance | UV index > 0 while illuminance < 50 lx |
| UV vs time of day | UV index > 2 between 22:00-04:00 local time |
| Rain rate vs total | Rain rate > 0 but cumulative rain total unchanged |
| Pressure stuck | Pressure unchanging for > 3h while wind speed > 2 m/s |

---

## Services {#services}

| Service | Description |
|---|---|
| `ws_core.reset_rain_baseline` | Reset the internal rain total baseline (useful after station rain counter resets) |
| `ws_core.apply_calibration` | Write sensor calibration offsets from an automation or Developer Tools |

---

## Sensor Calibration {#calibration}

All offsets are applied after unit conversion, before all derived calculations.

| Offset | Range | Typical use |
|---|---|---|
| Temperature | ±10 °C | Correct for sensor placement or radiation shield quality |
| Humidity | ±20% | Compensate for sensor aging |
| Pressure | ±10 hPa | Correct for altitude error |
| Wind speed | ±5 m/s | Adjust for sheltered mounting |

---

## Troubleshooting {#troubleshooting}

| Symptom | Likely Cause | Fix |
|---|---|---|
| All sensors show "unavailable" | Source entities not found | Check source sensor entity IDs in Configure |
| Temperature statistics look wrong | Old `TOTAL_INCREASING` state class | Delete the temperature entity from HA, restart |
| Rain rate stuck at 0 | Rain total sensor reset | Call `ws_core.reset_rain_baseline` service |
| Forecast shows "unavailable" | Provider API timeout or auth error | Check internet; verify API key if using OWM/Pirate Weather |
| "Stale" warning | Source sensor stopped updating | Check your weather station hardware |

Download diagnostics via **Settings → Devices & Services → Weather Station Core → ⋮ → Download Diagnostics**.

---

## Known Limitations

1. Illuminance-based cloud detection uses raw lux without solar-angle normalization. Accuracy degrades at low sun elevation angles.
2. Sea-level pressure uses current temperature only, not the WMO-recommended 12h mean.
3. Rain probability is a heuristic index, not a statistically calibrated probability.
4. FWI moisture codes are initialised at Van Wagner's standard defaults on first run and self-correct within a few days.
5. Thunderstorm Risk is a surface-based proxy only and cannot detect elevated convection.
6. 24h statistics are computed from in-memory rolling windows and reset on HA restart.

---

## Example Automations

Five automation blueprints are provided in `blueprints/automation/ws_core/`:

- **Frost Alert** — Notify when temperature drops below threshold
- **Storm Alert** — Alert on rapid pressure drop with high wind
- **Irrigation Rain Skip** — Skip watering when rain is expected or accumulated
- **Lightning Safety** — Notify when lightning is detected nearby
- **Fire Danger Alert** — Alert when fire danger reaches a configurable level

See [the blueprints folder](https://github.com/kmich/ha_ws_core/tree/main/blueprints) for installation instructions.

---

## Contributing {#contributing}

Contributions are welcome. Open an issue first to discuss what you'd like to change.

- **Translations**: Copy `custom_components/ws_core/translations/en.json` to a new
  locale file (e.g. `de.json`) and open a PR. All entity names, config flow strings,
  and state labels are covered.
- **Bug reports**: Use the GitHub issue template and include your diagnostics export.
- **Weather stations**: If your station brand needs special handling, open an issue
  with your entity details.
- **New forecast providers**: Create `custom_components/ws_core/providers/your_provider.py`,
  subclass `ForecastProvider` from `base.py`, and add one line to `providers/__init__.py`.

---

## License

[MIT](https://github.com/kmich/ha_ws_core/blob/main/LICENSE)

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/kmich/ha_ws_core
[release-url]: https://github.com/kmich/ha_ws_core/releases
[license-badge]: https://img.shields.io/github/license/kmich/ha_ws_core
[license-url]: https://github.com/kmich/ha_ws_core/blob/main/LICENSE
[validate-badge]: https://img.shields.io/github/actions/workflow/status/kmich/ha_ws_core/validate.yml?label=validate
[validate-url]: https://github.com/kmich/ha_ws_core/actions/workflows/validate.yml
[translation-badge]: https://img.shields.io/badge/translations-8-blue
[translation-url]: https://github.com/kmich/ha_ws_core/tree/main/custom_components/ws_core/translations
