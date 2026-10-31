"""Plain-English wording for quality checks and outcomes. No tkinter, no Foundation logic: wording only."""

from __future__ import annotations

import re
from dataclasses import dataclass

# check name -> (title, what it means, what to do)
CHECKS: dict[str, tuple[str, str, str]] = {
    "format_supported": ("File type not supported", "Q-MAP does not recognise this as a CSV, text, Excel or Parquet file.",
                         "Save the data as CSV or Excel (.xlsx) and try again."),
    "extension_matches_content": ("File name ending does not match the contents",
                                  "The file was read by what it really contains, not by its ending.",
                                  "Rename the file with the correct ending to avoid confusion."),
    "file_readable": ("The file could not be read", "The file is damaged, empty, or its layout does not match the profile.",
                      "Open the file in another program to check it, and check the delimiter/encoding in the profile."),
    "required_columns": ("A required column is missing",
                         "The profile expects columns (date, open, high, low, close) that are not in this file.",
                         "Choose the profile that matches this file, or edit the profile's column names."),
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
    "instrument_declared": ("Exchange or symbol is missing",
                            "Q-MAP needs to know exactly which instrument the file is for and will not guess.",
                            "Type the exchange and symbol in the options, or set them in the profile."),
    "instrument_registered": ("New instrument added", "This exchange and symbol were seen for the first time.",
                              "Nothing to do. Check the spelling if it is not what you expected."),
    "no_duplicate_timestamps": ("Two or more rows have the same date/time",
                                "Each date/time may appear only once. Q-MAP will not choose between duplicates.",
                                "Remove or correct the duplicates in the source."),
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
    "partial_session": ("Some trading days are incomplete", "Some days have fewer bars than usual.",
                        "This is normal for the first and last day of an export."),
    "not_empty": ("The file has no data rows", "There is a header but no data, or the file is empty.", "Check you chose the right file."),
    "profile_version": ("The profile changed without a new version number",
                        "This profile version was used before with different settings.",
                        "Increase profile_version in the profile and save it again."),
    "raw_integrity": ("A stored original file is damaged", "The stored copy no longer matches its checksum.",
                      "Use the restore step with the original file (see the instructions in the message)."),
}

OUTCOMES = {
    "accepted": "Accepted",
    "reused": "Already loaded (nothing new)",
    "rejected": "Rejected - see problems",
    "blocked": "Not retried (already rejected)",
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
