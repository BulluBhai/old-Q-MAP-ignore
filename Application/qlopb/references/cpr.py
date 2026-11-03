"""
CPR (Central Pivot Range: CPR, TC, BC, width) - NOT IMPLEMENTED YET (documented placeholder).

This file only reserves the module interface so the project structure is
ready for later expansion. No calculation exists here and no research uses
it. Do not describe this reference as available.

To add it later: write a function that takes a standard OHLC DataFrame (see
core/data_engine.py) and returns a DataFrame/array of level values, keep it
free of interaction/scoring code, add known-answer tests in
tests/test_references.py, then register it in references/__init__.py.
"""
STATUS = "placeholder"


def compute_cpr(*args, **kwargs):
    raise NotImplementedError(
        "CPR (Central Pivot Range: CPR, TC, BC, width) is not implemented yet. It is a documented placeholder only.")
