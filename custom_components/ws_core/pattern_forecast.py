"""Pattern Forecast engine (v2.11): local, learning-based event probabilities.

Learns from this station only and answers "what is the chance that X happens at
my station in the next H hours?" for rain, frost, heat, strong gusts and
thunderstorms. See docs/specs/pattern_forecast_v1.md for the full design.

Design principles:
  - Pure Python: no Home Assistant imports and nothing network-capable (a test
    enforces this). The coordinator feeds it numbers and reads numbers back.
  - One small online logistic regression (AdaGrad, L2, learning-rate floor) per
    target and horizon, over a shared pool of 23 standardized features.
  - Every issued forecast waits in a pending buffer until its window closes,
    is scored first (prequential Brier vs. the usual rate and vs. persistence)
    and only then trained on. Missing data is never labelled "no".
  - Bounded state: nothing here grows with time; the whole engine serializes to
    a few tens of KB and degrades gracefully (corrupt or mismatched store ->
    start fresh, per-target label/mask changes reset only that target).
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Any

from .const import (
    PATTERN_BASE_RATE_HALF_LIFE_DAYS,
    PATTERN_BIN_COUNT,
    PATTERN_CHECKPOINT_INTERVAL_S,
    PATTERN_COVERAGE_MIN,
    PATTERN_DEGRADED_MIN_EVENTS,
    PATTERN_DEGRADED_WEEKS,
    PATTERN_DOWNTIME_S,
    PATTERN_DRY_HOURS_CAP,
    PATTERN_EVENT_GAP_H,
    PATTERN_GRAD_CLIP,
    PATTERN_HISTORY_METHOD,
    PATTERN_HISTORY_RETRY_S,
    PATTERN_HISTORY_STD_WEIGHT,
    PATTERN_L2,
    PATTERN_LEARNING_RATE,
    PATTERN_LEARNING_RATE_FLOOR,
    PATTERN_MIN_DAYS_COLLECTING,
    PATTERN_MIN_EVENTS_COLLECTING,
    PATTERN_P_MAX,
    PATTERN_P_MIN,
    PATTERN_PENDING_MAX,
    PATTERN_POOL_ID,
    PATTERN_PRESSURE_SLOTS,
    PATTERN_PRIOR_RATE,
    PATTERN_RAIN_JUMP_CAP_MM,
    PATTERN_RAIN_THRESHOLD_MM,
    PATTERN_RELIABILITY_BINS,
    PATTERN_SCHEMA_VERSION,
    PATTERN_SCORING_WEEKS,
    PATTERN_SKILLED_BSS_MIN,
    PATTERN_SKILLED_MIN_EVENTS,
    PATTERN_STD_FLOOR,
    PATTERN_STD_HALF_LIFE_SAMPLES,
    PATTERN_STD_MIN_N,
    PATTERN_STD_WELFORD_N,
    PATTERN_STORM_MIN_STRIKES,
    PATTERN_STRIKE_JUMP_CAP,
    PATTERN_TICK_CAP_S,
    PATTERN_WEIGHT_NORM_MAX,
    PATTERN_Z_CLIP,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature pool (spec section 2)
# ---------------------------------------------------------------------------

POOL: tuple[str, ...] = (
    "mslp",
    "dp_3h",
    "dp_24h",
    "temp",
    "dpd",
    "dpd_1h",
    "t_1h",
    "t_3h",
    "t_max_24h",
    "wind_u",
    "wind_v",
    "wind_speed",
    "gust_1h",
    "rain_1h",
    "dry_hours",
    "cloud_deficit",
    "solar_ok",
    "last_day_clearness",
    "last_day_clearness_ok",
    "night_frac_12h",
    "hour_sin",
    "hour_cos",
    "lightning_1h",
)
N_POOL = len(POOL)
POOL_INDEX: dict[str, int] = {name: i for i, name in enumerate(POOL)}

_FEATURE_MASKS: dict[str, tuple[str, ...]] = {
    "rain": (
        "mslp",
        "dp_3h",
        "dp_24h",
        "dpd",
        "dpd_1h",
        "t_1h",
        "wind_u",
        "wind_v",
        "rain_1h",
        "dry_hours",
        "cloud_deficit",
        "solar_ok",
        "hour_sin",
        "hour_cos",
    ),
    "frost": (
        "mslp",
        "dp_3h",
        "dp_24h",
        "temp",
        "dpd",
        "t_1h",
        "t_3h",
        "wind_speed",
        "rain_1h",
        "last_day_clearness",
        "last_day_clearness_ok",
        "night_frac_12h",
        "hour_sin",
        "hour_cos",
    ),
    "heat": (
        "mslp",
        "dp_24h",
        "temp",
        "dpd",
        "t_3h",
        "t_max_24h",
        "wind_u",
        "wind_v",
        "dry_hours",
        "cloud_deficit",
        "solar_ok",
        "hour_sin",
        "hour_cos",
    ),
    "gust": (
        "mslp",
        "dp_3h",
        "dp_24h",
        "t_1h",
        "wind_u",
        "wind_v",
        "wind_speed",
        "gust_1h",
        "hour_sin",
        "hour_cos",
    ),
    "storm": (
        "mslp",
        "dp_3h",
        "temp",
        "dpd",
        "dpd_1h",
        "t_1h",
        "gust_1h",
        "rain_1h",
        "cloud_deficit",
        "solar_ok",
        "hour_sin",
        "hour_cos",
        "lightning_1h",
    ),
}

# Features the replay of recorder statistics cannot supply (wind direction is
# not averageable, the storm distance filter is lost); they train as masked.
REPLAY_MASKED_FEATURES: frozenset[str] = frozenset({"wind_u", "wind_v"})

# ---------------------------------------------------------------------------
# Target registry: adding a target is a declaration, not new machinery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetSpec:
    """One model: what it forecasts, over which window, from which features."""

    target_id: str
    kind: str  # rain | frost | heat | gust | storm
    horizon_h: int
    hourly_only: bool = False  # trained on the on-the-hour issues only

    @property
    def window_s(self) -> float:
        return self.horizon_h * 3600.0

    @property
    def features(self) -> tuple[str, ...]:
        return _FEATURE_MASKS[self.kind]

    @property
    def mask_id(self) -> str:
        digest = hashlib.sha1(",".join(self.features).encode()).hexdigest()[:10]
        return f"{self.kind}-m1:{digest}"


TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec("rain_1h", "rain", 1),
    TargetSpec("rain_3h", "rain", 3),
    TargetSpec("rain_6h", "rain", 6),
    TargetSpec("frost_12h", "frost", 12, hourly_only=True),
    TargetSpec("heat_24h", "heat", 24, hourly_only=True),
    TargetSpec("gust_3h", "gust", 3),
    TargetSpec("storm_3h", "storm", 3),
)
TARGET_BY_ID: dict[str, TargetSpec] = {t.target_id: t for t in TARGETS}
RAIN_CHAIN: tuple[str, ...] = ("rain_1h", "rain_3h", "rain_6h")  # nested events -> monotone
STORM_SOURCES: tuple[str, ...] = ("local", "internet")

WEEK_S = 7 * 86400.0
_LOGIT_CLAMP = 30.0
_EPS = 1e-6  # float slack: a sum of 0.2 mm tips can land at 0.19999999999999996


@dataclass(frozen=True)
class Thresholds:
    """The user-facing thresholds that define the labels (existing ws_core settings)."""

    frost_c: float = 0.0
    heat_c: float = 30.0
    gust_ms: float = 17.0
    storm_km: float = 15.0
    rain_mm: float = PATTERN_RAIN_THRESHOLD_MM


def label_id(kind: str, th: Thresholds, storm_source: str | None = None) -> str:
    """Definition + threshold (+ data source for storm) of a label.

    A change in this string resets exactly the models of that kind.
    """
    if kind == "rain":
        return f"rain-v1:mm={th.rain_mm:g}"
    if kind == "frost":
        return f"frost-v1:thr={round(float(th.frost_c), 3)!r}"
    if kind == "heat":
        return f"heat-v1:thr={round(float(th.heat_c), 3)!r}"
    if kind == "gust":
        return f"gust-v1:thr={round(float(th.gust_ms), 3)!r}"
    return f"storm-v1:km={th.storm_km:g}:src={storm_source}"


@dataclass(slots=True)
class Observation:
    """One 60 s tick of station readings. ``None`` means unavailable or flagged."""

    temp: float | None = None
    dpd: float | None = None  # dew point depression, T - Td
    wind_u: float | None = None  # east-west component, m/s
    wind_v: float | None = None  # north-south component, m/s
    wind_speed: float | None = None
    gust: float | None = None
    rain_total: float | None = None  # cumulative counter, mm
    strikes_total: float | None = None  # cumulative lightning counter of the active storm source
    strike_km: float | None = None  # distance of the latest strike, when a distance sensor exists


@dataclass(slots=True)
class Instant:
    """Quantities the coordinator already has at issue time (every 15 min)."""

    mslp: float | None = None
    dp_3h: float | None = None
    temp: float | None = None
    dpd: float | None = None
    t_max_24h: float | None = None
    t_min_24h: float | None = None
    cloud_deficit: float = 0.0
    solar_ok: bool = False
    last_day_clearness: float | None = None
    night_frac_12h: float | None = None
    local_hour: float = 12.0


@dataclass
class HourlyHistory:
    """Hourly long-term statistics prepared for replay (all lists have ``n`` entries).

    Entry ``j`` describes the hour ``[start_ts + j*3600, start_ts + (j+1)*3600)``.
    ``None`` means the statistic is missing for that hour (never read as zero).
    Unit conversion, calibration offsets, sea-level reduction and the dew point
    depression are done by the caller, through the same normalization as live data.
    """

    start_ts: float
    n: int
    mslp: list[float | None]
    temp: list[float | None]  # hourly mean
    temp_min: list[float | None]
    temp_max: list[float | None]
    dpd: list[float | None]
    wind: list[float | None]  # hourly mean speed
    gust: list[float | None]  # hourly max
    rain: list[float | None]  # mm that fell in the hour
    strikes: list[float | None]  # lightning strikes in the hour
    night_frac: list[float | None]  # night fraction of the 12 h after the hour
    tz_offset: list[float]  # local UTC offset, seconds


# ---------------------------------------------------------------------------
# Small math helpers
# ---------------------------------------------------------------------------


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _sigmoid(s: float) -> float:
    s = max(-_LOGIT_CLAMP, min(_LOGIT_CLAMP, s))
    return 1.0 / (1.0 + math.exp(-s))


def _logit(p: float) -> float:
    p = max(1e-6, min(1.0 - 1e-6, p))
    return math.log(p / (1.0 - p))


def _floats_ok(seq: Any, n: int) -> bool:
    return isinstance(seq, list) and len(seq) == n and all(_finite(v) for v in seq)


def _opt_ok(v: Any) -> bool:
    return v is None or _finite(v)


def _episode_step(ep: dict[str, Any], ts: float, amount: float, gap_s: float, min_amount: float) -> bool:
    """Advance an activity episode; True when this step makes it count as an event."""
    if ep["ts"] is None or ts - ep["ts"] >= gap_s:
        ep["amt"] = 0.0
        ep["counted"] = False
    ep["ts"] = ts
    ep["amt"] += amount
    if not ep["counted"] and ep["amt"] >= min_amount - _EPS:
        ep["counted"] = True
        return True
    return False


def _rate_update(state: list, y: float, n_half: float) -> None:
    """Running rate ``[rate, n]``: shrinks toward the prior early, ~30-day EMA later."""
    rate, n = state
    a_ema = 1.0 - 0.5 ** (1.0 / max(1.0, n_half))
    alpha = max(1.0 / (n + 10.0), a_ema)
    state[0] = rate + alpha * (y - rate)
    state[1] = n + 1


# ---------------------------------------------------------------------------
# Shared standardizer
# ---------------------------------------------------------------------------


class Standardizer:
    """Per-feature running mean/variance: Welford first, then a slow EMA; z-clipped."""

    def __init__(self) -> None:
        self.mean: list[float] = [0.0] * N_POOL
        self.var: list[float] = [1.0] * N_POOL
        self.n: list[int] = [0] * N_POOL

    def update(self, i: int, x: float, weight: float = 1.0) -> None:
        n = self.n[i] + 1
        self.n[i] = n
        if n <= PATTERN_STD_WELFORD_N:
            d = x - self.mean[i]
            self.mean[i] += d / n
            m2 = self.var[i] * (n - 1) + d * (x - self.mean[i])
            self.var[i] = max(0.0, m2 / n)
        else:
            a = 1.0 - 0.5 ** (weight / PATTERN_STD_HALF_LIFE_SAMPLES)
            d = x - self.mean[i]
            self.mean[i] += a * d
            self.var[i] = (1.0 - a) * (self.var[i] + a * d * d)

    def z(self, i: int, x: float | None) -> float:
        if x is None or self.n[i] < PATTERN_STD_MIN_N:
            return 0.0
        std = max(math.sqrt(max(self.var[i], 0.0)), PATTERN_STD_FLOOR)
        return max(-PATTERN_Z_CLIP, min(PATTERN_Z_CLIP, (x - self.mean[i]) / std))

    def to_dict(self) -> dict[str, Any]:
        return {"mean": list(self.mean), "var": list(self.var), "n": list(self.n)}

    @classmethod
    def from_dict(cls, d: Any) -> Standardizer | None:
        if not isinstance(d, dict):
            return None
        mean, var, n = d.get("mean"), d.get("var"), d.get("n")
        if not (_floats_ok(mean, N_POOL) and _floats_ok(var, N_POOL) and _floats_ok(n, N_POOL)):
            return None
        if any(v < 0 for v in var) or any(v < 0 for v in n):
            return None
        s = cls()
        s.mean = [float(v) for v in mean]
        s.var = [float(v) for v in var]
        s.n = [int(v) for v in n]
        return s


# ---------------------------------------------------------------------------
# One model = online logistic regression with AdaGrad
# ---------------------------------------------------------------------------


class ModelState:
    """Weights, accumulators, checkpoint and bookkeeping of one target/horizon."""

    def __init__(self, spec: TargetSpec, label: str) -> None:
        self.spec = spec
        self.label_id = label
        self.mask_id = spec.mask_id
        self.idx: tuple[int, ...] = tuple(POOL_INDEX[f] for f in spec.features)
        k = len(self.idx) + 1  # bias first
        self.w: list[float] = [0.0] * k
        self.w[0] = _logit(PATTERN_PRIOR_RATE[spec.kind])
        self.g2: list[float] = [0.0] * k
        self.n_updates = 0
        self.cp_w: list[float] = list(self.w)
        self.cp_g2: list[float] = list(self.g2)
        self.cp_at: float | None = None
        self.maturity = "collecting"
        self.was_skilled = False
        self.first_scored: float | None = None
        self.last_scored: float | None = None
        self.hist_days = 0.0
        self.ev_live = 0
        self.ev_hist = 0
        self.discarded = 0

    # -- prediction ---------------------------------------------------------

    def zvec(self, std: Standardizer, feat: list[float | None], masked: frozenset[int] = frozenset()) -> list[float]:
        return [0.0 if i in masked else std.z(i, feat[i]) for i in self.idx]

    def predict(self, std: Standardizer, feat: list[float | None]) -> float:
        z = self.zvec(std, feat)
        s = self.w[0] + sum(w * v for w, v in zip(self.w[1:], z, strict=True))
        return max(PATTERN_P_MIN, min(PATTERN_P_MAX, _sigmoid(s)))

    # -- training -----------------------------------------------------------

    def train(
        self,
        std: Standardizer,
        feat: list[float | None],
        y: float,
        ts: float,
        masked: frozenset[int] = frozenset(),
    ) -> bool:
        """One SGD step. Returns False when the numeric guard restored the checkpoint."""
        z = self.zvec(std, feat, masked)
        active = [i not in masked for i in self.idx]
        s = self.w[0] + sum(w * v for w, v in zip(self.w[1:], z, strict=True))
        err = _sigmoid(s) - y
        clip = PATTERN_GRAD_CLIP
        # bias (no L2)
        g = max(-clip, min(clip, err))
        self._step(0, g)
        for j, (zj, act) in enumerate(zip(z, active, strict=True), start=1):
            if not act:
                continue
            g = max(-clip, min(clip, err * zj + PATTERN_L2 * self.w[j]))
            self._step(j, g)
        # weight-norm bound
        norm = math.sqrt(sum(w * w for w in self.w[1:]))
        if norm > PATTERN_WEIGHT_NORM_MAX:
            scale = PATTERN_WEIGHT_NORM_MAX / norm
            self.w[1:] = [w * scale for w in self.w[1:]]
        if not all(math.isfinite(v) for v in self.w) or not all(math.isfinite(v) for v in self.g2):
            _LOGGER.warning(
                "ws_core pattern forecast: non-finite weights in %s, restoring checkpoint", self.spec.target_id
            )
            self.w = list(self.cp_w)
            self.g2 = list(self.cp_g2)
            return False
        self.n_updates += 1
        if self.cp_at is None or ts - self.cp_at >= PATTERN_CHECKPOINT_INTERVAL_S:
            self.cp_w = list(self.w)
            self.cp_g2 = list(self.g2)
            self.cp_at = ts
        return True

    def _step(self, j: int, g: float) -> None:
        self.g2[j] += g * g
        rate = max(PATTERN_LEARNING_RATE / math.sqrt(self.g2[j] + 1e-8), PATTERN_LEARNING_RATE_FLOOR)
        self.w[j] -= rate * g

    def contributions(self, std: Standardizer, feat: list[float | None]) -> dict[str, tuple[float, float]]:
        """Per-feature (z-score, signed contribution w*z) for the explanation."""
        out: dict[str, tuple[float, float]] = {}
        for w, i in zip(self.w[1:], self.idx, strict=True):
            z = std.z(i, feat[i])
            out[POOL[i]] = (z, w * z)
        return out

    # -- (de)serialization --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_id": self.label_id,
            "mask_id": self.mask_id,
            "w": list(self.w),
            "g2": list(self.g2),
            "n_updates": self.n_updates,
            "checkpoint": {"w": list(self.cp_w), "g2": list(self.cp_g2), "at": self.cp_at},
            "maturity": self.maturity,
            "was_skilled": self.was_skilled,
            "first_scored": self.first_scored,
            "last_scored": self.last_scored,
            "hist_days": self.hist_days,
            "events": {"live": self.ev_live, "history": self.ev_hist},
            "discarded": self.discarded,
        }

    @classmethod
    def from_dict(cls, spec: TargetSpec, label: str, d: Any) -> ModelState | None:
        """Validated load; ``None`` when the entry is unusable or its ids no longer match."""
        if not isinstance(d, dict):
            return None
        if d.get("label_id") != label or d.get("mask_id") != spec.mask_id:
            return None
        k = len(spec.features) + 1
        cp = d.get("checkpoint")
        ev = d.get("events")
        if not (_floats_ok(d.get("w"), k) and _floats_ok(d.get("g2"), k)):
            return None
        if not (isinstance(cp, dict) and _floats_ok(cp.get("w"), k) and _floats_ok(cp.get("g2"), k)):
            return None
        if not (isinstance(ev, dict) and _finite(ev.get("live")) and _finite(ev.get("history"))):
            return None
        if d.get("maturity") not in MATURITY_STATES:
            return None
        for key in ("n_updates", "hist_days", "discarded"):
            if not _finite(d.get(key)):
                return None
        for key in ("first_scored", "last_scored"):
            if not _opt_ok(d.get(key)):
                return None
        if not _opt_ok(cp.get("at")):
            return None
        m = cls(spec, label)
        m.w = [float(v) for v in d["w"]]
        m.g2 = [float(v) for v in d["g2"]]
        m.n_updates = int(d["n_updates"])
        m.cp_w = [float(v) for v in cp["w"]]
        m.cp_g2 = [float(v) for v in cp["g2"]]
        m.cp_at = cp.get("at")
        m.maturity = d["maturity"]
        m.was_skilled = bool(d.get("was_skilled", False))
        m.first_scored = d.get("first_scored")
        m.last_scored = d.get("last_scored")
        m.hist_days = float(d["hist_days"])
        m.ev_live = int(ev["live"])
        m.ev_hist = int(ev["history"])
        m.discarded = int(d["discarded"])
        return m


MATURITY_STATES = ("collecting", "learning", "skilled", "degraded")

# ---------------------------------------------------------------------------
# Explanation: deterministic factor keys
# ---------------------------------------------------------------------------

# (feature, sign of z) -> factor key, per target kind. A factor is only
# reported when its condition is actually present (the sign matches), so
# "clear_sky: lowers" always reads true.
_FACTOR_MAP: dict[str, dict[tuple[str, int], str]] = {
    "rain": {
        ("dp_3h", -1): "pressure_falling",
        ("dp_3h", 1): "pressure_rising",
        ("dp_24h", -1): "pressure_falling",
        ("dp_24h", 1): "pressure_rising",
        ("dpd", -1): "air_near_saturation",
        ("dpd", 1): "dry_air",
        ("dpd_1h", -1): "air_near_saturation",
        ("dpd_1h", 1): "dry_air",
        ("wind_u", 0): "wet_wind_sector",
        ("wind_v", 0): "wet_wind_sector",
        ("rain_1h", 1): "raining_now",
        ("rain_1h", -1): "long_dry_spell",
        ("dry_hours", 1): "long_dry_spell",
        ("dry_hours", -1): "raining_now",
        ("cloud_deficit", 1): "cloudy",
        ("cloud_deficit", -1): "clear_sky",
    },
    "frost": {
        ("dp_3h", -1): "pressure_falling",
        ("dp_3h", 1): "pressure_rising",
        ("dp_24h", -1): "pressure_falling",
        ("dp_24h", 1): "pressure_rising",
        ("temp", -1): "already_cold",
        ("dpd", 1): "dry_air",
        ("dpd", -1): "air_near_saturation",
        ("t_1h", -1): "cooling_fast",
        ("t_3h", -1): "cooling_fast",
        ("wind_speed", -1): "calm_wind",
        ("wind_speed", 1): "windy_now",
        ("rain_1h", 1): "raining_now",
        ("last_day_clearness", 1): "clear_sky",
        ("last_day_clearness", -1): "cloudy",
        ("night_frac_12h", 1): "long_night",
    },
    "heat": {
        ("dp_24h", -1): "pressure_falling",
        ("dp_24h", 1): "pressure_rising",
        ("temp", 1): "hot_yesterday",
        ("t_max_24h", 1): "hot_yesterday",
        ("dpd", 1): "dry_air",
        ("dpd", -1): "air_near_saturation",
        ("wind_u", 0): "warm_wind_sector",
        ("wind_v", 0): "warm_wind_sector",
        ("dry_hours", 1): "long_dry_spell",
        ("cloud_deficit", -1): "sunny",
        ("cloud_deficit", 1): "cloudy",
    },
    "gust": {
        ("dp_3h", -1): "pressure_falling",
        ("dp_3h", 1): "pressure_rising",
        ("dp_24h", -1): "pressure_falling",
        ("dp_24h", 1): "pressure_rising",
        ("t_1h", -1): "cooling_fast",
        ("wind_u", 0): "windy_now",
        ("wind_v", 0): "windy_now",
        ("wind_speed", 1): "windy_now",
        ("wind_speed", -1): "calm_wind",
        ("gust_1h", 1): "gusty_now",
        ("gust_1h", -1): "calm_wind",
    },
    "storm": {
        ("dp_3h", -1): "pressure_falling",
        ("dp_3h", 1): "pressure_rising",
        ("temp", 1): "warm_and_humid",
        ("dpd", -1): "warm_and_humid",
        ("dpd", 1): "dry_air",
        ("dpd_1h", -1): "air_near_saturation",
        ("t_1h", -1): "cooling_fast",
        ("gust_1h", 1): "gusty_now",
        ("rain_1h", 1): "raining_now",
        ("cloud_deficit", 1): "cloudy",
        ("cloud_deficit", -1): "clear_sky",
        ("lightning_1h", 1): "lightning_nearby",
    },
}

FACTOR_KEYS: tuple[str, ...] = tuple(
    sorted({k for m in _FACTOR_MAP.values() for k in m.values()} | {"afternoon", "night"})
)


def _top_factors(
    model: ModelState, std: Standardizer, feat: list[float | None], local_hour: float
) -> list[dict[str, str]]:
    contrib = model.contributions(std, feat)
    kmap = _FACTOR_MAP[model.spec.kind]
    totals: dict[str, float] = {}
    for name, (z, c) in contrib.items():
        if name in ("hour_sin", "hour_cos"):
            key = (
                "afternoon"
                if 12.0 <= local_hour < 18.0
                else "night"
                if (local_hour >= 21.0 or local_hour < 5.0)
                else None
            )
        else:
            sign = 0 if (name, 0) in kmap else (1 if z > 0 else -1 if z < 0 else None)
            key = kmap.get((name, sign)) if sign is not None else None
        if key is None:
            continue
        totals[key] = totals.get(key, 0.0) + c
    ranked = sorted((kv for kv in totals.items() if abs(kv[1]) > 1e-6), key=lambda kv: -abs(kv[1]))
    return [{"factor": k, "effect": "raises" if v > 0 else "lowers"} for k, v in ranked[:3]]


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

_TALLY_DEFAULTS: dict[str, Any] = {
    "rs": 0.0,  # rain sum (mm)
    "rc": 0.0,  # rain coverage (s)
    "rbad": False,
    "tn": None,  # lowest temperature
    "tx": None,  # highest temperature
    "tc": 0.0,
    "gx": None,  # highest gust
    "gc": 0.0,
    "ls": 0.0,  # strikes within proximity
    "lc": 0.0,
    "lbad": False,
    "down": False,  # HA was down (or restarted) while this window was open
}
_GROUPS = ("rain", "temp", "gust", "storm")


class PatternEngine:
    """All Pattern Forecast state and logic for one config entry."""

    def __init__(
        self,
        thresholds: Thresholds | None = None,
        storm_source: str | None = None,
        source_fingerprint: str = "",
        tick_cap_s: float = PATTERN_TICK_CAP_S,
    ) -> None:
        self.thresholds = thresholds or Thresholds()
        self.storm_source = storm_source if storm_source in STORM_SOURCES else None
        self.source_fingerprint = source_fingerprint
        self.tick_cap_s = tick_cap_s
        self.std = Standardizer()
        self.models: dict[str, ModelState] = {}
        self.pending: list[dict[str, Any]] = []
        self.pressure: deque[list[float]] = deque(maxlen=PATTERN_PRESSURE_SLOTS)
        self.bins: deque[dict[str, Any]] = deque(maxlen=PATTERN_BIN_COUNT)
        self.scoring: dict[str, list[list[float]]] = {}
        self.reliability: dict[str, list[list[float]]] = {}
        self.base_rate: dict[str, list[float]] = {}
        self.cond: dict[str, list[list[float]]] = {}
        self.history_learn: dict[str, Any] = {}
        self.last_trained_at: float | None = None
        self.first_obs_ts: float | None = None
        self.last_rain_ts: float | None = None
        self.last_day_clear: list[float] | None = None  # [clearness, ts] carried through the night
        self._episodes: dict[str, dict[str, Any]] = {
            "rain": {"ts": None, "amt": 0.0, "counted": False},
            "gust": {"ts": None, "amt": 0.0, "counted": False},
            "storm": {"ts": None, "amt": 0.0, "counted": False},
            "frost": {"id": None},
            "heat": {"id": None},
        }
        # volatile (not persisted)
        self._last_obs_ts: float | None = None
        self._last_group: dict[str, float | None] = dict.fromkeys(_GROUPS)
        self._last_rain_total: float | None = None
        self._last_strikes_total: float | None = None
        self._acc: dict[str, Any] = self._new_acc()
        self._tz_offset_s = 0.0
        self._restored = False
        self._last_issue_ts: float | None = None
        self._last_issue: dict[str, dict[str, Any]] = {}
        self._now_ts: float = 0.0
        self.counter_resets = {"rain": 0, "storm": 0}
        self.configure(self.thresholds, self.storm_source)

    # -- configuration / reset ----------------------------------------------

    def active_target_ids(self) -> list[str]:
        return [t.target_id for t in TARGETS if t.kind != "storm" or self.storm_source is not None]

    def _label_for(self, spec: TargetSpec) -> str:
        return label_id(spec.kind, self.thresholds, self.storm_source)

    def configure(self, thresholds: Thresholds, storm_source: str | None) -> list[str]:
        """Apply thresholds and storm source; return the target ids that were reset.

        Only a model whose label definition changed is reset (spec section 4);
        a storm target disappears when no storm source is available.
        """
        self.thresholds = thresholds
        self.storm_source = storm_source if storm_source in STORM_SOURCES else None
        reset: list[str] = []
        for spec in TARGETS:
            tid = spec.target_id
            if spec.kind == "storm" and self.storm_source is None:
                if tid in self.models:
                    self._drop_model(tid)
                    reset.append(tid)
                continue
            label = self._label_for(spec)
            existing = self.models.get(tid)
            if existing is None:
                self._init_model(spec, label)
            elif existing.label_id != label or existing.mask_id != spec.mask_id:
                self._drop_model(tid)
                self._init_model(spec, label)
                reset.append(tid)
        return reset

    def _init_model(self, spec: TargetSpec, label: str) -> None:
        tid = spec.target_id
        self.models[tid] = ModelState(spec, label)
        self.scoring[tid] = []
        self.reliability[tid] = [[0.0, 0.0, 0.0] for _ in range(PATTERN_RELIABILITY_BINS)]
        prior = PATTERN_PRIOR_RATE[spec.kind]
        self.base_rate[tid] = [prior, 0]
        self.cond[tid] = [[prior, 0], [prior, 0]]

    def _drop_model(self, tid: str) -> None:
        self.models.pop(tid, None)
        self.scoring.pop(tid, None)
        self.reliability.pop(tid, None)
        self.base_rate.pop(tid, None)
        self.cond.pop(tid, None)
        self._last_issue.pop(tid, None)
        self.history_learn.get("targets", {}).pop(tid, None)
        for e in self.pending:
            for key in ("p", "c", "h"):
                e[key].pop(tid, None)
        self.pending = [e for e in self.pending if e["p"]]

    def reset_target(self, tid: str) -> None:
        spec = TARGET_BY_ID[tid]
        self._drop_model(tid)
        if spec.kind != "storm" or self.storm_source is not None:
            self._init_model(spec, self._label_for(spec))

    def reset_all(self) -> None:
        """Back to a fresh engine (same configuration)."""
        fresh = PatternEngine(self.thresholds, self.storm_source, self.source_fingerprint, self.tick_cap_s)
        self.__dict__.update(fresh.__dict__)

    # -- 60 s tick: tallies, events, label resolution -----------------------

    @staticmethod
    def _new_acc() -> dict[str, Any]:
        return {"n": 0, "t": None, "d": None, "u": 0.0, "v": 0.0, "s": 0.0, "wn": 0, "g": None, "r": None, "k": None}

    def _cov(self, group: str, ok: bool, ts: float) -> float:
        """Seconds of coverage this tick adds for an input group (0 across any gap)."""
        if not ok:
            self._last_group[group] = None
            return 0.0
        prev = self._last_group[group]
        self._last_group[group] = ts
        if prev is None:
            return 0.0
        return max(0.0, min(ts - prev, self.tick_cap_s))

    def observe(self, ts: float, obs: Observation, tz_offset_s: float = 0.0) -> None:
        """Feed one 60 s tick: update every open window's tally and resolve closed windows."""
        th = self.thresholds
        self._now_ts = ts
        self._tz_offset_s = tz_offset_s
        if self.first_obs_ts is None:
            self.first_obs_ts = ts
        if self._restored or (self._last_obs_ts is not None and ts - self._last_obs_ts > PATTERN_DOWNTIME_S):
            # downtime or a restart: forecasts still open cannot be labelled (never "no")
            for e in self.pending:
                e["down"] = True
            self._restored = False
        self._last_obs_ts = ts
        acc = self._acc

        # ---- rain (cumulative counter: positive deltas only, decrease = reset)
        rain_ok = obs.rain_total is not None
        rain_delta = 0.0
        rain_bad = False
        if rain_ok:
            total = float(obs.rain_total)  # type: ignore[arg-type]
            if self._last_rain_total is not None:
                d = total - self._last_rain_total
                if d < 0:
                    self.counter_resets["rain"] += 1
                elif d > PATTERN_RAIN_JUMP_CAP_MM:
                    rain_bad = True
                else:
                    rain_delta = d
            self._last_rain_total = total
            acc["r"] = (acc["r"] or 0.0) + rain_delta
            if rain_delta > 0:
                self.last_rain_ts = ts
                self._episode("rain", ts, rain_delta, PATTERN_EVENT_GAP_H["rain"], th.rain_mm)
        rain_cov = self._cov("rain", rain_ok, ts)

        # ---- temperature
        temp_ok = obs.temp is not None
        if temp_ok:
            t = float(obs.temp)  # type: ignore[arg-type]
            acc["t"] = t
            if t <= th.frost_c:
                self._id_event("frost", ts, offset_s=-43200.0)
            if t >= th.heat_c:
                self._id_event("heat", ts, offset_s=0.0)
        if obs.dpd is not None:
            acc["d"] = float(obs.dpd)
        temp_cov = self._cov("temp", temp_ok, ts)

        # ---- wind / gust
        if obs.wind_u is not None and obs.wind_v is not None and obs.wind_speed is not None:
            acc["u"] += float(obs.wind_u)
            acc["v"] += float(obs.wind_v)
            acc["s"] += float(obs.wind_speed)
            acc["wn"] += 1
        gust_ok = obs.gust is not None
        if gust_ok:
            g = float(obs.gust)  # type: ignore[arg-type]
            acc["g"] = g if acc["g"] is None else max(acc["g"], g)
            if g >= th.gust_ms:
                self._episode("gust", ts, 1.0, PATTERN_EVENT_GAP_H["gust"], 1.0)
        gust_cov = self._cov("gust", gust_ok, ts)

        # ---- lightning (counter of the active storm source)
        storm_on = self.storm_source is not None
        storm_ok = storm_on and obs.strikes_total is not None
        strike_delta = 0.0
        strike_bad = False
        if storm_ok:
            total = float(obs.strikes_total)  # type: ignore[arg-type]
            if self._last_strikes_total is not None:
                d = total - self._last_strikes_total
                if d < 0:
                    self.counter_resets["storm"] += 1
                elif d > PATTERN_STRIKE_JUMP_CAP:
                    strike_bad = True
                elif obs.strike_km is None or obs.strike_km <= th.storm_km:
                    strike_delta = d
            self._last_strikes_total = total
            acc["k"] = (acc["k"] or 0.0) + strike_delta
            if strike_delta > 0:
                self._episode("storm", ts, strike_delta, PATTERN_EVENT_GAP_H["storm"], PATTERN_STORM_MIN_STRIKES)
        storm_cov = self._cov("storm", storm_ok, ts)
        acc["n"] += 1

        # ---- update every open entry's tally, then resolve closed windows
        for e in self.pending:
            if rain_ok:
                e["rs"] += rain_delta
                e["rc"] += rain_cov
                if rain_bad:
                    e["rbad"] = True
            if temp_ok:
                t = float(obs.temp)  # type: ignore[arg-type]
                e["tn"] = t if e["tn"] is None else min(e["tn"], t)
                e["tx"] = t if e["tx"] is None else max(e["tx"], t)
                e["tc"] += temp_cov
            if gust_ok:
                g = float(obs.gust)  # type: ignore[arg-type]
                e["gx"] = g if e["gx"] is None else max(e["gx"], g)
                e["gc"] += gust_cov
            if storm_ok:
                e["ls"] += strike_delta
                e["lc"] += storm_cov
                if strike_bad:
                    e["lbad"] = True
        self._resolve_due(ts)

    def _episode(self, kind: str, ts: float, amount: float, gap_h: float, min_amount: float) -> None:
        if _episode_step(self._episodes[kind], ts, amount, gap_h * 3600.0, min_amount):
            self._count_event(kind, ts)

    def _id_event(self, kind: str, ts: float, offset_s: float) -> None:
        """Frost nights (noon-to-noon) and hot days (local date) count once per id."""
        ident = math.floor((ts + self._tz_offset_s + offset_s) / 86400.0)
        ep = self._episodes[kind]
        if ep["id"] != ident:
            ep["id"] = ident
            self._count_event(kind, ts)

    def _count_event(self, kind: str, ts: float) -> None:
        wk = int(ts // WEEK_S)
        for tid, m in self.models.items():
            if m.spec.kind == kind:
                m.ev_live += 1
                self._week_row(tid, wk)[7] += 1

    # -- label resolution ---------------------------------------------------

    def _new_entry(self, ts: float, hourly: bool, feat: list[float | None]) -> dict[str, Any]:
        e: dict[str, Any] = {"ts": ts, "hr": hourly, "f": feat, "p": {}, "c": {}, "h": {}}
        e.update(_TALLY_DEFAULTS)
        return e

    def _label(self, e: dict[str, Any], spec: TargetSpec) -> bool | None:
        """True / False, or None when the window cannot be labelled (never "no")."""
        th = self.thresholds
        need = PATTERN_COVERAGE_MIN * spec.window_s
        k = spec.kind
        if e["down"]:
            return None
        if k == "rain":
            return None if (e["rbad"] or e["rc"] < need) else e["rs"] >= th.rain_mm - _EPS
        if k == "frost":
            return None if (e["tc"] < need or e["tn"] is None) else e["tn"] <= th.frost_c
        if k == "heat":
            return None if (e["tc"] < need or e["tx"] is None) else e["tx"] >= th.heat_c
        if k == "gust":
            return None if (e["gc"] < need or e["gx"] is None) else e["gx"] >= th.gust_ms
        return None if (e["lbad"] or e["lc"] < need) else e["ls"] >= PATTERN_STORM_MIN_STRIKES - _EPS

    def _resolve_due(self, ts: float) -> None:
        keep: list[dict[str, Any]] = []
        for e in self.pending:
            for tid in list(e["p"]):
                spec = TARGET_BY_ID[tid]
                if ts - e["ts"] < spec.window_s:
                    continue
                label = self._label(e, spec)
                p = e["p"].pop(tid)
                cond = e["c"].pop(tid, 0)
                heur = e["h"].pop(tid, None)
                m = self.models.get(tid)
                if m is None:
                    continue
                if label is None:
                    m.discarded += 1
                    continue
                self._score_and_train(m, e["f"], p, cond, heur, label, ts)
            if e["p"] and ts - e["ts"] < 86400.0 + 3600.0:
                keep.append(e)
        self.pending = keep

    def _week_row(self, tid: str, wk: int) -> list[float]:
        rows = self.scoring[tid]
        if rows and rows[-1][0] == wk:
            return rows[-1]
        for r in reversed(rows):
            if r[0] == wk:
                return r
        row = [float(wk), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        rows.append(row)
        rows.sort(key=lambda r: r[0])
        cutoff = wk - PATTERN_SCORING_WEEKS - 1
        while rows and rows[0][0] < cutoff:
            rows.pop(0)
        return row

    def _score_and_train(
        self, m: ModelState, feat: list[float | None], p: float, cond: int, heur: float | None, label: bool, ts: float
    ) -> None:
        tid = m.spec.target_id
        y = 1.0 if label else 0.0
        # ---- score first (prequential): every baseline is the value before this label
        usual = self.base_rate[tid][0]
        crate, cn = self.cond[tid][cond]
        persist = crate if cn >= 10 else usual
        row = self._week_row(tid, int(ts // WEEK_S))
        row[1] += 1
        row[2] += (p - y) ** 2
        row[3] += (usual - y) ** 2
        row[4] += (persist - y) ** 2
        if heur is not None:
            row[5] += (heur - y) ** 2
            row[6] += 1
        rel = self.reliability[tid][min(PATTERN_RELIABILITY_BINS - 1, int(p * PATTERN_RELIABILITY_BINS))]
        rel[0] += 1
        rel[1] += p
        rel[2] += y
        if rel[0] > 20000:
            for r in self.reliability[tid]:
                r[0] *= 0.5
                r[1] *= 0.5
                r[2] *= 0.5
        per_day = 24.0 if m.spec.hourly_only else 96.0
        n_half = PATTERN_BASE_RATE_HALF_LIFE_DAYS * per_day
        _rate_update(self.base_rate[tid], y, n_half)
        _rate_update(self.cond[tid][cond], y, n_half)
        if m.first_scored is None:
            m.first_scored = ts
        m.last_scored = ts
        # ---- then train
        m.train(self.std, feat, y, ts)
        self.last_trained_at = ts

    # -- 15 min issue --------------------------------------------------------

    def _close_bin(self, ts: float) -> None:
        acc = self._acc
        if acc["n"] > 0:
            wn = acc["wn"]
            self.bins.append(
                {
                    "ts": ts,
                    "t": acc["t"],
                    "d": acc["d"],
                    "u": acc["u"] / wn if wn else None,
                    "v": acc["v"] / wn if wn else None,
                    "s": acc["s"] / wn if wn else None,
                    "g": acc["g"],
                    "r": acc["r"],
                    "k": acc["k"],
                    "n": wn,
                }
            )
        self._acc = self._new_acc()

    def pressure_change_24h(self, ts: float, mslp: float | None) -> float | None:
        """Change versus the sample ~24 h ago (None until one exists)."""
        if mslp is None:
            return None
        best = None
        for t, v in self.pressure:
            if abs((ts - t) - 86400.0) <= 450.0 and (
                best is None or abs((ts - t) - 86400.0) < abs((ts - best[0]) - 86400.0)
            ):
                best = (t, v)
        return None if best is None else mslp - best[1]

    @staticmethod
    def pressure_seed_from_history(hist: HourlyHistory) -> list[list[float]]:
        """15-min sea-level pressure points for the last ~25 h of a replay.

        Hourly means sit at the middle of their hour; points on the :00/:15/:30/:45
        grid are interpolated between neighbouring hours (never across a missing
        hour), so the live 24 h pressure change has a reference on day one.
        """
        first = max(0, hist.n - 27)
        centers = [
            (hist.start_ts + j * 3600.0 + 1800.0, float(v))
            for j, v in enumerate(hist.mslp[first:], start=first)
            if v is not None
        ]
        out: list[list[float]] = []
        for (t0, v0), (t1, v1) in zip(centers, centers[1:], strict=False):
            if t1 - t0 > 3600.0 + 1.0:
                continue
            t = math.ceil(t0 / 900.0) * 900.0
            while t < t1:
                out.append([t, round(v0 + (v1 - v0) * (t - t0) / (t1 - t0), 2)])
                t += 900.0
        if centers and centers[-1][0] % 900.0 == 0:
            out.append([centers[-1][0], round(centers[-1][1], 2)])
        return out

    def seed_pressure(self, points: list[list[float]]) -> int:
        """Fill gaps in the 24 h pressure history from replayed statistics.

        Live readings always win: a seed point within 7.5 min of a live one is
        dropped. Returns how many seed points were kept.
        """
        live = [list(p) for p in self.pressure]
        seeds = [
            [float(t), float(v)]
            for t, v in points
            if _finite(t) and _finite(v) and not any(abs(t - q[0]) <= 450.0 for q in live)
        ]
        merged = sorted(live + seeds, key=lambda p: p[0])[-PATTERN_PRESSURE_SLOTS:]
        self.pressure = deque(merged, maxlen=PATTERN_PRESSURE_SLOTS)
        kept = {p[0] for p in merged}
        return sum(1 for s in seeds if s[0] in kept)

    def _features(self, ts: float, inst: Instant) -> tuple[dict[str, float | None], dict[str, bool]]:
        """Raw feature values plus the per-target 'wet/hot/...now' persistence conditions."""
        bins = list(self.bins)
        hour_bins = [b for b in bins if ts - b["ts"] < 3300.0]

        def ref(age_s: float, tol_s: float) -> dict[str, Any] | None:
            cand = [b for b in bins if abs((ts - b["ts"]) - age_s) <= tol_s]
            return min(cand, key=lambda b: abs((ts - b["ts"]) - age_s)) if cand else None

        def mean_of(key: str) -> float | None:
            pts = [(b[key], b["n"]) for b in hour_bins if b[key] is not None and b["n"]]
            if len(pts) < 3:
                return None
            w = sum(n for _, n in pts)
            return sum(v * n for v, n in pts) / w if w else None

        f: dict[str, float | None] = dict.fromkeys(POOL)
        f["mslp"] = inst.mslp
        f["dp_3h"] = inst.dp_3h
        f["dp_24h"] = self.pressure_change_24h(ts, inst.mslp)
        f["temp"] = inst.temp
        f["dpd"] = inst.dpd
        r1, r3 = ref(3600.0, 450.0), ref(10800.0, 900.0)
        if inst.dpd is not None and r1 is not None and r1["d"] is not None:
            f["dpd_1h"] = inst.dpd - r1["d"]
        if inst.temp is not None and r1 is not None and r1["t"] is not None:
            f["t_1h"] = inst.temp - r1["t"]
        if inst.temp is not None and r3 is not None and r3["t"] is not None:
            f["t_3h"] = inst.temp - r3["t"]
        f["t_max_24h"] = inst.t_max_24h
        f["wind_u"] = mean_of("u")
        f["wind_v"] = mean_of("v")
        f["wind_speed"] = mean_of("s")
        gusts = [b["g"] for b in hour_bins if b["g"] is not None]
        f["gust_1h"] = max(gusts) if len(gusts) >= 3 else None
        rains = [b["r"] for b in hour_bins if b["r"] is not None]
        rain_1h_mm = sum(rains) if len(rains) >= 3 else None
        f["rain_1h"] = None if rain_1h_mm is None else math.log1p(max(0.0, rain_1h_mm))
        anchor = self.last_rain_ts if self.last_rain_ts is not None else (self.first_obs_ts or ts)
        f["dry_hours"] = math.log1p(min(PATTERN_DRY_HOURS_CAP, max(0.0, (ts - anchor) / 3600.0)))
        f["cloud_deficit"] = float(inst.cloud_deficit)
        f["solar_ok"] = 1.0 if inst.solar_ok else 0.0
        f["last_day_clearness"] = 0.0 if inst.last_day_clearness is None else float(inst.last_day_clearness)
        f["last_day_clearness_ok"] = 0.0 if inst.last_day_clearness is None else 1.0
        f["night_frac_12h"] = inst.night_frac_12h
        ang = 2.0 * math.pi * (inst.local_hour % 24.0) / 24.0
        f["hour_sin"] = math.sin(ang)
        f["hour_cos"] = math.cos(ang)
        strikes = [b["k"] for b in hour_bins if b["k"] is not None]
        f["lightning_1h"] = math.log1p(sum(strikes)) if (len(strikes) >= 3 and self.storm_source) else None

        gust_3h = [b["g"] for b in bins if b["g"] is not None and ts - b["ts"] < 10800.0 + 300.0]
        th = self.thresholds
        now = {
            "rain": rain_1h_mm is not None and rain_1h_mm >= th.rain_mm,
            "frost": inst.t_min_24h is not None and inst.t_min_24h <= th.frost_c,
            "heat": inst.t_max_24h is not None and inst.t_max_24h >= th.heat_c,
            "gust": bool(gust_3h) and max(gust_3h) >= th.gust_ms,
            "storm": bool(strikes) and sum(strikes) > 0,
        }
        return f, now

    def issue(
        self,
        ts: float,
        inst: Instant,
        tz_offset_s: float = 0.0,
        hourly: bool | None = None,
        heuristics: dict[str, float] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Issue forecasts for every active target; open a pending entry for training."""
        if self._last_issue_ts is not None and ts - self._last_issue_ts < 60.0:
            return self._last_issue
        self._last_issue_ts = ts
        self._now_ts = max(self._now_ts, ts)
        self._tz_offset_s = tz_offset_s
        if hourly is None:
            hourly = int(ts // 60) % 60 == 0
        self._close_bin(ts)
        if inst.last_day_clearness is not None:
            self.last_day_clear = [float(inst.last_day_clearness), ts]
        elif self.last_day_clear is not None and ts - self.last_day_clear[1] < 26 * 3600.0:
            inst.last_day_clearness = self.last_day_clear[0]
        feats, now_flags = self._features(ts, inst)
        if inst.mslp is not None:
            self.pressure.append([ts, float(inst.mslp)])
        vec: list[float | None] = [feats[name] for name in POOL]
        for i, x in enumerate(vec):
            if x is not None and math.isfinite(x):
                self.std.update(i, float(x))
            elif x is not None:
                vec[i] = None

        raw: dict[str, float] = {}
        out: dict[str, dict[str, Any]] = {}
        for tid in self.active_target_ids():
            m = self.models[tid]
            missing = next((POOL[i] for i in m.idx if vec[i] is None), None)
            if missing is not None:
                out[tid] = {"p": None, "reason": f"waiting_for:{missing}", "factors": [], "issued_at": ts}
                continue
            raw[tid] = m.predict(self.std, vec)
        # nested rain events: p1 <= p3 <= p6
        prev = 0.0
        for tid in RAIN_CHAIN:
            if tid in raw:
                raw[tid] = max(raw[tid], prev)
                prev = raw[tid]
        heur = heuristics or {}
        entry: dict[str, Any] | None = None
        for tid, p in raw.items():
            m = self.models[tid]
            out[tid] = {
                "p": p,
                "reason": None,
                "factors": _top_factors(m, self.std, vec, inst.local_hour) if m.maturity != "collecting" else [],
                "issued_at": ts,
            }
            if m.spec.hourly_only and not hourly:
                continue
            if entry is None:
                entry = self._new_entry(ts, hourly, vec)
            entry["p"][tid] = round(p, 6)
            entry["c"][tid] = 1 if now_flags.get(m.spec.kind) else 0
            if tid in heur and _finite(heur[tid]):
                entry["h"][tid] = max(0.0, min(1.0, float(heur[tid])))
        if entry is not None:
            self.pending.append(entry)
            if len(self.pending) > PATTERN_PENDING_MAX:
                self.pending = self.pending[-PATTERN_PENDING_MAX:]
        for tid in self.models:
            self._update_maturity(self.models[tid], ts)
        self._last_issue = out
        return out

    # -- scoring windows, maturity ------------------------------------------

    def window_stats(self, tid: str, now_ts: float, weeks: int) -> dict[str, float]:
        """Sums over the most recent ``weeks`` weekly aggregates."""
        wk_now = int(now_ts // WEEK_S)
        n = bm = bu = bp = bh = nh = ev = 0.0
        for r in self.scoring.get(tid, []):
            if wk_now - weeks < r[0] <= wk_now:
                n += r[1]
                bm += r[2]
                bu += r[3]
                bp += r[4]
                bh += r[5]
                nh += r[6]
                ev += r[7]
        return {"n": n, "bm": bm, "bu": bu, "bp": bp, "bh": bh, "nh": nh, "ev": ev}

    @staticmethod
    def _bss(num: float, den: float) -> float | None:
        return None if den <= 1e-12 else 1.0 - num / den

    def _skill_of(self, w: dict[str, float], vs: str = "bu") -> float | None:
        """Brier skill over a window; undefined (None) until the window has seen an event."""
        return self._bss(w["bm"], w[vs]) if w["ev"] > 0 else None

    def days_checked(self, m: ModelState) -> float:
        live = 0.0
        if m.first_scored is not None and m.last_scored is not None:
            live = max(0.0, (m.last_scored - m.first_scored) / 86400.0)
        return live + m.hist_days

    def progress_pct(self, m: ModelState) -> int:
        d = min(1.0, self.days_checked(m) / PATTERN_MIN_DAYS_COLLECTING)
        e = min(1.0, (m.ev_live + m.ev_hist) / PATTERN_MIN_EVENTS_COLLECTING)
        return int(round(100.0 * min(d, e)))

    def _update_maturity(self, m: ModelState, now_ts: float) -> None:
        tid = m.spec.target_id
        if (
            self.days_checked(m) < PATTERN_MIN_DAYS_COLLECTING
            or (m.ev_live + m.ev_hist) < PATTERN_MIN_EVENTS_COLLECTING
        ):
            m.maturity = "collecting"
            return
        w52 = self.window_stats(tid, now_ts, PATTERN_SCORING_WEEKS)
        bss52 = self._bss(w52["bm"], w52["bu"])
        need = PATTERN_SKILLED_MIN_EVENTS[m.spec.kind]
        bar = w52["ev"] >= need and bss52 is not None and bss52 > PATTERN_SKILLED_BSS_MIN
        prev = m.maturity
        if prev in ("skilled", "degraded"):
            w5 = self.window_stats(tid, now_ts, PATTERN_DEGRADED_WEEKS)
            if w5["ev"] >= PATTERN_DEGRADED_MIN_EVENTS:
                bss5 = self._bss(w5["bm"], w5["bu"])
                new = "degraded" if (bss5 is not None and bss5 <= 0.0) else ("skilled" if bar else "learning")
            else:
                new = prev  # not enough recent events to judge: the previous verdict stands
        else:
            new = "skilled" if bar else "learning"
        if new == "skilled":
            m.was_skilled = True
        m.maturity = new

    # -- learning from history (recorder long-term statistics) ----------------

    def targets_needing_replay(self, now_ts: float) -> list[str]:
        """Active targets that have not learned from history yet (or may retry)."""
        done = (self.history_learn or {}).get("targets") or {}
        out = []
        for tid in self.active_target_ids():
            entry = done.get(tid)
            stale = (
                entry is not None
                and entry.get("status") != "ok"
                and (
                    now_ts - float(entry.get("attempted_at", 0.0)) >= PATTERN_HISTORY_RETRY_S
                    or (float(entry["method"]) if _finite(entry.get("method")) else 1.0) < PATTERN_HISTORY_METHOD
                )
            )
            if entry is None or stale:
                out.append(tid)
        return out

    def std_is_cold(self) -> bool:
        """True when the standardizer has (almost) no data, so a replay may build it."""
        return max(self.std.n) < 2 * PATTERN_STD_MIN_N

    def replay(self, hist: HourlyHistory, targets: list[str], update_std: bool) -> dict[str, dict[str, Any]]:
        """Train the given targets on hourly statistics. Meant for a COPY of the engine.

        Replayed samples train the weights, seed the usual rate and count toward
        leaving ``collecting`` (``hist_days`` and ``ev_hist``), but they are never
        scored: skill must be proven on live 15-minute data. Wind direction cannot
        be averaged across 0/360, so ``wind_u`` / ``wind_v`` train masked; storm
        labels have no distance filter; short changes come from hourly means.
        """
        th = self.thresholds
        n = hist.n
        specs = [TARGET_BY_ID[t] for t in targets if t in self.models]
        masked = frozenset(POOL_INDEX[f] for f in REPLAY_MASKED_FEATURES)
        report: dict[str, dict[str, Any]] = {
            s.target_id: {"samples": 0, "events": 0, "first": None, "last": None} for s in specs
        }
        kinds = {s.kind for s in specs}

        # ---- events (independent of the forecast samples)
        eps = {k: {"ts": None, "amt": 0.0, "counted": False} for k in ("rain", "gust", "storm")}
        ids: dict[str, Any] = {"frost": None, "heat": None}
        events = dict.fromkeys(kinds, 0)
        for j in range(n):
            ts_end = hist.start_ts + (j + 1) * 3600.0
            off = hist.tz_offset[j]
            rain, gust, strikes = hist.rain[j], hist.gust[j], hist.strikes[j]
            if "rain" in kinds and rain is not None and rain > 0:
                events["rain"] += _episode_step(
                    eps["rain"], ts_end, rain, PATTERN_EVENT_GAP_H["rain"] * 3600.0, th.rain_mm
                )
            if "gust" in kinds and gust is not None and gust >= th.gust_ms:
                events["gust"] += _episode_step(eps["gust"], ts_end, 1.0, PATTERN_EVENT_GAP_H["gust"] * 3600.0, 1.0)
            if "storm" in kinds and strikes is not None and strikes > 0:
                gap = PATTERN_EVENT_GAP_H["storm"] * 3600.0
                if _episode_step(eps["storm"], ts_end, strikes, gap, PATTERN_STORM_MIN_STRIKES):
                    events["storm"] += 1
            if "frost" in kinds and hist.temp_min[j] is not None and hist.temp_min[j] <= th.frost_c:
                ident = math.floor((ts_end - 1800.0 + off - 43200.0) / 86400.0)
                if ids["frost"] != ident:
                    ids["frost"] = ident
                    events["frost"] += 1
            if "heat" in kinds and hist.temp_max[j] is not None and hist.temp_max[j] >= th.heat_c:
                ident = math.floor((ts_end - 1800.0 + off) / 86400.0)
                if ids["heat"] != ident:
                    ids["heat"] = ident
                    events["heat"] += 1

        def diff(a: list[float | None], i: int, b: int) -> float | None:
            return None if a[i] is None or a[b] is None else a[i] - a[b]

        # ---- samples: one per hour boundary, features from the hours before it
        last_wet: int | None = None
        for k in range(1, n + 1):
            j = k - 1
            if hist.rain[j] is not None and hist.rain[j] >= 0.1:
                last_wet = j
            if k < 25:
                continue
            ts = hist.start_ts + k * 3600.0
            vec: list[float | None] = [None] * N_POOL
            vec[POOL_INDEX["mslp"]] = hist.mslp[j]
            dp3 = diff(hist.mslp, j, j - 3)
            vec[POOL_INDEX["dp_3h"]] = None if dp3 is None else dp3 / 3.0
            vec[POOL_INDEX["dp_24h"]] = diff(hist.mslp, j, j - 24)
            vec[POOL_INDEX["temp"]] = hist.temp[j]
            vec[POOL_INDEX["dpd"]] = hist.dpd[j]
            vec[POOL_INDEX["dpd_1h"]] = diff(hist.dpd, j, j - 1)
            vec[POOL_INDEX["t_1h"]] = diff(hist.temp, j, j - 1)
            vec[POOL_INDEX["t_3h"]] = diff(hist.temp, j, j - 3)
            highs = [v for v in hist.temp_max[j - 23 : j + 1] if v is not None]
            lows = [v for v in hist.temp_min[j - 23 : j + 1] if v is not None]
            vec[POOL_INDEX["t_max_24h"]] = max(highs) if len(highs) >= 20 else None
            vec[POOL_INDEX["wind_speed"]] = hist.wind[j]
            vec[POOL_INDEX["gust_1h"]] = hist.gust[j]
            vec[POOL_INDEX["rain_1h"]] = None if hist.rain[j] is None else math.log1p(max(0.0, hist.rain[j]))
            dry = (j - last_wet) if last_wet is not None else min(PATTERN_DRY_HOURS_CAP, float(j + 1))
            vec[POOL_INDEX["dry_hours"]] = math.log1p(min(PATTERN_DRY_HOURS_CAP, float(dry)))
            vec[POOL_INDEX["cloud_deficit"]] = 0.0
            vec[POOL_INDEX["solar_ok"]] = 0.0
            vec[POOL_INDEX["last_day_clearness"]] = 0.0
            vec[POOL_INDEX["last_day_clearness_ok"]] = 0.0
            vec[POOL_INDEX["night_frac_12h"]] = hist.night_frac[j]
            local_hour = ((ts + hist.tz_offset[j]) / 3600.0) % 24.0
            vec[POOL_INDEX["hour_sin"]] = math.sin(2.0 * math.pi * local_hour / 24.0)
            vec[POOL_INDEX["hour_cos"]] = math.cos(2.0 * math.pi * local_hour / 24.0)
            vec[POOL_INDEX["lightning_1h"]] = None if hist.strikes[j] is None else math.log1p(max(0.0, hist.strikes[j]))
            if update_std:
                for i, x in enumerate(vec):
                    if x is not None and i not in masked:
                        self.std.update(i, float(x), PATTERN_HISTORY_STD_WEIGHT)
            for spec in specs:
                m = self.models[spec.target_id]
                if any(vec[i] is None and i not in masked for i in m.idx):
                    continue
                label = self._replay_label(hist, spec, k)
                if label is None:
                    continue
                if spec.kind == "rain":
                    cond = hist.rain[j] is not None and hist.rain[j] >= th.rain_mm - _EPS
                elif spec.kind == "frost":
                    cond = bool(lows) and min(lows) <= th.frost_c
                elif spec.kind == "heat":
                    cond = bool(highs) and max(highs) >= th.heat_c
                elif spec.kind == "gust":
                    g3 = [v for v in hist.gust[max(0, j - 2) : j + 1] if v is not None]
                    cond = bool(g3) and max(g3) >= th.gust_ms
                else:
                    cond = hist.strikes[j] is not None and hist.strikes[j] > 0
                y = 1.0 if label else 0.0
                n_half = PATTERN_BASE_RATE_HALF_LIFE_DAYS * 24.0
                _rate_update(self.base_rate[spec.target_id], y, n_half)
                _rate_update(self.cond[spec.target_id][1 if cond else 0], y, n_half)
                m.train(self.std, vec, y, ts, masked)
                r = report[spec.target_id]
                r["samples"] += 1
                r["first"] = ts if r["first"] is None else r["first"]
                r["last"] = ts
        for spec in specs:
            m = self.models[spec.target_id]
            r = report[spec.target_id]
            r["events"] = events.get(spec.kind, 0)
            m.ev_hist = r["events"]
            m.hist_days = 0.0 if r["first"] is None else max(0.0, (r["last"] - r["first"]) / 86400.0)
        return report

    def _replay_label(self, hist: HourlyHistory, spec: TargetSpec, k: int) -> bool | None:
        """Label of the window of hours k .. k+H-1 (None = not enough data, never "no")."""
        h = spec.horizon_h
        if k + h > hist.n:
            return None
        th = self.thresholds
        need = PATTERN_COVERAGE_MIN * h
        if spec.kind == "rain":
            ok = [v for v in hist.rain[k : k + h] if v is not None]
            return None if len(ok) < need else sum(ok) >= th.rain_mm - _EPS
        if spec.kind == "frost":
            ok = [v for v in hist.temp_min[k : k + h] if v is not None]
            return None if len(ok) < need else min(ok) <= th.frost_c
        if spec.kind == "heat":
            ok = [v for v in hist.temp_max[k : k + h] if v is not None]
            return None if len(ok) < need else max(ok) >= th.heat_c
        if spec.kind == "gust":
            ok = [v for v in hist.gust[k : k + h] if v is not None]
            return None if len(ok) < need else max(ok) >= th.gust_ms
        ok = [v for v in hist.strikes[k : k + h] if v is not None]
        return None if len(ok) < need else sum(ok) >= PATTERN_STORM_MIN_STRIKES - _EPS

    def adopt_replay(
        self,
        trained: PatternEngine,
        report: dict[str, dict[str, Any]],
        statuses: dict[str, dict[str, Any]],
        update_std: bool,
        now_ts: float,
    ) -> None:
        """Swap replay results into the live engine (called on the event loop).

        Only the learned parameters move over; live counters, scoring and pending
        forecasts of the live engine are kept. ``statuses`` holds the per-target
        status and reason, including targets that could not replay at all.
        """
        for tid, r in report.items():
            live, src = self.models.get(tid), trained.models.get(tid)
            if live is None or src is None or r["samples"] == 0:
                continue
            live.w, live.g2 = list(src.w), list(src.g2)
            live.cp_w, live.cp_g2, live.cp_at = list(src.cp_w), list(src.cp_g2), src.cp_at
            live.n_updates = src.n_updates
            live.ev_hist, live.hist_days = src.ev_hist, src.hist_days
            self.base_rate[tid] = list(trained.base_rate[tid])
            self.cond[tid] = [list(c) for c in trained.cond[tid]]
        if update_std:
            self.std = trained.std
        targets = dict((self.history_learn or {}).get("targets") or {})
        for tid, st in statuses.items():
            if tid in self.models:
                targets[tid] = {**st, "attempted_at": now_ts, "method": PATTERN_HISTORY_METHOD}
        oks = [t for t in targets.values() if t.get("status") == "ok"]
        spans = [r["last"] - r["first"] for r in report.values() if r["first"] is not None]
        failed = [f"{t}: {v.get('reason')}" for t, v in targets.items() if v.get("status") != "ok"]
        self.history_learn = {
            "done_at": now_ts,
            "span_days": round(max(spans) / 86400.0, 1) if spans else 0.0,
            "status": "ok" if not failed else ("partial" if oks else "unavailable"),
            "reason": "; ".join(failed) if failed else None,
            "targets": targets,
        }
        for m in self.models.values():
            self._update_maturity(m, now_ts)

    # -- outputs -------------------------------------------------------------

    def target_status(self, tid: str) -> str:
        """collecting | learning | skilled | degraded | paused (an input is missing now)."""
        m = self.models[tid]
        if m.maturity != "collecting" and self._last_issue.get(tid, {}).get("p") is None and self._last_issue:
            return "paused"
        return m.maturity

    def output(self, tid: str) -> dict[str, Any]:
        m = self.models[tid]
        li = self._last_issue.get(tid) or {}
        status = self.target_status(tid)
        published = status in ("learning", "skilled", "degraded") and li.get("p") is not None
        issued_at = li.get("issued_at")
        w52 = self.window_stats(tid, self._now_ts, PATTERN_SCORING_WEEKS)
        return {
            "target": m.spec.kind,
            "target_id": tid,
            "horizon_h": m.spec.horizon_h,
            "probability": int(round(li["p"] * 100)) if published else None,
            "maturity": status,
            "model_maturity": m.maturity,
            "progress_pct": self.progress_pct(m) if m.maturity == "collecting" else 100,
            "brier_skill": self._round(self._skill_of(w52)),
            "usual_rate": round(self.base_rate[tid][0], 4),
            "issued_at": issued_at,
            "valid_until": None if issued_at is None else issued_at + m.spec.window_s,
            "top_factors": li.get("factors", []) if published else [],
            "samples_trained": m.n_updates,
            "reason": li.get("reason"),
            "events_live": m.ev_live,
            "events_from_history": m.ev_hist,
            "events_required": PATTERN_SKILLED_MIN_EVENTS[m.spec.kind],
        }

    @staticmethod
    def _round(v: float | None, nd: int = 4) -> float | None:
        return None if v is None else round(v, nd)

    def skill(self, tid: str) -> dict[str, Any]:
        w = self.window_stats(tid, self._now_ts, PATTERN_SCORING_WEEKS)
        n = w["n"]
        return {
            "brier": self._round(w["bm"] / n) if n else None,
            "brier_usual": self._round(w["bu"] / n) if n else None,
            "brier_persistence": self._round(w["bp"] / n) if n else None,
            "brier_heuristic": self._round(w["bh"] / w["nh"]) if w["nh"] else None,
            "bss": self._round(self._skill_of(w)),
            "bss_vs_persistence": self._round(self._skill_of(w, "bp")),
            "n_scored": int(n),
            "events": int(w["ev"]),
            "reliability": [
                {
                    "bin": i,
                    "count": int(r[0]),
                    "mean_p": self._round(r[1] / r[0]) if r[0] else None,
                    "freq": self._round(r[2] / r[0]) if r[0] else None,
                }
                for i, r in enumerate(self.reliability[tid])
            ],
        }

    def bss(self, tid: str) -> float | None:
        return self._skill_of(self.window_stats(tid, self._now_ts, PATTERN_SCORING_WEEKS))

    def overall_status(self) -> str:
        """``collecting`` (nothing published yet), ``learning`` or ``active`` (>= 1 skilled)."""
        states = [self.target_status(t) for t in self.models]
        if any(s == "skilled" for s in states):
            return "active"
        if any(s in ("learning", "degraded") for s in states):
            return "learning"
        return "collecting"

    def skilled_count(self) -> int:
        return sum(1 for t in self.models if self.target_status(t) == "skilled")

    def named_weights(self, tid: str) -> dict[str, float]:
        m = self.models[tid]
        out = {"bias": round(m.w[0], 4)}
        for w, i in zip(m.w[1:], m.idx, strict=True):
            out[POOL[i]] = round(w, 4)
        return out

    def internet_inputs(self) -> list[str]:
        return ["storm_3h"] if self.storm_source == "internet" and "storm_3h" in self.models else []

    def data_source(self, tid: str) -> str:
        return "internet" if tid == "storm_3h" and self.storm_source == "internet" else "local"

    # -- (de)serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PATTERN_SCHEMA_VERSION,
            "pool_id": PATTERN_POOL_ID,
            "source_fingerprint": self.source_fingerprint,
            "standardizer": self.std.to_dict(),
            "models": {tid: m.to_dict() for tid, m in self.models.items()},
            "pending": [self._entry_to_dict(e) for e in self.pending],
            "pressure_24h": [list(p) for p in self.pressure],
            "recent_bins": [dict(b) for b in self.bins],
            "scoring": {tid: [list(r) for r in rows] for tid, rows in self.scoring.items()},
            "reliability": {tid: [list(r) for r in rows] for tid, rows in self.reliability.items()},
            "base_rate": {tid: list(v) for tid, v in self.base_rate.items()},
            "cond_freq": {tid: [list(v) for v in vv] for tid, vv in self.cond.items()},
            "episodes": {k: dict(v) for k, v in self._episodes.items()},
            "first_obs_ts": self.first_obs_ts,
            "last_rain_ts": self.last_rain_ts,
            "last_day_clear": list(self.last_day_clear) if self.last_day_clear else None,
            "last_trained_at": self.last_trained_at,
            "history_learn": self.history_learn,
        }

    @staticmethod
    def _entry_to_dict(e: dict[str, Any]) -> dict[str, Any]:
        d = dict(e)
        d["f"] = list(e["f"])
        d["p"] = dict(e["p"])
        d["c"] = dict(e["c"])
        d["h"] = dict(e["h"])
        return d

    @staticmethod
    def _entry_valid(e: Any) -> bool:
        if not isinstance(e, dict):
            return False
        if not (_finite(e.get("ts")) and isinstance(e.get("hr"), bool)):
            return False
        f = e.get("f")
        if not (isinstance(f, list) and len(f) == N_POOL and all(_opt_ok(v) for v in f)):
            return False
        for key in ("p", "c", "h"):
            d = e.get(key)
            if not isinstance(d, dict) or any(k not in TARGET_BY_ID or not _finite(v) for k, v in d.items()):
                return False
        if any(not 0.0 <= v <= 1.0 for v in e["p"].values()):
            return False
        for key in ("rs", "rc", "tc", "gc", "ls", "lc"):
            if not _finite(e.get(key)):
                return False
        return (
            isinstance(e.get("down", False), bool)
            and all(_opt_ok(e.get(k)) for k in ("tn", "tx", "gx"))
            and isinstance(e.get("rbad"), bool)
            and isinstance(e.get("lbad"), bool)
        )

    @classmethod
    def from_dict(
        cls,
        data: Any,
        thresholds: Thresholds | None = None,
        storm_source: str | None = None,
        source_fingerprint: str = "",
        tick_cap_s: float = PATTERN_TICK_CAP_S,
    ) -> tuple[PatternEngine, list[str]]:
        """Validated load. Returns (engine, notes); on any global problem a fresh engine.

        Notes list what was discarded (one warning is enough for the caller).
        """
        eng = cls(thresholds, storm_source, source_fingerprint, tick_cap_s)
        notes: list[str] = []
        if not data:
            return eng, notes
        try:
            if not isinstance(data, dict):
                raise ValueError("payload is not a mapping")
            if data.get("schema_version") != PATTERN_SCHEMA_VERSION:
                raise ValueError(f"schema_version {data.get('schema_version')!r} != {PATTERN_SCHEMA_VERSION}")
            if data.get("pool_id") != PATTERN_POOL_ID:
                raise ValueError(f"pool_id {data.get('pool_id')!r} != {PATTERN_POOL_ID!r}")
            if data.get("source_fingerprint", "") != source_fingerprint:
                raise ValueError("source fingerprint changed (different station or elevation)")
            std = Standardizer.from_dict(data.get("standardizer"))
            if std is None:
                raise ValueError("invalid standardizer")
            loaded = cls._load_parts(eng, data, std, notes)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            notes.append(f"store discarded: {exc}")
            return cls(thresholds, storm_source, source_fingerprint, tick_cap_s), notes
        return loaded, notes

    @classmethod
    def _load_parts(
        cls, eng: PatternEngine, data: dict[str, Any], std: Standardizer, notes: list[str]
    ) -> PatternEngine:
        eng.std = std
        raw_models = data.get("models")
        if not isinstance(raw_models, dict):
            raise ValueError("models missing")
        loaded: set[str] = set()
        for spec in TARGETS:
            tid = spec.target_id
            if tid not in eng.models or tid not in raw_models:
                continue
            m = ModelState.from_dict(spec, eng.models[tid].label_id, raw_models[tid])
            if m is None:
                notes.append(f"{tid}: reset (label/mask changed or entry invalid)")
                continue
            eng.models[tid] = m
            if eng._load_per_target(tid, data, notes):
                loaded.add(tid)
        pending: list[dict[str, Any]] = []
        for e in data.get("pending") or []:
            if not cls._entry_valid(e):
                continue
            d = cls._entry_to_dict(e)
            d.setdefault("down", False)
            for key in ("p", "c", "h"):
                d[key] = {t: v for t, v in d[key].items() if t in loaded}
            if d["p"]:
                pending.append(d)
        eng.pending = pending[-PATTERN_PENDING_MAX:]
        eng._restored = bool(eng.pending)
        for t, v in data.get("pressure_24h", []):
            if _finite(t) and _finite(v):
                eng.pressure.append([float(t), float(v)])
        for b in data.get("recent_bins", []):
            if isinstance(b, dict) and _finite(b.get("ts")) and _finite(b.get("n")):
                eng.bins.append(dict(b))
        for kind, ep in (data.get("episodes") or {}).items():
            if kind in eng._episodes and isinstance(ep, dict):
                eng._episodes[kind].update({k: v for k, v in ep.items() if k in eng._episodes[kind]})
        for key in ("first_obs_ts", "last_rain_ts", "last_trained_at"):
            v = data.get(key)
            setattr(eng, key, float(v) if _finite(v) else None)
        ldc = data.get("last_day_clear")
        eng.last_day_clear = [float(ldc[0]), float(ldc[1])] if _floats_ok(ldc, 2) else None
        eng.history_learn = cls._clean_history(data.get("history_learn"), loaded)
        return eng

    @staticmethod
    def _clean_history(hl: Any, loaded: set[str]) -> dict[str, Any]:
        """Keep only well-formed per-target history entries of models that loaded intact.

        A model that was reset on load (label or mask changed) has to replay again.
        """
        if not isinstance(hl, dict) or not hl:
            return {}
        raw = hl.get("targets")
        clean: dict[str, Any] = {}
        if isinstance(raw, dict):
            for tid, e in raw.items():
                if (
                    tid in loaded
                    and isinstance(e, dict)
                    and isinstance(e.get("status"), str)
                    and _finite(e.get("attempted_at"))
                    and isinstance(e.get("reason"), (str, type(None)))
                ):
                    clean[tid] = dict(e)
        out: dict[str, Any] = {}
        for key in ("done_at", "span_days"):
            if _opt_ok(hl.get(key)):
                out[key] = hl.get(key)
        for key in ("status", "reason"):
            if isinstance(hl.get(key), (str, type(None))):
                out[key] = hl.get(key)
        out["targets"] = clean
        return out

    def _load_per_target(self, tid: str, data: dict[str, Any], notes: list[str]) -> bool:
        """Scoring, reliability and rates of a loaded model; reset the model if they are invalid."""
        rows = (data.get("scoring") or {}).get(tid)
        rel = (data.get("reliability") or {}).get(tid)
        rate = (data.get("base_rate") or {}).get(tid)
        cond = (data.get("cond_freq") or {}).get(tid)
        ok = (
            isinstance(rows, list)
            and len(rows) <= PATTERN_SCORING_WEEKS + 2
            and all(_floats_ok(r, 8) for r in rows)
            and isinstance(rel, list)
            and len(rel) == PATTERN_RELIABILITY_BINS
            and all(_floats_ok(r, 3) for r in rel)
            and _floats_ok(rate, 2)
            and isinstance(cond, list)
            and len(cond) == 2
            and all(_floats_ok(c, 2) for c in cond)
        )
        if not ok:
            notes.append(f"{tid}: reset (scoring state invalid)")
            spec = TARGET_BY_ID[tid]
            self._drop_model(tid)
            self._init_model(spec, self._label_for(spec))
            return False
        self.scoring[tid] = [[float(v) for v in r] for r in rows]
        self.reliability[tid] = [[float(v) for v in r] for r in rel]
        self.base_rate[tid] = [float(rate[0]), float(rate[1])]
        self.cond[tid] = [[float(c[0]), float(c[1])] for c in cond]
        return True


# ---------------------------------------------------------------------------
# Storage helpers (duck-typed store: this module never imports Home Assistant)
# ---------------------------------------------------------------------------


async def async_load_engine(
    store: Any,
    thresholds: Thresholds | None = None,
    storm_source: str | None = None,
    source_fingerprint: str = "",
) -> PatternEngine:
    """Load the engine from a Store-like object; missing or corrupt data starts fresh."""
    try:
        data = await store.async_load()
        eng, notes = PatternEngine.from_dict(data, thresholds, storm_source, source_fingerprint)
        if notes:
            _LOGGER.warning("ws_core pattern forecast: %s - re-learning", "; ".join(notes))
        return eng
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("ws_core pattern forecast store unreadable (%s) - starting fresh", exc)
        return PatternEngine(thresholds, storm_source, source_fingerprint)


async def async_save_engine(store: Any, engine: PatternEngine) -> None:
    """Persist the engine; a failed write is logged, never raised."""
    try:
        await store.async_save(engine.to_dict())
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("ws_core pattern forecast save failed: %s", exc)
