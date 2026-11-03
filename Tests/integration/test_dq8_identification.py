"""DQ-8 (owner instruction 03-Nov-26): file-name cleaning, editable alias registry, identification precedence.

Approved behaviour: the file name identifies the instrument when the data do not (ON by default for new AND existing
folders); copy/download suffixes are cleaned; the alias registry (a CSV the user edits) maps names to canonical
instruments; no registry match = provisional identity with a warning (never an invented canonical name); explicit
columns in the file take precedence (DQ-2) and a disagreeing name is reported with both identities; NSE is the default
exchange; crypto is the category CRYPTO with the venue unknown. All data are SYNTHETIC.
"""

from __future__ import annotations

import csv
import hashlib

import pytest

from fixtures.builders import HEADER, ohlcv, weekdays, write_delimited
from qmap.catalog import list_datasets
from qmap.core.runs import run_context
from qmap.data_engine import auto_interpret as A
from qmap.data_engine import discovery as D
from qmap.data_engine.instrument_names import (AliasRegistry, add_aliases, clean_filename, ensure_registry_template,
                                               name_key, registry_path, symbol_from_name)
from qmap.storage.db import open_database


def daily(path, n=10, seed=1):
    return write_delimited(path, HEADER, [[d.isoformat()] + r for d, r in zip(weekdays(n), ohlcv(n, seed))])


def write_registry(settings, rows, header=True):
    path = registry_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if header:
            w.writerow(["Canonical name", "Alias 1", "Alias 2", "Alias 3"])
        w.writerows(rows)
    return path


EXAMPLE = [["NIFTY 50", "NIFTY", "NIFTY50", "NIFTY_50"],
           ["RELIANCE", "RELIANCE INDUSTRIES", "RELIANCE", "RELIANCE_EQ"],
           ["BANK NIFTY", "BANKNIFTY", "NIFTY BANK", "BANK_NIFTY"]]


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "market_files"
    f.mkdir()
    return f


def scan(settings, db, src):
    with run_context(settings, db, D.MODULE_CODE, area=D.AREA) as run:
        return D.scan_source(run, src.source_id)


# ---- cleaning ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["RELIANCE.csv", "RELIANCE (1).csv", "RELIANCE (2).csv", "RELIANCE - Copy.csv",
                                  "RELIANCE_Copy.csv", "RELIANCE - Copy (2).csv", "Copy of RELIANCE.csv",
                                  "reliance.CSV", "Reliance_download.csv", "RELIANCE (downloaded).txt",
                                  "RELIANCE_20260225.csv", "RELIANCE_03_Nov_26_002420.xlsx", "RELIANCE__.csv",
                                  "RELIANCE_5min.csv", "RELIANCE, 1D.csv", "RELIANCE.csv.txt"])
def test_copies_downloads_case_separators_and_extensions_clean_to_one_name(name):
    c = clean_filename(name)
    assert c.cleaned == "RELIANCE" and c.original == name


@pytest.mark.parametrize("name, cleaned", [
    ("NIFTY 50.csv", "NIFTY 50"), ("NIFTY_50.csv", "NIFTY 50"),       # a bare number is part of the name
    ("L&T (PARTLY PAID).csv", "L&T (PARTLY PAID)"),                     # brackets that are not a copy number stay
    ("BAJAJ-AUTO (1).csv", "BAJAJ-AUTO"), ("M&M_5min.csv", "M&M"),     # "-" and "&" stay
    ("NSE_BANKNIFTY, 15.csv", "BANKNIFTY"), ("SBI COPYRIGHT.csv", "SBI COPYRIGHT"),  # "copy" only as a suffix word
])
def test_meaningful_parts_of_names_are_kept(name, cleaned):
    prefix = "NSE" if name.startswith("NSE_") else None
    assert clean_filename(name, prefix=prefix).cleaned == cleaned


def test_symbols_are_registry_safe_and_names_compare_loosely():
    assert symbol_from_name("NIFTY 50") == "NIFTY_50" and symbol_from_name("L&T (PARTLY PAID)") == "L&T_PARTLY_PAID"
    assert name_key("nifty_50") == name_key("NIFTY-50") == name_key("Nifty 50") == "NIFTY 50"


# ---- registry ---------------------------------------------------------------------------------------------------
def test_canonical_and_alias_matches_with_case_and_separator_variations(settings):
    reg = AliasRegistry.load(write_registry(settings, EXAMPLE))
    assert not reg.problems and reg.rows == 3
    for name, canonical, status in (("NIFTY.csv", "NIFTY 50", "alias"), ("nifty-50 (1).csv", "NIFTY 50", "canonical"),
                                    ("Nifty_Bank - Copy.csv", "BANK NIFTY", "alias"),
                                    ("RELIANCE_EQ.csv", "RELIANCE", "alias"), ("reliance.csv", "RELIANCE", "canonical")):
        m = reg.match(clean_filename(name))
        assert (m.status, m.canonical) == (status, canonical), name
    assert reg.match(clean_filename("BANKNIFTY.csv")).symbol == "BANK_NIFTY"


def test_registry_collisions_duplicates_and_invalid_rows_are_reported_and_conflicts_ignored(settings):
    rows = EXAMPLE + [["NIFTY NEXT 50", "NIFTY"],          # "NIFTY" now claimed by two instruments
                      ["", "ORPHAN"],                       # no canonical name
                      ["RELIANCE", "RIL", "RIL"],           # duplicate canonical row and duplicate alias
                      ["!!!"]]
    reg = AliasRegistry.load(write_registry(settings, rows))
    kinds = sorted(p.kind for p in reg.problems)
    assert kinds.count("conflict") == 1 and "empty_canonical" in kinds and "invalid" in kinds and "duplicate" in kinds
    m = reg.match(clean_filename("NIFTY.csv"))
    assert m.status == "ambiguous" and m.candidates == ["NIFTY 50", "NIFTY NEXT 50"] and m.symbol == "NIFTY"
    assert reg.match(clean_filename("RIL.csv")).canonical == "RELIANCE"  # the combined row still works
    assert reg.match(clean_filename("NIFTY50.csv")).canonical == "NIFTY 50"  # other aliases unaffected


def test_unidentified_names_are_provisional_with_possible_matches(settings):
    reg = AliasRegistry.load(write_registry(settings, EXAMPLE))
    m = reg.match(clean_filename("RELIANCEPOWER.csv"))
    assert m.status == "provisional" and m.canonical == "RELIANCEPOWER" and "RELIANCE" in m.candidates


def test_the_template_is_created_empty_and_never_overwritten(settings):
    path = ensure_registry_template(settings)
    assert path.read_text(encoding="utf-8").strip() == "Canonical name,Alias 1,Alias 2,Alias 3"
    write_registry(settings, EXAMPLE)
    before = path.read_bytes()
    ensure_registry_template(settings)
    assert path.read_bytes() == before


# ---- in the scan ------------------------------------------------------------------------------------------------
def test_copies_of_one_instrument_get_one_identity_and_are_grouped_in_the_report(settings, db, folder):
    write_registry(settings, EXAMPLE)
    daily(folder / "RELIANCE.csv")
    daily(folder / "RELIANCE (1).csv")             # identical content: loaded once
    daily(folder / "RELIANCE - Copy.csv", seed=2)  # other content, same instrument: a second dataset, reported
    daily(folder / "TATAPOWER (1).csv")
    daily(folder / "TATAPOWER_Copy.csv", seed=5)
    src = D.add_folder_source(settings, db, folder)  # ON by default, no folder exchange: NSE
    res = scan(settings, db, src)
    outcomes = {f[0]: f[3] for f in res.files}
    assert outcomes["RELIANCE (1).csv"] in ("reused", "imported") and outcomes["RELIANCE.csv"] in ("reused", "imported")
    assert {d.instrument for d in list_datasets(db)} == {"NSE:RELIANCE", "NSE:TATAPOWER"}
    rows = list(csv.DictReader(open(res.identification_report_path, encoding="utf-8")))
    (tata,) = [r for r in rows if r["Cleaned name"] == "TATAPOWER"]
    assert tata["Exception"].startswith("Not in the alias registry") and tata["Files"] == "2"
    assert tata["Identity used"] == "TATAPOWER" and not [r for r in rows if r["Cleaned name"] == "RELIANCE"]
    states = {s.relative_path: s for s in D.file_states(db, src.source_id)}
    ident = states["RELIANCE - Copy.csv"].interpretation["decisions"]["identification"]
    assert ident["original_filename"] == "RELIANCE - Copy.csv" and ident["cleaned"]["removed"] == ["- Copy"]
    assert ident["match"]["status"] == "canonical" and ident["exception"] is None
    names = {r[0] for r in db.query("SELECT original_filename FROM ingest_events")}
    assert {"RELIANCE.csv", "RELIANCE - Copy.csv", "TATAPOWER (1).csv"} <= names  # original names preserved


def test_an_alias_gives_the_canonical_instrument(settings, db, folder):
    write_registry(settings, EXAMPLE)
    daily(folder / "NIFTY BANK_5min.csv")
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    assert [d.instrument for d in list_datasets(db)] == ["NSE:BANK_NIFTY"]


def test_a_bulk_registry_update_resolves_provisional_files_on_the_next_scan(settings, db, folder):
    daily(folder / "RELIANCE_EQ.csv")
    daily(folder / "RIL.csv", seed=2)
    src = D.add_folder_source(settings, db, folder)
    first = scan(settings, db, src)
    assert {d.instrument for d in list_datasets(db)} == {"NSE:RELIANCE_EQ", "NSE:RIL"}  # provisional, warned
    groups = D.identification_exceptions(D.file_states(db, src.source_id))
    assert [g["cleaned"] for g in groups] == ["RELIANCE_EQ".replace("_", " "), "RIL"]
    assert first.identification_report_path.is_file()
    with run_context(settings, db, "ALIAS", area="Data_Management") as run:
        record = add_aliases(run, [("RELIANCE", "RELIANCE_EQ"), ("RELIANCE", "RIL")])
    assert record.is_file() and any(p.name.startswith("Instrument_Aliases_before_") for p in record.parent.iterdir())
    scan(settings, db, src)  # the registry changed: the files are identified again, as new datasets
    assert {d.instrument for d in list_datasets(db) if d.status == "active"} >= {"NSE:RELIANCE"}
    assert D.identification_exceptions(D.file_states(db, src.source_id)) == []
    assert {d.instrument for d in list_datasets(db)} == {"NSE:RELIANCE_EQ", "NSE:RIL", "NSE:RELIANCE"}  # nothing deleted


def test_registry_problems_are_listed_in_the_scan_report(settings, db, folder):
    write_registry(settings, EXAMPLE + [["NIFTY NEXT 50", "NIFTY"]])
    daily(folder / "NIFTY.csv")
    src = D.add_folder_source(settings, db, folder)
    res = scan(settings, db, src)
    assert res.registry_problems and any("more than one instrument" in t for t in res.registry_problems)
    rows = list(csv.DictReader(open(res.identification_report_path, encoding="utf-8")))
    assert any(r["Exception"] == "Alias registry problem" for r in rows)
    assert any(r["Exception"].startswith("Ambiguous") and r["Possible matches"] == "NIFTY 50; NIFTY NEXT 50" for r in rows)
    assert [d.instrument for d in list_datasets(db)] == ["NSE:NIFTY"]  # provisional, never a guessed canonical


def test_columns_take_precedence_over_a_registry_match_and_the_disagreement_is_reported(settings, src):
    write_registry(settings, EXAMPLE)
    rows = [[d.isoformat(), "INFY"] + r for d, r in zip(weekdays(10), ohlcv(10))]
    p = write_delimited(src / "RELIANCE.csv", ["date", "symbol", "open", "high", "low", "close", "volume"], rows)
    it = A.interpret_file(p, settings)
    assert it.status == A.READY and it.profile.instrument.symbol_from == "column" and "symbol" not in it.overrides
    assert any("says symbol RELIANCE" in w and "INFY" in w for w in it.warnings)


def test_nse_is_the_default_exchange_and_crypto_is_a_category_with_unknown_venue(settings, src):
    p = daily(src / "TCS.csv")
    assert A.interpret_file(p, settings).overrides["exchange"] == "NSE"
    assert A.interpret_file(p, settings, default_exchange="BSE").overrides["exchange"] == "BSE"
    c = daily(src / "CRYPTO_BTCUSD.csv")
    it = A.interpret_file(c, settings, default_exchange="NSE")
    assert it.overrides["exchange"] == "CRYPTO" and it.decisions["identification"]["venue"] == "unknown"


def test_existing_folders_are_switched_on_by_migration_9_and_new_folders_default_on(settings, tmp_path, monkeypatch):
    import qmap.storage.db as dbmod

    path = tmp_path / "old.sqlite"
    monkeypatch.setattr(dbmod, "MIGRATIONS", dbmod.MIGRATIONS[:8])  # a registry created before this change
    old = open_database(path)
    f = tmp_path / "old_folder"
    f.mkdir()
    old.connection().execute("INSERT INTO data_sources(kind, location, label, symbol_from_filename, created_at, "
                             "updated_at) VALUES ('folder', ?, 'old', 0, 'x', 'x')", (str(f),))
    old.connection().commit()
    old.close()
    monkeypatch.undo()
    db = open_database(path)
    assert db.current_version() == 9
    assert db.one("SELECT symbol_from_filename FROM data_sources")[0] == 1
    g = tmp_path / "new_folder"
    g.mkdir()
    assert D.add_folder_source(settings, db, g).symbol_from_filename
    off = D.update_folder_source(db, 2, symbol_from_filename=False)  # the user can still switch it off
    assert off.symbol_from_filename is False


def test_source_files_are_never_changed(settings, db, folder):
    write_registry(settings, EXAMPLE)
    paths = [daily(folder / n) for n in ("RELIANCE (1).csv", "NIFTY.csv", "CRYPTO_ABC.csv", "odd name.csv")]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    src = D.add_folder_source(settings, db, folder)
    scan(settings, db, src)
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} == before
