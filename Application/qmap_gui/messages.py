"""Plain-English wording for quality checks and outcomes. No tkinter, no Foundation logic: wording only."""

from __future__ import annotations

import re
from dataclasses import dataclass

# check name -> (title, what it means, what to do)
CHECKS: dict[str, tuple[str, str, str]] = {
    "format_supported": ("File type not supported", "Q-MAP does not recognise this as a CSV, text, Excel or Parquet file.",
                         "Save the data as CSV or Excel (.xlsx) and try again."),
    "format_matches_profile": ("The profile is for a different file type",
                               "This file is readable, but the chosen profile was written for another file type "
                               "(for example a CSV profile for an Excel file).",
                               "Choose a profile made for this file type (see 'File type' in the profile details)."),
    "extension_matches_content": ("File name ending does not match the contents",
                                  "The file was read by what it really contains, not by its ending.",
                                  "Rename the file with the correct ending to avoid confusion."),
    "file_readable": ("The file could not be read", "The file is damaged, empty, or its layout does not match the profile.",
                      "Open the file in another program to check it, and check the delimiter/encoding in the profile."),
    "required_columns": ("A required column is missing",
                         "The profile expects columns (date, open, high, low, close) that are not in this file.",
                         "Choose the profile that matches this file, or edit the profile's column names."),
    "first_row_looks_like_header": ("The first row looks like column names",
                                    "The profile says this file has no header row, but row 1 contains words such as "
                                    "'time' and 'open'. Row 1 was treated as data, as the profile says.",
                                    "If the file has a header row, choose a profile with 'First row is a header: Yes'."),
    "row_accounting": ("Rows could not all be accounted for", "An internal safety check failed.",
                       "Please report this; nothing was loaded."),
    "datetime_parseable": ("Some dates or times could not be understood",
                           "The date format in the profile does not match what is in the file.",
                           "Look at the first rows in the preview and correct the date settings in the profile."),
    "date_in_range": ("A date looks wrong", "A date is far in the past or future, which usually means the wrong format, "
                      "century or Unix time unit (seconds vs milliseconds).", "Check the date settings in the profile."),
    "timezone_declared": ("Time zone is missing", "The times have no time zone and Q-MAP will not guess it.",
                          "Set the time zone in the profile."),
    "numeric_types": ("A price or volume is not a number", "A cell contains text where a number is expected.",
                      "Fix those cells in the source file, or check the decimal/thousands settings in the profile."),
    "no_missing_values": ("Some prices are blank or not finite", "Open, high, low or close is empty, NaN or infinite.",
                          "Fix or remove those rows in the source file. Q-MAP will not fill them in."),
    "low_le_open_close": ("Low price is higher than Open or Close", "A bar cannot have its low above its open or close.",
                          "These rows are wrong in the source; correct them there."),
    "high_ge_open_close": ("High price is lower than Open or Close", "A bar cannot have its high below its open or close.",
                           "These rows are wrong in the source; correct them there."),
    "low_le_high": ("Low price is higher than High", "A bar cannot have its low above its high.",
                    "These rows are wrong in the source; correct them there."),
    "prices_positive": ("A price is zero or negative", "Prices must be above zero.", "Correct these rows in the source."),
    "volume_non_negative": ("Volume is negative", "Volume cannot be below zero.", "Correct these rows in the source."),
    "volume_required": ("Volume is required but missing", "The chosen purpose of this data needs volume.",
                        "Use a source with volume, or switch the profile to a price-only purpose."),
    "volume_mapping_resolved": ("The volume columns are unclear",
                                "There are several volume-like columns, or two that disagree, and Q-MAP will not merge them.",
                                "Say in the profile which column is volume (and which others to keep but not use)."),
    "volume_columns_ignored": ("An extra volume-like column was not used",
                               "The file has another column that looks like volume. It is kept for reference only.",
                               "Nothing is wrong. Name it under 'preserved_not_volume' in the profile to hide this note."),
    "constant_volume": ("Volume is the same number on every row", "That looks like a placeholder, not real volume.",
                        "Check the source before relying on volume."),
    "zero_volume_bars": ("Some bars have zero volume", "This is allowed.", "Nothing to do."),
    "instrument_declared": ("Exchange, symbol or timeframe is missing or not valid",
                            "Q-MAP needs to know exactly which instrument and timeframe the file is for, and will not guess.",
                            "Follow the advice under Details. Depending on the profile: type the value in section 3, "
                            "rename the file to fit the profile's file-name pattern, or choose a profile that asks you "
                            "for it."),
    "instrument_registered": ("New instrument added", "This exchange and symbol were seen for the first time.",
                              "Nothing to do. Check the spelling if it is not what you expected."),
    "no_duplicate_timestamps": ("Two or more rows have the same date/time (older records)",
                                "Before 03-Nov-26 a repeated date/time rejected the file.",
                                "Load the file again: identical copies are now removed and differing ones kept."),
    "timeframe_inferred": ("Timeframe measured from the data",
                           "Q-MAP measured the bar interval in sampled parts of the file (no calendar, no file name).",
                           "Nothing to do. If it is wrong, reject the file in Sources."),
    "timeframe_declared_differs": ("The stated timeframe differs from the data",
                                   "The file name, profile or typed value says one interval; the bars are spaced at "
                                   "another. Q-MAP registered the interval the data actually have.",
                                   "Check the source if you expected the stated timeframe."),
    "mixed_intervals": ("Mixed bar intervals",
                        "Different parts of the file have different bar intervals (for example 1-minute and 5-minute). "
                        "The data are kept as one dataset with timeframe MIXED.",
                        "Analyses that need one interval will say they cannot use it. Split the file if you need "
                        "single-interval datasets."),
    "instrument_timeframes_differ": ("Instruments in the file have different bar intervals",
                                     "The file holds several instruments, and measured on its own rows at least one "
                                     "has another bar interval than the file as a whole. Nothing was registered.",
                                     "Split the file into one file per instrument (or per timeframe) and load those."),
    "instrument_timeframe_not_verified": ("An instrument's bar interval could not be checked on its own",
                                          "The file holds several instruments; one has too few rows to measure its own "
                                          "interval, so the file's interval was used for it.",
                                          "Check that instrument's timeframe in the source."),
    "instrument_timeframes_agree": ("Every instrument has the file's bar interval",
                                    "Each instrument in the file was measured on its own rows as well.",
                                    "Nothing to do."),
    "interval_change_detected": ("Part of the file has another bar interval",
                                 "Reading every row found a section (listed with its source rows) whose bars are spaced "
                                 "differently from the rest, for example a 5-minute tail in a 1-minute file.",
                                 "Results across that section mix intervals. Split the file, or keep it in mind."),
    "interval_change_uncertain": ("Part of the file may have another bar interval",
                                  "Reading every row found a section (listed with its source rows) on a regular coarser "
                                  "grid, for example every bar 2 minutes apart in 1-minute data. The timestamps cannot "
                                  "show whether that part has another interval or has bars missing at regular positions.",
                                  "Check the source for that section. The registered timeframe is unchanged."),
    "timeframe_not_measurable": ("Timeframe could not be measured",
                                 "The file is too short to measure the bar interval; the stated timeframe was used.",
                                 "Check the timeframe is right."),
    "period_has_conflicting_observations": ("Some periods are built from conflicting observations",
                                            "The daily data have dates with more than one different value; the usual "
                                            "rules were applied to all of them.",
                                            "Resolve the conflicts in the daily data if these periods matter."),
    "exact_duplicates_removed": ("Identical copies of rows were removed",
                                 "Some rows were identical in every column to an earlier row. The standardised copy "
                                 "keeps one of each; your original file is unchanged.",
                                 "Nothing to do. The removed rows are listed in the problem report."),
    "conflicting_observations": ("Some dates/times have more than one different value",
                                 "Rows with the same date/time disagree (for example two different closes). Q-MAP keeps "
                                 "all of them and does not choose. Analyses still run; calculations that go bar by bar "
                                 "treat each row as a bar.",
                                 "Check the listed rows in the source. Correct the file and load it again, or analyse "
                                 "the data knowing about the conflict."),
    "source_order": ("Rows were not in date order", "Q-MAP stored a sorted copy and kept each row's original position.",
                     "Nothing is lost. Check the source if the order matters to you."),
    "date_order_unverified": ("Day/month order could not be proven",
                              "Every date has a day of 12 or less, so day-first and month-first look the same.",
                              "Please confirm the profile's date format is right for this file."),
    "date_gaps": ("Long gaps between dates", "Some dates are missing for more than the allowed number of days.",
                  "Check the source is complete."),
    "large_moves": ("Very large price moves", "A price moved by more than the allowed percentage between bars.",
                    "Check these rows are real (splits and bad ticks look like this)."),
    "timeframe_spacing": ("Bar spacing does not match the timeframe", "The gaps between bars differ from the profile's timeframe.",
                          "Check the timeframe you chose."),
    "one_bar_per_period": ("More than one bar per day, week or month",
                           "The profile declares a daily, weekly or monthly timeframe, but some days (weeks, months) "
                           "have several bars, which looks like intraday data.",
                           "Check the timeframe you chose (for example 5m instead of 1D). Q-MAP never changes it for you."),
    "partial_session": ("Some days have fewer bars than usual",
                        "Q-MAP found days with fewer bars than the most common number of bars per day in this file. "
                        "This does not show whether a trading session is complete or incomplete: Q-MAP has no trading "
                        "calendar, so a day can also be missing bars without this note appearing (for example when "
                        "every day in the file is short).",
                        "Check the source data and its session coverage (first and last bar time of each day) before "
                        "using these days in session-based analysis."),
    "not_empty": ("The file has no data rows", "There is a header but no data, or the file is empty.", "Check you chose the right file."),
    "profile_version": ("The profile changed without a new version number",
                        "This profile version was used before with different settings.",
                        "Increase profile_version in the profile and save it again."),
    "retry_after_date_limit": ("Retried automatically: the dates are now allowed",
                               "An earlier attempt on this unchanged file was rejected only because some dates were later "
                               "than the allowed limit (today plus the profile's allowed days ahead). Those dates are now "
                               "within the limit, so Q-MAP processed the file again. The earlier rejection stays in the history.",
                               "Nothing to do."),
    "overlaps_existing_dataset": ("Some bars are already in another dataset, with the same values",
                                  "This dataset shares bars with an earlier dataset of the same instrument and timeframe, "
                                  "and every shared bar has identical prices and volume.",
                                  "Nothing to do. Both datasets are kept."),
    "conflicts_with_existing_dataset": ("Some bars differ from another dataset of the same instrument",
                                        "This dataset and an earlier dataset of the same instrument and timeframe have "
                                        "different values for the same bars (for example a revised close). Neither was "
                                        "changed and nothing was merged.",
                                        "Check which source is right, and select that dataset for analysis."),
    "raw_integrity": ("A stored original file is damaged", "The stored copy no longer matches its checksum.",
                      "Use the restore step with the original file (see the instructions in the message)."),
}

OUTCOMES = {
    "accepted": "Accepted",
    "reused": "Already loaded (nothing new)",
    "rejected": "Rejected - see problems",
    "blocked": "Not retried (already rejected)",
    "waiting": "Waiting - its dates are not allowed yet",
    "unsupported": "File type not supported",
    "failed": "Failed",
    "would_be_accepted": "Would be accepted",
    "would_be_rejected": "Would be rejected",
}


@dataclass(frozen=True)
class Finding:
    severity: str  # error | warning | info
    check: str
    title: str
    meaning: str
    todo: str
    detail: str

    def text(self) -> str:
        tag = {"error": "PROBLEM", "warning": "NOTE", "info": "INFO"}[self.severity]
        lines = [f"[{tag}] {self.title}", f"    What it means: {self.meaning}"]
        if self.detail:
            lines.append(f"    Details: {self.detail}")
        lines.append(f"    What to do: {self.todo}")
        return "\n".join(lines)


def explain(name: str) -> tuple[str, str, str]:
    return CHECKS.get(name, (name.replace("_", " ").capitalize(), "", ""))


_CODE_PREFIX = re.compile(r"\[E_[A-Z_]+\]\s*")


def readable(detail: str) -> str:
    """Remove technical error codes such as [E_COLUMN_MISSING] from a message."""
    return _CODE_PREFIX.sub("", detail or "").replace(" Action: ", "  What to do: ")


def findings_from_checks(checks) -> list[Finding]:
    """Failed errors and warnings (and informative info lines) as readable findings. Passed checks are omitted."""
    out = []
    for c in checks:
        if c.passed and not (c.severity == "info" and c.detail):
            continue
        title, meaning, todo = explain(c.name)
        out.append(Finding(c.severity, c.name, title, meaning, todo, readable(c.detail)))
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda f: order[f.severity])
