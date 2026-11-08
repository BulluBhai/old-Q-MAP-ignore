"""Build source-profile TOML text for tests (so the real profile parser is exercised)."""

from __future__ import annotations

import copy

from qmap.data_engine.profiles import SourceProfile, parse_profile

DEFAULTS = {
    "profile_id": "test_profile",
    "profile_version": 1,
    "source_label": "unit-test",
    "file": {"header": True},
    "instrument": {"exchange_from": "fixed", "exchange": "NSE", "symbol_from": "fixed", "symbol": "TEST",
                   "timeframe": "1D"},
    "columns": {"date": {"name": "time"}, "open": {"name": "open"}, "high": {"name": "high"},
                "low": {"name": "low"}, "close": {"name": "close"}},
    "datetime": {"kind": "iso"},
    "volume": {"rule": "use_column", "column": "Volume", "requirement_set": "price_only"},
}


def _val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t") + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_val(x)}" for k, x in v.items()) + " }"
    raise TypeError(v)


def render(d: dict) -> str:
    lines = []
    for k, v in d.items():
        if not isinstance(v, dict) or k in ("_inline",):
            lines.append(f"{k} = {_val(v)}")
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"\n[{k}]")
            for kk, vv in v.items():
                lines.append(f"{kk} = {_val(vv)}")
    return "\n".join(lines) + "\n"


def profile_dict(**overrides) -> dict:
    """Defaults merged with overrides. Section values are merged key by key; None removes a key/section."""
    d = copy.deepcopy(DEFAULTS)
    for key, val in overrides.items():
        if val is None:
            d.pop(key, None)
        elif isinstance(val, dict) and isinstance(d.get(key), dict) and key not in ("columns",):
            d[key].update(val)
            for kk in [k for k, x in d[key].items() if x is None]:
                d[key].pop(kk)
        else:
            d[key] = val
    return d


def profile_text(**overrides) -> str:
    return render(profile_dict(**overrides))


def make_profile(**overrides) -> SourceProfile:
    return parse_profile(profile_text(**overrides))


def do_ingest(run, path, profile=None, **kw):
    """Ingest with a default test profile unless one is given."""
    from qmap.data_engine.ingest import ingest_file

    return ingest_file(run, path, profile or make_profile(), **kw)


def failed_names(result) -> set:
    return {c.name for c in result.checks if c.is_error}


def read_group(settings, db, dataset_id):
    """Cleaned dataset as a dict of python lists."""
    from qmap.storage.parquet_io import read_canonical

    row = db.one("SELECT relative_path FROM datasets WHERE dataset_id = ?", (dataset_id,))
    return read_canonical(settings.data_path(row["relative_path"])).to_pydict()
