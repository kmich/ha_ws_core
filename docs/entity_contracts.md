# Entity creation and registry defaults

The entity key and unique ID remain stable across these prerequisite changes.
Feature selection controls whether a family is created; a temporarily unavailable
source makes its reading unknown rather than removing the configured entity.

| Family | Creation prerequisite | Calculation prerequisite |
|---|---|---|
| Solar PV forecast | Solar PV forecast selected | Forecast service and PV settings |
| Daily Penman–Monteith ET₀, solar energy, peak sun hours, net radiation | Solar radiation source mapped, or lux mapped with the explicit illuminance estimate selected | Fresh source data and each calculation's weather and completed-period inputs |
| Clearness and cloud cover | Measured solar radiation source mapped | Fresh measured radiation and solar geometry |
| Max theoretical solar radiation | None | Location and day of year |
| Irrigation deficit | None | ET₀ and rainfall for the relevant period |
| FWI composite and daily severity | Fire Risk selected | Temperature, humidity, wind, and rain |
| FWI intermediate codes | FWI Components selected | The same FWI calculation runs even if the Fire Risk display switch is off |

Configured source identity, current source health, and model readiness are separate
states. A source going temporarily offline does not alter registry membership or a
user's enabled/disabled choice.

## Newly registered entity defaults

The existing `entity_registry_enabled_default=False` declarations were reviewed.
The primary FWI is enabled on new registrations when Fire Risk is selected;
the other 34 remain the specialist default set. They cover extra thermodynamic and comfort
indices, wind/solar/agro diagnostics, FWI details, air pollutant details, and
Pattern Forecast skill. The primary temperature, humidity, pressure, rain, and
forecast readings retain their declared enabled defaults. This change makes the
declarations effective at the entity boundary; it does not rewrite any existing
entity registry record. Home Assistant preserves manually enabled, disabled, and
renamed entities on upgrade, including the seventeen enabled during the audit.

The shipped full dashboard includes specialist cards and can refer to readings
that require a feature selection or an entity enabled by the user. The streamlined
dashboard preview uses the normal core readings and labels optional cards as
such. Review the chosen default dashboard against a fresh registry before release.
