"""The canonical market-data structure shared by every downstream Q-MAP module.

One Parquet file per instrument and timeframe, with these columns:

  session_date    date          MANDATORY. Source value for daily+ bars; DERIVED from the timestamp and the
                                declared exchange time zone for intraday bars.
  timestamp_utc   timestamp UTC MANDATORY for intraday, empty for date-only sources. Bar start.
  open/high/low/close float64   MANDATORY.
  volume          float64       OPTIONAL. Empty (null) when absent - never zero-filled.
  src_row         int64         Position (1-based) of the row in the original source, whatever the sort order.
  quality_flags   int64         Bit mask, see FLAG_* below.
  x_<name>        as read       Preserved original columns. NOT quantitative inputs: modules must only use the
                                columns listed in QUANT_COLUMNS.
"""

from __future__ import annotations

CANONICAL_SCHEMA_VERSION = 1

KEY_COLUMNS = ("session_date", "timestamp_utc")
QUANT_COLUMNS = ("open", "high", "low", "close", "volume")
CORE_COLUMNS = ("session_date", "timestamp_utc", "open", "high", "low", "close", "volume", "src_row", "quality_flags")

FLAG_VOLUME_MISSING = 1  # volume is mapped for the dataset but empty on this row
FLAG_DATE_ORDER_UNVERIFIED = 2  # day/month order could not be verified from the data for this row
FLAG_LARGE_MOVE = 4  # close-to-close move above the configured threshold (warning only)
FLAG_MOVED_BY_SORT = 8  # row is not in its original source position after the time-ordering sort
# another row has the same timestamp (or date) with different values (DQ-10). Bit 16 is taken by derived datasets
# (period_may_be_incomplete), so the next free bit is used.
FLAG_CONFLICTING_OBSERVATION = 32

FLAG_DESCRIPTIONS = {
    FLAG_VOLUME_MISSING: "volume_missing",
    FLAG_DATE_ORDER_UNVERIFIED: "date_order_unverified",
    FLAG_LARGE_MOVE: "large_move",
    FLAG_MOVED_BY_SORT: "moved_by_sort",
    FLAG_CONFLICTING_OBSERVATION: "conflicting_observation",
}

# Documented sort rule for the standardised output (the raw file is never modified):
# stable ascending sort on timestamp_utc (intraday) or session_date (daily and longer); rows whose time
# could not be parsed go last; src_row always records the original position.
SORT_RULE = ("stable ascending by timestamp_utc (intraday) or session_date; unparseable times last; src_row keeps "
             "source position (so conflicting observations of one timestamp stay in source order)")
# Repeated timestamps (instruction DQ-10): rows identical in EVERY source column are exact duplicates; only the first
# (lowest src_row) is kept in the standardised copy and the others are recorded. Rows sharing a timestamp with any
# difference are conflicting observations: all are kept, flagged FLAG_CONFLICTING_OBSERVATION, and reported. Q-MAP
# never chooses between them.
DUPLICATE_RULE = ("exact duplicate = same instrument and every source column identical; first occurrence kept, others "
                  "removed from the standardised copy only; conflicting observations (same timestamp, any difference) "
                  "all kept and flagged")
