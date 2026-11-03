"""Instrument identification from file names, with an editable alias registry (owner instruction DQ-8, 03-Nov-26).

Sequence (D5-22): original file name (kept for provenance) -> remove recognised copy/download suffixes, the extension,
a trailing timeframe token and an exchange/market prefix -> normalise case and separators -> match against the alias
registry -> canonical name on a clear match; otherwise the cleaned name is a PROVISIONAL identity (warned, never an
invented canonical name). Every step is recorded, so the decision can be explained and corrected.

Cleaning only removes what is recognisably NOT part of an instrument name:
  copies     "RELIANCE (1)", "RELIANCE (2)", "RELIANCE - Copy", "RELIANCE - Copy (2)", "RELIANCE_Copy", "Copy of RELIANCE"
  downloads  "_download", "(downloaded)", "_export", trailing dates "_20260225", "_2026-02-25", "_03_Nov_26_002420"
  timeframe  ", 15", ", 1D", "_5min", "_15m", "_1h" (a bare number after a space or "_" is KEPT: "NIFTY 50", "NIFTY_50")
Brackets that are not copy numbers ("L&T (PARTLY PAID)"), "&", "-" and digits inside names are kept.

The registry is a CSV under Q-MAP_DATA/Reference_Files/Instrument_Aliases.csv: first column the canonical name, the
other columns its aliases. It is edited with any spreadsheet or text editor; Q-MAP never rewrites it except through an
explicit "add to alias registry" action, which keeps a backup copy and records the change in a run folder.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REGISTRY_FILE = "Instrument_Aliases.csv"
REGISTRY_HEADER = ("Canonical name", "Alias 1", "Alias 2", "Alias 3")
_COPY_PATTERNS = (
    re.compile(r"\s*\(\d{1,3}\)$"),                              # "RELIANCE (1)" Windows/browser copy number
    re.compile(r"[\s_-]*-\s*copy(\s*\(\d{1,3}\))?$", re.I),       # "RELIANCE - Copy", "RELIANCE - Copy (2)"
    re.compile(r"[\s_]+copy(\s*\(\d{1,3}\)|\s*\d{1,3})?$", re.I),  # "RELIANCE_Copy", "RELIANCE copy 2"
    re.compile(r"[\s_-]*\(?(downloaded|download|export|exported)\)?$", re.I),
    re.compile(r"[\s_-]+(19|20)\d{2}-?\d{2}-?\d{2}$"),            # "_20260225", "_2026-02-25"
    re.compile(r"[\s_-]+\d{2}[_-][A-Za-z]{3}[_-]\d{2}([_-]\d{6})?$"),  # "_03_Nov_26" / "_03_Nov_26_002420"
)
_COPY_PREFIX = re.compile(r"^copy\s+of\s+", re.I)
_TIMEFRAME_TOKEN = re.compile(r"(,\s*\d{1,4}(min|[mhHDWM])?|_\d{1,4}(min|[mhHDWM])|\s\d{1,4}(min|[mhHDWM]))$")
_SEPARATORS = re.compile(r"[\s_.\-]+")  # for MATCHING only (name_key)
_SPACES = re.compile(r"[\s_]+")  # for the cleaned NAME: "-", "." and "&" are part of symbols (BAJAJ-AUTO, M&M)
_SYMBOL_UNSAFE = re.compile(r"[^A-Z0-9._&-]+")


def name_key(text: str) -> str:
    """Comparison key: case-insensitive; spaces, underscores, dots and hyphens are all one separator."""
    return _SEPARATORS.sub(" ", str(text).strip().upper()).strip()


def symbol_from_name(text: str) -> str:
    """A registry-safe symbol for a name: spaces become "_" ("NIFTY 50" -> "NIFTY_50"); other characters that symbols
    cannot hold become "_". The display name is kept separately (instruments.name)."""
    s = _SYMBOL_UNSAFE.sub("_", _SPACES.sub("_", str(text).strip().upper())).strip("_.-")
    return re.sub(r"_+", "_", s)


@dataclass
class CleanedName:
    original: str                 # the file name exactly as found (with extension)
    stem: str                     # without the extension
    without_copies: str           # copy/download suffixes removed
    cleaned: str                  # also without a trailing timeframe token, separators normalised (display form)
    removed: list = field(default_factory=list)  # what was removed, in order

    def as_dict(self) -> dict:
        return {"original": self.original, "stem": self.stem, "without_copies": self.without_copies,
                "cleaned": self.cleaned, "removed": self.removed}


def clean_filename(name: str, *, prefix: str | None = None) -> CleanedName:
    """Clean a file name (with or without its folder). `prefix`, if given, is a recognised exchange or market prefix
    ("NSE", "CRYPTO") to remove from the start ("NSE_BANKNIFTY" -> "BANKNIFTY")."""
    original = Path(str(name)).name
    stem = Path(original).stem
    while Path(stem).suffix.lower() in (".csv", ".txt", ".xlsx", ".xls", ".parquet"):  # "x.csv.txt"
        stem = Path(stem).stem
    text, removed = stem.strip(), []
    m = _COPY_PREFIX.match(text)
    if m:
        removed.append(m.group(0).strip())
        text = text[m.end():]
    changed = True
    while changed:
        changed = False
        for pat in _COPY_PATTERNS:
            m = pat.search(text)
            if m and m.start() > 0:
                removed.append(m.group(0).strip())
                text = text[:m.start()].rstrip()
                changed = True
    without_copies = text
    m = _TIMEFRAME_TOKEN.search(text)
    if m and m.start() > 0:
        removed.append(m.group(0).strip(" ,_"))
        text = text[:m.start()].rstrip(" ,_")
    if prefix and name_key(text).startswith(name_key(prefix) + " "):
        removed.append(f"{prefix}_")
        text = re.sub(r"^" + re.escape(prefix) + r"[\s_.\-]+", "", text, flags=re.I)
    cleaned = _SPACES.sub(" ", text).strip().upper()
    return CleanedName(original, stem, without_copies, cleaned, removed)


# ---- registry ------------------------------------------------------------------------------------------------------
@dataclass
class RegistryProblem:
    row: int          # 1-based row in the CSV
    kind: str         # conflict | duplicate | empty_canonical | invalid
    text: str


@dataclass
class Match:
    status: str                    # canonical | alias | ambiguous | provisional
    canonical: str | None          # display name (canonical) or the cleaned name (provisional)
    symbol: str                    # registry-safe symbol
    method: str                    # plain words
    candidates: list = field(default_factory=list)  # for ambiguous / possible matches

    def as_dict(self) -> dict:
        return {"status": self.status, "canonical": self.canonical, "symbol": self.symbol, "method": self.method,
                "candidates": self.candidates}


class AliasRegistry:
    """canonical name + aliases, matched on name_key(). Conflicting aliases are reported and IGNORED (never guessed)."""

    def __init__(self, path: Path | None = None):
        self.path = path
        self.canonicals: dict[str, str] = {}   # key -> canonical display name
        self.aliases: dict[str, str] = {}      # key -> canonical display name (canonicals included)
        self.problems: list[RegistryProblem] = []
        self.conflicts: dict[str, list] = {}  # key -> the canonical names that claim it (never used for matching)
        self.rows = 0

    @classmethod
    def load(cls, path: Path) -> "AliasRegistry":
        reg = cls(path)
        if not path.is_file():
            return reg
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        claims: dict[str, set] = {}
        for n, row in enumerate(rows, start=1):
            cells = [c.strip() for c in row]
            if not any(cells):
                continue
            if n == 1 and cells[0].casefold().startswith("canonical"):
                continue  # header row
            reg.rows += 1
            canonical, aliases = cells[0], [c for c in cells[1:] if c]
            if not canonical:
                reg.problems.append(RegistryProblem(n, "empty_canonical",
                                                    f"Row {n} has aliases but no canonical name; it is ignored."))
                continue
            if not symbol_from_name(canonical):
                reg.problems.append(RegistryProblem(n, "invalid", f"Row {n}: {canonical!r} cannot be an instrument name."))
                continue
            ckey = name_key(canonical)
            if ckey in reg.canonicals and reg.canonicals[ckey] != canonical:
                reg.problems.append(RegistryProblem(n, "duplicate", f"Row {n}: canonical name {canonical!r} also appears "
                                                                     "on an earlier row; the rows are combined."))
            reg.canonicals.setdefault(ckey, canonical)
            seen_here = {ckey}  # an alias equal to the canonical name (e.g. NIFTY_50 for NIFTY 50) is simply redundant
            claims.setdefault(ckey, set()).add(reg.canonicals[ckey])
            alias_keys = set()
            for text in aliases:
                key = name_key(text)
                if key in alias_keys:
                    reg.problems.append(RegistryProblem(n, "duplicate", f"Row {n}: alias {text!r} is listed twice."))
                if key in seen_here:
                    alias_keys.add(key)
                    continue
                seen_here.add(key)
                alias_keys.add(key)
                claims.setdefault(key, set()).add(reg.canonicals[ckey])
        for key, owners in claims.items():
            if len(owners) == 1:
                reg.aliases[key] = next(iter(owners))
            else:
                reg.problems.append(RegistryProblem(0, "conflict", f"{key!r} is an alias of more than one instrument "
                                                                   f"({', '.join(sorted(owners))}); it is not used "
                                                                   "until the registry is corrected."))
                reg.aliases.pop(key, None)
                reg.conflicts[key] = sorted(owners)
        return reg

    def match(self, cleaned: CleanedName) -> Match:
        for text in (cleaned.cleaned, cleaned.without_copies):
            key = name_key(text)
            if key in self.conflicts:
                return Match("ambiguous", cleaned.cleaned, symbol_from_name(cleaned.cleaned),
                             f"'{cleaned.cleaned}' is an alias of more than one instrument in the registry "
                             f"({', '.join(self.conflicts[key])}); the cleaned file name is used provisionally",
                             list(self.conflicts[key]))
            if key in self.aliases:
                canonical = self.aliases[key]
                how = "canonical" if name_key(canonical) == key else "alias"
                return Match(how, canonical, symbol_from_name(canonical),
                             f"'{cleaned.cleaned}' is the {'canonical name' if how == 'canonical' else 'alias'} of "
                             f"{canonical} in the alias registry")
        return Match("provisional", cleaned.cleaned, symbol_from_name(cleaned.cleaned),
                     f"'{cleaned.cleaned}' is not in the alias registry; the cleaned file name is used as a provisional "
                     "identity", self.possible_matches(cleaned.cleaned))

    def possible_matches(self, text: str, limit: int = 3) -> list:
        key = name_key(text).replace(" ", "")
        if len(key) < 3:
            return []
        out = []
        for akey, canonical in self.aliases.items():
            k = akey.replace(" ", "")
            if (key in k or k in key) and canonical not in out:
                out.append(canonical)
        return sorted(out)[:limit]


def registry_path(settings) -> Path:
    return settings.data_root / "Reference_Files" / REGISTRY_FILE


def load_registry(settings) -> AliasRegistry:
    return AliasRegistry.load(registry_path(settings))


def ensure_registry_template(settings) -> Path:
    """Create an EMPTY registry (header only) if none exists. An existing file is never touched."""
    path = registry_path(settings)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(REGISTRY_HEADER)
    return path


def add_aliases(run, entries: list[tuple[str, str]]) -> Path:
    """Bulk registry update: append (canonical, alias) pairs (one row per canonical). Keeps a backup copy of the
    previous file and a JSON record in the run folder (the run is the audit record). Returns the record path."""
    settings = run.settings
    path = ensure_registry_template(settings)
    backup = run.output_path(f"Instrument_Aliases_before_{datetime.now().strftime('%d_%b_%y_%H%M%S')}.csv")
    shutil.copy2(path, backup)
    grouped: dict[str, list] = {}
    for canonical, alias in entries:
        canonical, alias = str(canonical).strip(), str(alias).strip()
        if not canonical:
            raise ValueError("A canonical name is required.")
        grouped.setdefault(canonical, [])
        if alias and name_key(alias) != name_key(canonical) and alias not in grouped[canonical]:
            grouped[canonical].append(alias)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for canonical, aliases in grouped.items():
            w.writerow([canonical, *aliases])
    after = AliasRegistry.load(path)
    record = run.output_path("Alias_Registry_Change.json")
    record.write_text(json.dumps({"registry": str(path), "backup": str(backup), "added": grouped,
                                  "problems_after": [p.__dict__ for p in after.problems]}, indent=2), encoding="utf-8")
    return record
