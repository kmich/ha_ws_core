"""Synthetic station for the Pattern Forecast tests.

Builds a whole weather series up front (so runs are deterministic per seed) in
which one kind of event is *planted* with a readable precursor signature:

  rain   dew point depression collapses and pressure falls in the 4 h before a wet spell
  frost  a clear, calm, dry day is followed by a night that drops below 0 C
  heat   clear days run hot, and a hot day tends to follow a hot day
  gust   pressure falls and the wind builds in the 3 h before a gale
  storm  warm, humid, pressure-falling afternoons on "storm days" bring strikes
  noise  nothing is predictable: events fire at a fixed rate with no precursor

Drive an engine with ``run_world``: ``observe`` every ``STEP_S`` and ``issue``
every 15 minutes, exactly like the coordinator.
"""

from __future__ import annotations

import math
import random

from custom_components.ws_core.pattern_forecast import Instant, Observation

T0 = 1_767_225_600.0  # 2026-01-01 00:00:00 UTC (a multiple of 3600)
STEP_S = 300.0  # 5-minute ticks keep runs fast; the engine is told to accept them
DAY = 86400.0


def _smooth_noise(rng: random.Random, n: int, sigma: float, rho: float = 0.9) -> list[float]:
    out, x = [], 0.0
    s = sigma * math.sqrt(1.0 - rho * rho)
    for _ in range(n):
        x = rho * x + rng.gauss(0.0, s)
        out.append(x)
    return out


class World:
    def __init__(self, kind: str, days: int, seed: int = 1, rate: float | None = None) -> None:
        self.kind = kind
        self.n = int(days * DAY / STEP_S)
        self.rng = random.Random(seed)
        rng = self.rng
        n = self.n
        hours = [((i * STEP_S) / 3600.0) % 24.0 for i in range(n)]
        self.hours = hours
        # defaults: a plain, unremarkable day
        self.mslp = [
            1013.0 + 3.0 * math.sin(2 * math.pi * i / (n / max(1, days / 5))) + v
            for i, v in enumerate(_smooth_noise(rng, n, 1.5))
        ]
        self.dp_3h = [v for v in _smooth_noise(rng, n, 0.35, 0.8)]
        self.temp = [
            14.0 + 6.0 * math.sin(2 * math.pi * (h - 9.0) / 24.0) + v
            for h, v in zip(hours, _smooth_noise(rng, n, 0.8), strict=True)
        ]
        self.dpd = [max(0.3, 4.0 + v) for v in _smooth_noise(rng, n, 1.0)]
        self.speed = [max(0.3, 3.0 + v) for v in _smooth_noise(rng, n, 1.0)]
        self.gust = [s * 1.5 + abs(rng.gauss(0, 0.8)) for s in self.speed]
        self.rain_rate = [0.0] * n  # mm/h
        self.strikes = [0.0] * n
        self.clear_day = [0.0] * (days + 2)
        self.cloud_deficit = [0.0] * n
        self.solar_ok = [False] * n
        self.last_day_clear: list[float | None] = [None] * n
        self.events: list[tuple[int, int]] = []  # [start, end) step indices of the planted event
        getattr(self, f"_plant_{kind}")(days, rate)

    # ---- helpers -------------------------------------------------------

    def _poisson_events(self, mean_gap_h: float, min_gap_h: float, dur_h: tuple[float, float]) -> list[tuple[int, int]]:
        rng = self.rng
        out, t = [], 6.0
        while True:
            t += min_gap_h + rng.expovariate(1.0 / max(0.1, mean_gap_h - min_gap_h))
            d = rng.uniform(*dur_h)
            s, e = int(t * 3600 / STEP_S), int((t + d) * 3600 / STEP_S)
            if e >= self.n:
                return out
            out.append((s, e))
            t += d

    def _pre(self, i: int, start: int, lead_h: float) -> float:
        lead = lead_h * 3600.0 / STEP_S
        return min(1.0, max(0.0, 1.0 - (start - i) / lead))

    # ---- planted worlds -----------------------------------------------

    def _plant_rain(self, days: int, rate: float | None) -> None:
        self.events = self._poisson_events(rate or 14.0, 6.0, (1.0, 3.0))
        w = [0.0] * self.n
        for s, e in self.events:
            for i in range(max(0, s - int(4 * 3600 / STEP_S)), min(self.n, e)):
                w[i] = 1.0 if i >= s else self._pre(i, s, 4.0)
            for i in range(s, e):
                self.rain_rate[i] = 1.2 + self.rng.random()
        for i in range(self.n):
            self.dpd[i] = max(0.2, 4.0 - 3.4 * w[i] + 0.5 * self.rng.gauss(0, 1) + (self.dpd[i] - 4.0) * 0.3)
            self.dp_3h[i] = -1.4 * w[i] * (1.0 if self.rain_rate[i] == 0 else 0.3) + 0.2 * self.dp_3h[i]

    def _plant_gust(self, days: int, rate: float | None) -> None:
        self.events = self._poisson_events(rate or 16.0, 6.5, (0.5, 1.5))
        for s, e in self.events:
            for i in range(max(0, s - int(3 * 3600 / STEP_S)), min(self.n, e)):
                p = 1.0 if i >= s else self._pre(i, s, 3.0)
                self.dp_3h[i] = -2.0 * p + 0.2 * self.dp_3h[i]
                self.speed[i] = max(self.speed[i], 3.0 + 9.0 * p)
                self.gust[i] = self.speed[i] * 1.3 + abs(self.rng.gauss(0, 0.5))
            for i in range(s, e):
                self.gust[i] = 18.5 + 4.0 * self.rng.random()

    def _plant_storm(self, days: int, rate: float | None) -> None:
        rng = self.rng
        storm_day_p = rate or 0.28
        for d in range(days):
            hot = rng.random() < storm_day_p
            for i in range(int(d * DAY / STEP_S), min(self.n, int((d + 1) * DAY / STEP_S))):
                h = self.hours[i]
                if hot and 9.0 <= h < 19.0:
                    ramp = min(1.0, (h - 9.0) / 5.0)
                    self.temp[i] += 6.0 * ramp
                    self.dpd[i] = max(0.3, 4.0 - 2.8 * ramp + 0.4 * rng.gauss(0, 1))
                    self.dp_3h[i] = -1.0 * ramp + 0.2 * self.dp_3h[i]
            if hot:
                s = int((d * 24 + 14.0 + rng.uniform(0, 2)) * 3600 / STEP_S)
                e = s + int(rng.uniform(1.0, 2.5) * 3600 / STEP_S)
                if e < self.n:
                    self.events.append((s, e))
                    for i in range(s, e):
                        self.strikes[i] = rng.choice([0.0, 1.0, 2.0, 3.0])

    def _curve(self, min_at, max_at) -> None:
        """Temperature as a cosine through a 03:00 minimum and a 15:00 maximum each day."""
        for i in range(self.n):
            h_abs = i * STEP_S / 3600.0
            k = math.floor((h_abs - 3.0) / 12.0)
            f = (h_abs - (3.0 + 12.0 * k)) / 12.0

            def val(kk: int) -> float:
                d = max(kk // 2, 0)
                return min_at(d) if kk % 2 == 0 else max_at(d)

            a, b = val(k), val(k + 1)
            self.temp[i] = a + (b - a) * (1.0 - math.cos(math.pi * f)) / 2.0 + 0.15 * self.dp_3h[i]

    def _day_index(self, i: int) -> int:
        """The day whose daytime (from 08:00) is the most recent one."""
        return max(0, int((i * STEP_S / 3600.0 - 8.0) // 24))

    def _plant_frost(self, days: int, rate: float | None) -> None:
        rng = self.rng
        clear = [rng.random() for _ in range(days + 3)]
        calm = [rng.random() for _ in range(days + 3)]
        tmin = [5.5 - 8.5 * c - 2.5 * k + rng.gauss(0, 0.6) + (rate or 0.0) for c, k in zip(clear, calm, strict=True)]
        self._curve(lambda d: tmin[max(d - 1, 0)], lambda d: 8.0 + 6.0 * clear[d])
        for i in range(self.n):
            d = self._day_index(i)
            h = self.hours[i]
            self.speed[i] = max(0.2, 1.0 + 5.0 * (1.0 - calm[d]) + 0.2 * rng.gauss(0, 1))
            self.gust[i] = self.speed[i] * 1.4
            self.dpd[i] = max(0.3, 1.5 + 3.0 * clear[d] + 0.3 * rng.gauss(0, 1))
            if 8.0 <= h < 17.0:
                self.solar_ok[i] = True
                self.cloud_deficit[i] = 1.0 - clear[d]
            self.last_day_clear[i] = clear[d]
        self.events = self._below(0.0)

    def _below(self, thr: float) -> list[tuple[int, int]]:
        out, start = [], None
        for i, t in enumerate(self.temp):
            if t <= thr and start is None:
                start = i
            elif t > thr and start is not None:
                out.append((start, i))
                start = None
        return out

    def _plant_heat(self, days: int, rate: float | None) -> None:
        rng = self.rng
        clear, tmax = [], []
        x = 0.5
        for _ in range(days + 3):
            x = min(1.0, max(0.0, 0.7 * x + 0.3 * rng.random() + 0.08 * rng.gauss(0, 1)))
            clear.append(x)
            tmax.append(24.5 + 8.5 * x + rng.gauss(0, 1.0) + (rate or 0.0))
        self._curve(lambda d: tmax[d] - 10.0, lambda d: tmax[d])
        for i in range(self.n):
            d = self._day_index(i)
            h = self.hours[i]
            self.dpd[i] = max(0.3, 2.0 + 6.0 * clear[d] + 0.4 * rng.gauss(0, 1))
            if 8.0 <= h < 17.0:
                self.solar_ok[i] = True
                self.cloud_deficit[i] = 1.0 - clear[d]
        self.events = [(s, e) for s, e in self._above(30.0)]

    def _above(self, thr: float) -> list[tuple[int, int]]:
        out, start = [], None
        for i, t in enumerate(self.temp):
            if t >= thr and start is None:
                start = i
            elif t < thr and start is not None:
                out.append((start, i))
                start = None
        return out

    def _plant_noise(self, days: int, rate: float | None) -> None:
        """Independent single-tick events at a fixed rate: nothing predicts them."""
        rng = self.rng
        for i in range(self.n):
            if rng.random() < 0.010:
                self.rain_rate[i] = 2.4  # one 0.2 mm tip in this tick
            if rng.random() < 0.004:
                self.gust[i] = 20.0
            if rng.random() < 0.010:
                self.strikes[i] = 1.0
            if rng.random() < 0.0025:
                self.temp[i] = -1.0
            elif rng.random() < 0.0008:
                self.temp[i] = 31.0

    # ---- stepping -------------------------------------------------------

    def run(self, engine, with_issue: bool = True, tz_offset_s: float = 0.0, start: float = T0) -> None:
        rain_total = 0.0
        strikes_total = 0.0
        temp_hist: list[float] = []
        wind_dir = self.rng.uniform(0, 360)
        for i in range(self.n):
            ts = start + i * STEP_S
            rain_total += self.rain_rate[i] * STEP_S / 3600.0
            strikes_total += self.strikes[i]
            temp_hist.append(self.temp[i])
            if len(temp_hist) > 288:
                temp_hist.pop(0)
            ang = math.radians(wind_dir)
            sp = self.speed[i]
            obs = Observation(
                temp=self.temp[i],
                dpd=self.dpd[i],
                wind_u=-sp * math.sin(ang),
                wind_v=-sp * math.cos(ang),
                wind_speed=sp,
                gust=self.gust[i],
                rain_total=round(rain_total / 0.2) * 0.2,
                strikes_total=strikes_total if engine.storm_source else None,
            )
            engine.observe(ts, obs, tz_offset_s)
            if with_issue and i % 3 == 0:
                inst = Instant(
                    mslp=self.mslp[i],
                    dp_3h=self.dp_3h[i],
                    temp=self.temp[i],
                    dpd=self.dpd[i],
                    t_max_24h=max(temp_hist),
                    t_min_24h=min(temp_hist),
                    cloud_deficit=self.cloud_deficit[i],
                    solar_ok=self.solar_ok[i],
                    last_day_clearness=self.last_day_clear[i],
                    night_frac_12h=_night_frac(self.hours[i]),
                    local_hour=self.hours[i],
                )
                engine.issue(ts, inst, tz_offset_s)


def _night_frac(hour: float) -> float:
    """Fraction of the next 12 h spent between 19:00 and 07:00."""
    n = 0
    for k in range(24):
        h = (hour + (k + 0.5) / 2.0) % 24.0
        if h >= 19.0 or h < 7.0:
            n += 1
    return n / 24.0


def make_engine(storm_source: str | None = None, cap: float = STEP_S * 1.5, **kw):
    from custom_components.ws_core.pattern_forecast import PatternEngine, Thresholds

    return PatternEngine(Thresholds(**kw), storm_source, tick_cap_s=cap)
