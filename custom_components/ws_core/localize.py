"""Localized free-text strings for sensor states HA cannot translate.

A few sensors expose a *generated free-text string* as their state - the
current-conditions summary and the alert message. Home Assistant's translation
system only localizes fixed state keys, not dynamic text, so these are
localized here in Python using the HA-configured language, falling back to
English for any unsupported language (issue #104).

Add a new language by adding its two-letter code to both tables below.
"""

from __future__ import annotations

# Conditions-summary fragments. ``{v}`` is a pre-formatted value, unit included,
# so it follows the configured display units.
_SUMMARY: dict[str, dict[str, str]] = {
    "en": {
        "feels_like": "feels like {v}",
        "rain": "{v} rain",
        "gusting": "gusting {v}",
        "humidity": "RH {v}%",
        "no_data": "No data",
    },
    "fr": {
        "feels_like": "ressenti {v}",
        "rain": "{v} de pluie",
        "gusting": "rafales {v}",
        "humidity": "HR {v}%",
        "no_data": "Aucune donnée",
    },
}

# Alert-message fragments. ``{v}`` is a pre-formatted value, unit included.
_ALERT: dict[str, dict[str, str]] = {
    "en": {
        "wind": "Extreme wind: {v}",
        "rain": "Heavy rain: {v}",
        "freeze": "Freeze risk: {v}",
        "lightning": "Lightning detected nearby — stay indoors",
        "clear": "All clear",
    },
    "fr": {
        "wind": "Vent extrême : {v}",
        "rain": "Pluie forte : {v}",
        "freeze": "Risque de gel : {v}",
        "lightning": "Foudre détectée à proximité — restez à l'intérieur",
        "clear": "Tout est normal",
    },
}


def _lang(language: str | None) -> str:
    """Normalise an HA language code to a supported key, defaulting to English."""
    if not language:
        return "en"
    code = language.split("-")[0].lower()
    return code if code in _SUMMARY else "en"


def summary(language: str | None, key: str, **fmt: str) -> str:
    """Return a localized conditions-summary fragment."""
    return _SUMMARY[_lang(language)][key].format(**fmt)


def alert(language: str | None, key: str, **fmt: str) -> str:
    """Return a localized alert-message fragment."""
    return _ALERT[_lang(language)][key].format(**fmt)


_WINDOW_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "suitable_now": "Conditions meet all limits for {name} starting now for at least {dur} hours.",
        "window_upcoming": "Next suitable window starts at {start} for {dur} hours.",
        "horizon_truncated": "Window extends to the end of the available forecast horizon.",
        "no_horizon_in_window": "No forecast hours within the 24-hour evaluation window.",
        "insufficient_horizon": "No continuous suitable interval meets the {dur}-hour minimum duration.",
        "insufficient_data": "Insufficient hourly forecast data available to evaluate windows.",
        "currently_raining": "Rain is currently falling at the station.",
        "current_gust_high": "Current wind gusts exceed the {limit} limit.",
        "nighttime": "Sun is below horizon (daylight required).",
        "rain_risk": "Forecast rain probability exceeds {limit}%.",
        "rain_amount": "Forecast precipitation exceeds {limit}.",
        "too_cold": "Temperature is below {limit}.",
        "too_hot": "Temperature exceeds {limit}.",
        "high_humidity": "Relative humidity exceeds {limit}%.",
        "low_humidity": "Relative humidity is below {limit}%.",
        "calm_air": "Wind is calm (< {limit}).",
        "high_wind": "Wind speed exceeds {limit}.",
        "high_gust": "Wind gusts exceed {limit}.",
        "heavy_clouds": "Cloud cover exceeds {limit}% (sunshine proxy).",
        "missing_data": "Required forecast variable is missing from provider.",
        "not_assessed_by_provider": "Not assessed by forecast provider: {fields}.",
    },
    "fr": {
        "suitable_now": "Les conditions respectent toutes les limites pour {name} dès maintenant pendant au moins {dur} h.",
        "window_upcoming": "Prochain créneau favorable à partir de {start} pendant {dur} h.",
        "horizon_truncated": "Le créneau atteint la fin de l'horizon de prévision disponible.",
        "no_horizon_in_window": "Aucune heure de prévision dans l'horizon de 24 heures.",
        "insufficient_horizon": "Aucun intervalle continu n'atteint la durée minimale de {dur} h.",
        "insufficient_data": "Données horaires insuffisantes pour évaluer les créneaux.",
        "currently_raining": "Il pleut actuellement à la station.",
        "current_gust_high": "Les rafales actuelles dépassent la limite de {limit}.",
        "nighttime": "Le soleil est sous l'horizon (lumière du jour requise).",
        "rain_risk": "La probabilité de pluie prévue dépasse {limit}%.",
        "rain_amount": "Les précipitations prévues dépassent {limit}.",
        "too_cold": "La température est inférieure à {limit}.",
        "too_hot": "La température dépasse {limit}.",
        "high_humidity": "L'humidité relative dépasse {limit}%.",
        "low_humidity": "L'humidité relative est inférieure à {limit}%.",
        "calm_air": "Vent trop faible (< {limit}).",
        "high_wind": "La vitesse du vent dépasse {limit}.",
        "high_gust": "Les rafales dépassent {limit}.",
        "heavy_clouds": "La nébulosité dépasse {limit}% (indicateur d'ensoleillement).",
        "missing_data": "Une variable météo requise est absente de la prévision.",
        "not_assessed_by_provider": "Non évalué par le fournisseur de prévisions : {fields}.",
    },
    "de": {
        "suitable_now": "Alle Grenzwerte für {name} sind ab jetzt für mindestens {dur} Std. erfüllt.",
        "window_upcoming": "Nächstes geeignetes Zeitfenster beginnt um {start} für {dur} Std.",
        "horizon_truncated": "Das Zeitfenster reicht bis zum Ende des verfügbaren Vorhersagehorizonts.",
        "no_horizon_in_window": "Keine Vorhersagestunden im 24-Stunden-Fenster.",
        "insufficient_horizon": "Kein durchgehendes Zeitfenster erreicht die Mindestdauer von {dur} Std.",
        "insufficient_data": "Unzureichende stündliche Vorhersagedaten.",
        "currently_raining": "An der Station fällt derzeit Regen.",
        "current_gust_high": "Aktuelle Windböen überschreiten das Limit von {limit}.",
        "nighttime": "Sonne unter dem Horizont (Tageslicht erforderlich).",
        "rain_risk": "Vorhergesagte Regenwahrscheinlichkeit übersteigt {limit}%.",
        "rain_amount": "Vorhergesagter Niederschlag übersteigt {limit}.",
        "too_cold": "Temperatur liegt unter {limit}.",
        "too_hot": "Temperatur liegt über {limit}.",
        "high_humidity": "Relative Luftfeuchtigkeit übersteigt {limit}%.",
        "low_humidity": "Relative Luftfeuchtigkeit liegt unter {limit}%.",
        "calm_air": "Wind ist zu schwach (< {limit}).",
        "high_wind": "Windgeschwindigkeit übersteigt {limit}.",
        "high_gust": "Windböen übersteigen {limit}.",
        "heavy_clouds": "Bewölkung übersteigt {limit}% (Sonnenschein-Proxy).",
        "missing_data": "Erforderliche Vorhersagevariable fehlt beim Anbieter.",
        "not_assessed_by_provider": "Vom Vorhersageanbieter nicht bereitgestellt: {fields}.",
    },
    "es": {
        "suitable_now": "Las condiciones cumplen todos los límites para {name} desde ahora durante al menos {dur} h.",
        "window_upcoming": "La próxima ventana favorable comienza a las {start} durante {dur} h.",
        "horizon_truncated": "La ventana se extiende hasta el final del horizonte de pronóstico disponible.",
        "no_horizon_in_window": "No hay horas de pronóstico dentro de la ventana de 24 horas.",
        "insufficient_horizon": "Ningún intervalo continuo alcanza la duración mínima de {dur} h.",
        "insufficient_data": "Datos horarios insuficientes para evaluar ventanas.",
        "currently_raining": "Está lloviendo actualmente en la estación.",
        "current_gust_high": "Las rachas actuales superan el límite de {limit}.",
        "nighttime": "El sol está bajo el horizonte (se requiere luz diurna).",
        "rain_risk": "La probabilidad de lluvia prevista supera el {limit}%.",
        "rain_amount": "La precipitación prevista supera {limit}.",
        "too_cold": "La temperatura es inferior a {limit}.",
        "too_hot": "La temperatura supera {limit}.",
        "high_humidity": "La humedad relativa supera el {limit}%.",
        "low_humidity": "La humedad relativa es inferior al {limit}%.",
        "calm_air": "Viento demasiado débil (< {limit}).",
        "high_wind": "La velocidad del viento supera {limit}.",
        "high_gust": "Las rachas de viento superan {limit}.",
        "heavy_clouds": "La nubosidad supera el {limit}% (indicador de sol).",
        "missing_data": "Falta una variable meteorológica obligatoria del proveedor.",
        "not_assessed_by_provider": "No evaluado por el proveedor de pronóstico: {fields}.",
    },
    "it": {
        "suitable_now": "Le condizioni rispettano tutti i limiti per {name} da subito per almeno {dur} ore.",
        "window_upcoming": "La prossima finestra favorevole inizia alle {start} per {dur} ore.",
        "horizon_truncated": "La finestra si estende fino alla fine dell'orizzonte di previsione disponibile.",
        "no_horizon_in_window": "Nessuna ora di previsione nella finestra di 24 ore.",
        "insufficient_horizon": "Nessun intervallo continuo raggiunge la durata minima di {dur} ore.",
        "insufficient_data": "Dati orari insufficienti per valutare le finestre.",
        "currently_raining": "Sta piovendo attualmente alla stazione.",
        "current_gust_high": "Le raffiche attuali superano il limite di {limit}.",
        "nighttime": "Il sole è sotto l'orizzonte (luce diurna richiesta).",
        "rain_risk": "La probabilità di pioggia prevista supera il {limit}%.",
        "rain_amount": "Le precipitazioni previste superano {limit}.",
        "too_cold": "La temperatura è inferiore a {limit}.",
        "too_hot": "La temperatura supera {limit}.",
        "high_humidity": "L'umidità relativa supera il {limit}%.",
        "low_humidity": "L'umidità relativa è inferiore al {limit}%.",
        "calm_air": "Vento troppo debole (< {limit}).",
        "high_wind": "La velocità del vento supera {limit}.",
        "high_gust": "Le raffiche di vento superano {limit}.",
        "heavy_clouds": "La copertura nuvolosa supera il {limit}% (indice di sole).",
        "missing_data": "Variabile di previsione richiesta mancante dal fornitore.",
        "not_assessed_by_provider": "Non valutato dal fornitore di previsioni: {fields}.",
    },
    "nl": {
        "suitable_now": "De omstandigheden voldoen vanaf nu minstens {dur} uur aan alle limieten voor {name}.",
        "window_upcoming": "Volgend geschikt venster begint om {start} gedurende {dur} uur.",
        "horizon_truncated": "Het venster loopt door tot het einde van de beschikbare verwachtingshorizon.",
        "no_horizon_in_window": "Geen verwachtingsuren binnen het 24-uursvenster.",
        "insufficient_horizon": "Geen aaneengesloten interval haalt de minimumduur van {dur} uur.",
        "insufficient_data": "Onvoldoende uurlijkse verwachtingsgegevens om vensters te beoordelen.",
        "currently_raining": "Het regent momenteel bij het station.",
        "current_gust_high": "Huidige windstoten overschrijden de limiet van {limit}.",
        "nighttime": "De zon staat onder de horizon (daglicht vereist).",
        "rain_risk": "Verwachte neerslagkans is hoger dan {limit}%.",
        "rain_amount": "Verwachte neerslag overschrijdt {limit}.",
        "too_cold": "Temperatuur is lager dan {limit}.",
        "too_hot": "Temperatuur is hoger dan {limit}.",
        "high_humidity": "Relatieve luchtvochtigheid is hoger dan {limit}%.",
        "low_humidity": "Relatieve luchtvochtigheid is lager dan {limit}%.",
        "calm_air": "Wind is te zwak (< {limit}).",
        "high_wind": "Windsnelheid overschrijdt {limit}.",
        "high_gust": "Windstoten overschrijden {limit}.",
        "heavy_clouds": "Bewolking overschrijdt {limit}% (zonneschijn-proxy).",
        "missing_data": "Vereiste verwachtingsvariabele ontbreekt bij de provider.",
        "not_assessed_by_provider": "Niet beoordeeld door verwachtingsprovider: {fields}.",
    },
    "pl": {
        "suitable_now": "Warunki spełniają wszystkie limity dla {name} od teraz przez co najmniej {dur} godz.",
        "window_upcoming": "Następne sprzyjające okno rozpoczyna się o {start} na {dur} godz.",
        "horizon_truncated": "Okno sięga końca dostępnego horyzontu prognozy.",
        "no_horizon_in_window": "Brak godzin prognozy w 24-godzinnym oknie oceny.",
        "insufficient_horizon": "Żaden ciągły przedział nie spełnia minimalnego czasu {dur} godz.",
        "insufficient_data": "Niewystarczające dane godzinowe do oceny okien pogodowych.",
        "currently_raining": "Na stacji aktualnie pada deszcz.",
        "current_gust_high": "Aktualne porywy wiatru przekraczają limit {limit}.",
        "nighttime": "Słońce poniżej horyzontu (wymagane światło dzienne).",
        "rain_risk": "Prognozowane prawdopodobieństwo opadów przekracza {limit}%.",
        "rain_amount": "Prognozowane opady przekraczają {limit}.",
        "too_cold": "Temperatura jest poniżej {limit}.",
        "too_hot": "Temperatura przekracza {limit}.",
        "high_humidity": "Wilgotność względna przekracza {limit}%.",
        "low_humidity": "Wilgotność względna jest poniżej {limit}%.",
        "calm_air": "Wiatr jest zbyt słaby (< {limit}).",
        "high_wind": "Prędkość wiatru przekracza {limit}.",
        "high_gust": "Porywy wiatru przekraczają {limit}.",
        "heavy_clouds": "Zachmurzenie przekracza {limit}% (wskaźnik nasłonecznienia).",
        "missing_data": "Brak wymaganej zmiennej prognozy od dostawcy.",
        "not_assessed_by_provider": "Nie oceniono przez dostawcę prognozy: {fields}.",
    },
    "pt": {
        "suitable_now": "As condições cumprem todos os limites para {name} desde já durante pelo menos {dur} h.",
        "window_upcoming": "Próxima janela favorável começa às {start} durante {dur} h.",
        "horizon_truncated": "A janela estende-se até ao fim do horizonte de previsão disponível.",
        "no_horizon_in_window": "Sem horas de previsão na janela de avaliação de 24 horas.",
        "insufficient_horizon": "Nenhum intervalo contínuo atinge a duração mínima de {dur} h.",
        "insufficient_data": "Dados horários insuficientes para avaliar janelas.",
        "currently_raining": "Está a chover atualmente na estação.",
        "current_gust_high": "As rajadas atuais excedem o limite de {limit}.",
        "nighttime": "O sol está abaixo do horizonte (requer luz solar).",
        "rain_risk": "A probabilidade de chuva prevista excede {limit}%.",
        "rain_amount": "A precipitação prevista excede {limit}.",
        "too_cold": "A temperatura está abaixo de {limit}.",
        "too_hot": "A temperatura excede {limit}.",
        "high_humidity": "A humidade relativa excede {limit}%.",
        "low_humidity": "A humidade relativa está abaixo de {limit}%.",
        "calm_air": "Vento demasiado fraco (< {limit}).",
        "high_wind": "A velocidade do vento excede {limit}.",
        "high_gust": "As rajadas de vento excedem {limit}.",
        "heavy_clouds": "A nebulosidade excede {limit}% (indicador de sol).",
        "missing_data": "Variável de previsão obrigatória em falta no fornecedor.",
        "not_assessed_by_provider": "Não avaliado pelo fornecedor de previsão: {fields}.",
    },
}


def window_text(language: str | None, key: str, **fmt: object) -> str:
    """Return a localized weather-window explanation string."""
    code = language.split("-")[0].lower() if language else "en"
    table = _WINDOW_TEXT.get(code, _WINDOW_TEXT["en"])
    return table.get(key, _WINDOW_TEXT["en"][key]).format(**fmt)
