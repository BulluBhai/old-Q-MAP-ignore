"""Instrument identity is exchange + symbol, always declared, never guessed."""

import pytest

from fixtures.builders import HEADER, daily_rows, write_delimited
from fixtures.profiles import do_ingest, failed_names, make_profile, read_group
from qmap.core.errors import IngestError
from qmap.data_engine.instruments import normalise_exchange, normalise_symbol

ROWS = daily_rows(6)


def instruments(db):
    return [(r["exchange"], r["symbol"]) for r in db.query("SELECT * FROM instruments ORDER BY instrument_id")]


@pytest.mark.parametrize("raw,expected", [(" nse ", "NSE"), ("bse", "BSE"), ("NSE_FO", "NSE_FO")])
def test_exchange_is_normalised(raw, expected):
    assert normalise_exchange(raw) == expected


@pytest.mark.parametrize("raw,expected", [(" nifty ", "NIFTY"), ("m&m", "M&M"), ("BAJAJ-AUTO", "BAJAJ-AUTO"),
                                          ("RELIANCE.NS", "RELIANCE.NS")])
def test_symbol_is_normalised(raw, expected):
    assert normalise_symbol(raw) == expected


@pytest.mark.parametrize("bad", ["", "  ", None, "A/B", "A:B", "A*B", "-A", "CON", "nul", "COM1", "A B", "A\\B", "A.", "x" * 41])
def test_unsafe_or_empty_symbols_are_rejected(bad):
    with pytest.raises(IngestError):
        normalise_symbol(bad)


@pytest.mark.parametrize("bad", ["", None, "N SE", "N/SE", "CON", "x" * 21])
def test_invalid_exchange_rejected(bad):
    with pytest.raises(IngestError):
        normalise_exchange(bad)


def test_same_symbol_on_two_exchanges_gives_two_instruments_and_two_datasets(src, run, settings, db):
    p = write_delimited(src / "a.csv", HEADER, ROWS)
    a = do_ingest(run, p, make_profile(profile_id="nse", instrument={"exchange": "NSE", "symbol": "NIFTY"}))
    b = do_ingest(run, p, make_profile(profile_id="bse", instrument={"exchange": "BSE", "symbol": "NIFTY"}))
    assert a.outcome == b.outcome == "accepted"
    assert instruments(db) == [("NSE", "NIFTY"), ("BSE", "NIFTY")]
    paths = [r["relative_path"] for r in db.query("SELECT relative_path FROM datasets WHERE layer='cleaned'")]
    assert any("/NSE/NIFTY/" in p for p in paths) and any("/BSE/NIFTY/" in p for p in paths)
    assert len(db.query("SELECT 1 FROM datasets WHERE layer='cleaned' AND status='active'")) == 2


def test_first_seen_instrument_is_created_and_the_event_is_recorded(src, run, db):
    res = do_ingest(run, write_delimited(src / "a.csv", HEADER, ROWS))
    assert instruments(db) == [("NSE", "TEST")]
    assert [c for c in res.checks if c.name == "instrument_registered"][0].severity == "info"
    # known instrument: no new row and no second 'created' note
    p2 = write_delimited(src / "b.csv", HEADER, daily_rows(6, seed=5))
    res2 = do_ingest(run, p2, make_profile(profile_version=2))
    assert instruments(db) == [("NSE", "TEST")] and not [c for c in res2.checks if c.name == "instrument_registered"]


def test_instrument_from_filename_pattern(src, run, db):
    p = write_delimited(src / "BSE_SENSEX_1D.csv", HEADER, ROWS)
    prof = make_profile(instrument={"exchange_from": "filename_pattern", "symbol_from": "filename_pattern",
                                    "filename_pattern": r"^(?P<exchange>[A-Za-z]+)_(?P<symbol>[A-Za-z0-9&]+)_",
                                    "exchange": None, "symbol": None})
    assert do_ingest(run, p, prof).outcome == "accepted"
    assert instruments(db) == [("BSE", "SENSEX")]


def test_filename_that_does_not_match_the_pattern_is_an_error(src, run, db):
    p = write_delimited(src / "mystery.csv", HEADER, ROWS)
    prof = make_profile(instrument={"exchange_from": "filename_pattern", "symbol_from": "filename_pattern",
                                    "filename_pattern": r"^(?P<exchange>[A-Z]+)_(?P<symbol>[A-Z]+)_",
                                    "exchange": None, "symbol": None})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected" and "instrument_declared" in failed_names(res) and "E_INSTRUMENT_REQUIRED" in res.message
    assert not instruments(db)


def test_instrument_supplied_at_ingest_time(src, run, db):
    p = write_delimited(src / "anon.csv", HEADER, ROWS)
    prof = make_profile(instrument={"exchange_from": "ingest", "symbol_from": "ingest", "exchange": None, "symbol": None})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected" and "instrument_declared" in failed_names(res)  # never guessed
    res2 = do_ingest(run, p, make_profile(profile_id="anon2", profile_version=1,
                                          instrument={"exchange_from": "ingest", "symbol_from": "ingest",
                                                      "exchange": None, "symbol": None}),
                     exchange="nse", symbol="Nifty")
    assert res2.outcome == "accepted" and instruments(db) == [("NSE", "NIFTY")]


def test_a_file_with_several_instruments_is_split_into_one_dataset_each(src, run, settings, db):
    header = ["Exchange", "Symbol"] + HEADER
    rows = []
    for i, r in enumerate(ROWS):
        rows.append(["NSE", "AAA"] + r)
        rows.append(["BSE", "AAA"] + [r[0]] + [x + 1 for x in r[1:5]] + [r[5]])
        rows.append(["NSE", "bbb"] + [r[0]] + [x + 2 for x in r[1:5]] + [r[5]])
    p = write_delimited(src / "multi.csv", header, rows)
    prof = make_profile(instrument={"exchange_from": "column", "exchange_column": "Exchange", "symbol_from": "column",
                                    "symbol_column": "Symbol", "exchange": None, "symbol": None})
    res = do_ingest(run, p, prof)
    assert res.outcome == "accepted", res.message
    assert len(res.dataset_ids) == 3 and set(instruments(db)) == {("NSE", "AAA"), ("BSE", "AAA"), ("NSE", "BBB")}
    for ds in res.dataset_ids:
        g = read_group(settings, db, ds)
        assert len(g["open"]) == 6 and g["src_row"] == sorted(g["src_row"])
    # every source row ended up in exactly one dataset
    all_rows = sorted(r for ds in res.dataset_ids for r in read_group(settings, db, ds)["src_row"])
    assert all_rows == list(range(1, 19))
    # the identity columns are used, not preserved as quant inputs
    assert "x_exchange" not in read_group(settings, db, res.dataset_ids[0])


def test_blank_symbol_in_a_row_rejects_the_file(src, run, db):
    header = ["Symbol"] + HEADER
    rows = [["AAA"] + r for r in ROWS]
    rows[2][0] = ""
    p = write_delimited(src / "blank_sym.csv", header, rows)
    prof = make_profile(instrument={"symbol_from": "column", "symbol_column": "Symbol", "symbol": None})
    res = do_ingest(run, p, prof)
    assert res.outcome == "rejected" and "instrument_declared" in failed_names(res)


def test_timeframe_from_the_file_name_with_an_explicit_map(src, run, db):
    prof = make_profile(instrument={"timeframe": "filename_pattern", "exchange_from": "filename_pattern",
                                    "symbol_from": "filename_pattern", "exchange": None, "symbol": None,
                                    "filename_pattern": r"^(?P<exchange>[A-Z]+)_(?P<symbol>[A-Z]+)_(?P<timeframe>[0-9A-Z]+)\.",
                                    "timeframe_map": {"1D": "1D", "1W": "1W"}})
    assert do_ingest(run, write_delimited(src / "NSE_NIFTY_1D.csv", HEADER, ROWS), prof).outcome == "accepted"
    assert db.one("SELECT timeframe FROM datasets WHERE layer='cleaned'")["timeframe"] == "1D"
    res = do_ingest(run, write_delimited(src / "NSE_NIFTY_7X.csv", HEADER, daily_rows(6, seed=3)), prof)
    assert res.outcome == "rejected" and "E_TIMEFRAME_REQUIRED" in res.message  # unknown code is never guessed


def test_timeframe_supplied_at_ingest(src, run, db):
    prof = make_profile(instrument={"timeframe": "ingest"})
    p = write_delimited(src / "tf.csv", HEADER, ROWS)
    assert do_ingest(run, p, prof).outcome == "rejected"
    res = do_ingest(run, p, make_profile(profile_id="tf2", instrument={"timeframe": "ingest"}), timeframe="1D")
    assert res.outcome == "accepted"
