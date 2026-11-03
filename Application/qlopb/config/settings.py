"""
QLOPB central settings.

Every common default lives here so that no other file needs "magic numbers".
Nothing in this file calculates anything; it only stores defaults and checks
that the values chosen by the user make sense before a run starts.

Values marked "V2 default" are carried over unchanged from MA Affinity
Scanner V2. They are NOT new methodology decisions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path

# ── Folders ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = PROJECT_ROOT / "logs"

APP_NAME = "QLOPB - Quant Lens on Price Behaviour"
APP_VERSION = "0.1 (initial foundation - awaiting independent review)"

# ── Date / file-name formats (owner preference: dd-mmm-yy everywhere) ─────
DATE_FMT = "%d-%b-%y"
DATETIME_FMT = "%d-%b-%y %H:%M"
DATETIME_SEC_FMT = "%d-%b-%y %H:%M:%S"
FILE_STAMP_FMT = "%d_%b_%y_%H%M%S"

# ── Moving averages ────────────────────────────────────────────────────────
ALL_MA_TYPES = ("SMA", "EMA", "WMA", "HMA", "RMA")
DEFAULT_MA_TYPES = ("SMA",)          # V2 default: SMA only

# ── Data-engine thresholds ─────────────────────────────────────────────────
MIN_ROWS_REQUIRED = 10               # V2 default
MAX_REJECTED_FRACTION = 0.20         # more rejected rows than this -> stop
MAX_OHLC_INCONSISTENT_FRACTION = 0.05  # V2 default (5%): probably wrong columns
OUTLIER_RETURN_PCT = 20.0            # close-to-close move flagged (not removed)
LOW_VOLUME_FLAG = 1                  # volume at or below this is flagged
CALENDAR_GAP_DAYS = 5                # gaps longer than this are listed
CONTENT_SAMPLE_ROWS = 50             # rows inspected for type detection
POSITIONAL_OHLC_MIN_CONSISTENT = 0.99  # share of rows that must fit O/H/L/C order
MAX_EXAMPLES_IN_REPORT = 5           # example dates shown for each flag

# ── Interaction details carried over from V2 (not user options) ────────────
SLOPE_LOOKBACK_BARS = 5
SLOPE_FLAT_THRESHOLD_PCT = 0.02

# ── Wording that must appear on every report ───────────────────────────────
DISCLAIMER_TEXT = (
    "These results describe historical data only. They do not predict or "
    "guarantee future price behaviour or future performance of any reference. "
    "This is a research tool, not a trading signal or recommendation."
)
LIMITATIONS = (
    "A historical rank is a description of the past, not evidence that a "
    "moving average will work in future.",
    "Many candidates (periods and MA types) are tested and the best are shown, "
    "so some will look good by chance. p-values are NOT corrected for this "
    "(multiple comparisons) and must not be read as proof.",
    "Neighbouring MA periods are almost identical, so the Top-N list may show "
    "one finding several times.",
    "Forward windows longer than the primary window overlap each other, so "
    "those statistics are not independent observations.",
    "Success is defined by the sign of the forward return (price higher after "
    "Support, lower after Resistance). It is not compared with the market's "
    "general drift.",
    "Forward Return (Directed IR) methodology is PENDING OWNER REVIEW. The V2 "
    "formula is kept unchanged and is documented in the README.",
    "The official affinity weight scheme is still undecided. The four V2 "
    "weights are kept in their original proportions and normalised.",
    "Out-of-sample samples can be small. Where the OOS sample is below the "
    "minimum, consistency is reported as insufficient evidence.",
)


def weight_problems(weights: dict) -> list:
    """Plain-English problems with a set of affinity weights (empty list = fine).
    Each weight must be finite and not negative; the total must be finite and above 0."""
    out = []
    vals = list(weights.values())
    if not all(math.isfinite(w) for w in vals):
        out.append("Affinity weights must be finite numbers (no NaN or infinity).")
    elif any(w < 0 for w in vals):
        out.append("Affinity weights must not be negative.")
    elif not math.isfinite(sum(vals)):
        out.append("The total of the affinity weights must be finite.")
    elif sum(vals) <= 0:
        out.append("At least one affinity weight must be above 0.")
    return out


class SettingsError(ValueError):
    """Raised when one or more research settings are not usable."""


@dataclass
class MAResearchSettings:
    """All options of the MA Affinity research run (V2 defaults)."""

    ma_types: tuple = DEFAULT_MA_TYPES
    ma_start: int = 10
    ma_end: int = 250
    proximity_pct: float = 3.0
    cooldown_bars: int = 5
    fwd_windows: tuple = (5, 10, 20, 50)   # FIRST entry is the primary window
    min_interactions: int = 10
    is_pct: int = 70
    regime_ma: int = 200
    top_n: int = 5
    # Four affinity weights. Only their relative proportions matter: they are
    # divided by their sum, so they do not have to add up to 100.
    weight_interaction_strength: float = 20
    weight_success_rate: float = 25
    weight_forward_return: float = 25
    weight_stability: float = 15
    # "top_n"  = OOS is evaluated only for the frozen Top-N list (default).
    # "all"    = OOS is also shown for every candidate (V2 behaviour); the
    #            extra OOS rows are informational and must not be used to pick.
    oos_scope: str = "top_n"
    min_oos_outcomes_for_consistency: int = 10
    timeframe: str = "as_loaded"          # as_loaded | D | W | M | Q

    # ── helpers ──
    @property
    def weights(self) -> dict:
        return {
            "interaction_strength": float(self.weight_interaction_strength),
            "success_rate": float(self.weight_success_rate),
            "forward_return": float(self.weight_forward_return),
            "stability": float(self.weight_stability),
        }

    @property
    def primary_window(self) -> int:
        return int(self.fwd_windows[0])

    @property
    def n_candidates(self) -> int:
        return len(self.ma_types) * max(0, self.ma_end - self.ma_start + 1)

    def problems(self) -> list:
        """Return a list of plain-English problems (empty list = settings OK)."""
        out = []

        def is_int(v):
            return isinstance(v, int) and not isinstance(v, bool)

        if not self.ma_types:
            out.append("Select at least one MA type.")
        for t in self.ma_types:
            if t not in ALL_MA_TYPES:
                out.append(f"Unknown MA type '{t}'. Allowed: {', '.join(ALL_MA_TYPES)}.")
        if not is_int(self.ma_start) or self.ma_start < 2:
            out.append("MA Start must be a whole number of 2 or more.")
        if not is_int(self.ma_end) or self.ma_end < 2:
            out.append("MA End must be a whole number of 2 or more.")
        if (is_int(self.ma_start) and is_int(self.ma_end)
                and self.ma_end < self.ma_start):
            out.append("MA End must be greater than or equal to MA Start.")
        try:
            prox = float(self.proximity_pct)
            if not 0 < prox < 50:
                out.append("Proximity % must be above 0 and below 50.")
        except (TypeError, ValueError):
            out.append("Proximity % must be a number.")
        if not is_int(self.cooldown_bars) or self.cooldown_bars < 0:
            out.append("Cooldown must be a whole number of 0 or more.")
        wins = self.fwd_windows
        if (not isinstance(wins, (tuple, list)) or len(wins) == 0
                or not all(is_int(w) and w >= 1 for w in wins)):
            out.append("Forward Windows must be whole numbers of 1 or more, "
                       "for example 5,10,20,50.")
        elif len(set(wins)) != len(wins):
            out.append("Forward Windows must not contain repeated numbers.")
        if not is_int(self.min_interactions) or self.min_interactions < 1:
            out.append("Min Interactions must be a whole number of 1 or more.")
        if not is_int(self.is_pct) or not 1 <= self.is_pct <= 99:
            out.append("IS Split % must be a whole number from 1 to 99.")
        if not is_int(self.regime_ma) or self.regime_ma < 2:
            out.append("Regime MA must be a whole number of 2 or more.")
        if not is_int(self.top_n) or self.top_n < 1:
            out.append("Top-N must be a whole number of 1 or more.")
        out.extend(weight_problems(self.weights))
        if self.oos_scope not in ("top_n", "all"):
            out.append("OOS scope must be 'top_n' or 'all'.")
        if (not is_int(self.min_oos_outcomes_for_consistency)
                or self.min_oos_outcomes_for_consistency < 1):
            out.append("Minimum OOS outcomes must be a whole number of 1 or more.")
        if self.timeframe not in ("as_loaded", "D", "W", "M", "Q"):
            out.append("Timeframe must be as_loaded, D, W, M or Q.")
        return out

    def check(self) -> "MAResearchSettings":
        probs = self.problems()
        if probs:
            raise SettingsError("Please fix these settings:\n- " + "\n- ".join(probs))
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ma_types"] = list(self.ma_types)
        d["fwd_windows"] = list(self.fwd_windows)
        return d
