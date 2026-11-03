"""
Registry of reference modules and their honest status.

Only the moving-average module is implemented. Everything else is a
placeholder that raises NotImplementedError if it is called.
"""
from . import (moving_average, pivot_points, cpr, camarilla, bollinger_bands,
               previous_levels, other_references)

REFERENCE_STATUS = {
    "Moving averages (SMA, EMA, WMA, HMA, RMA)": moving_average.STATUS,
    "Pivot Points": pivot_points.STATUS,
    "CPR": cpr.STATUS,
    "Camarilla": camarilla.STATUS,
    "Bollinger Bands": bollinger_bands.STATUS,
    "Previous-period levels": previous_levels.STATUS,
    "Other references": other_references.STATUS,
}
