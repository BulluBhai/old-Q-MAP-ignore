"""
Research controls: turns the text typed in the window into a validated
MAResearchSettings object. This file has NO tkinter code, so it can be tested
without a screen. The window itself (gui/main_window.py) only collects strings.
"""
from __future__ import annotations

import math

from qlopb.config import settings as cfg
from qlopb.config.settings import MAResearchSettings, SettingsError


def _to_int(text, name, errors):
    try:
        return int(str(text).strip())
    except ValueError:
        errors.append(f"{name} must be a whole number (you typed '{text}').")
        return None


def _to_float(text, name, errors):
    try:
        return float(str(text).strip())
    except ValueError:
        errors.append(f"{name} must be a number (you typed '{text}').")
        return None


def parse_settings(values: dict) -> MAResearchSettings:
    """values: plain strings/lists from the window. Raises SettingsError listing ALL problems."""
    errors = []
    types = tuple(t for t in cfg.ALL_MA_TYPES if t in values.get("ma_types", ()))
    wins_text = str(values.get("fwd_windows", "")).replace(";", ",")
    wins = []
    for part in [p for p in wins_text.split(",") if p.strip()]:
        w = _to_int(part, "Forward Windows", errors)
        if w is not None:
            wins.append(w)
    if not wins and not any("Forward Windows" in e for e in errors):
        errors.append("Forward Windows must list at least one number, e.g. 5,10,20,50.")
    s = MAResearchSettings(
        ma_types=types,
        ma_start=_to_int(values.get("ma_start"), "MA Start", errors),
        ma_end=_to_int(values.get("ma_end"), "MA End", errors),
        proximity_pct=_to_float(values.get("proximity_pct"), "Proximity %", errors),
        cooldown_bars=_to_int(values.get("cooldown_bars"), "Cooldown", errors),
        fwd_windows=tuple(wins) if wins else (),
        min_interactions=_to_int(values.get("min_interactions"), "Min Interactions", errors),
        is_pct=_to_int(values.get("is_pct"), "IS Split %", errors),
        regime_ma=_to_int(values.get("regime_ma"), "Regime MA", errors),
        top_n=_to_int(values.get("top_n"), "Top-N", errors),
        weight_interaction_strength=_to_float(values.get("w_interaction"), "Weight: Interaction Strength", errors),
        weight_success_rate=_to_float(values.get("w_success"), "Weight: Success Rate", errors),
        weight_forward_return=_to_float(values.get("w_forward"), "Weight: Forward Return", errors),
        weight_stability=_to_float(values.get("w_stability"), "Weight: Stability", errors),
        oos_scope=values.get("oos_scope", "top_n"),
        min_oos_outcomes_for_consistency=_to_int(values.get("min_oos"), "Min OOS outcomes", errors),
        timeframe=values.get("timeframe", "as_loaded"))
    if errors:
        raise SettingsError("Please fix these settings:\n- " + "\n- ".join(errors))
    # None values (failed parsing) cannot reach here; now run the range checks
    return s.check()


def candidate_text(values: dict) -> str:
    """Short live text such as 'SMA x 241 periods = 241 candidates'."""
    try:
        types = [t for t in cfg.ALL_MA_TYPES if t in values.get("ma_types", ())]
        a, b = int(values["ma_start"]), int(values["ma_end"])
        per = max(0, b - a + 1)
        return f"{len(types)} type(s) x {per} periods = {len(types) * per} candidates"
    except (KeyError, ValueError, TypeError):
        return ""


def weight_text(values: dict) -> str:
    """Shows the four weights as shares of their sum (what is really used)."""
    try:
        w = [float(values[k]) for k in ("w_interaction", "w_success", "w_forward", "w_stability")]
        tot = sum(w)
        if not all(math.isfinite(x) for x in w) or not math.isfinite(tot) or tot <= 0 or min(w) < 0:
            return "Weights must be finite, not negative, and not all 0."
        return "Used as: " + " / ".join(f"{x / tot * 100:.1f}%" for x in w) + "  (divided by their sum)"
    except (KeyError, ValueError, TypeError):
        return ""
