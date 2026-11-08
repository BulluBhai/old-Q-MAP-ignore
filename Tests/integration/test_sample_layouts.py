"""Synthetic files laid out like the supplied sample layouts, ingested with the shipped example profiles.

No real market data is used: the numbers are generated. Only the LAYOUT (columns, date styles,
volume variations, defects) mirrors the samples the Project Owner described.
"""

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fixtures.builders import HEADER, daily_rows, intraday_utc, ohlcv, weekdays, write_delimited
from fixtures.profiles import failed_names, read_group
from qmap.data_engine.ingest import ingest_file
from qmap.data_engine.profiles import load_profile

PROFILES = Path(__file__).resolve().parents[2] / "Configuration" / "source_profiles"
IST = timezone(timedelta(hours=5, minutes=30))
NET_HEADER = HEADER + ["Net Volume"]


def prof(name):
    return load_profile(PROFILES / f"{name}.toml")


def with_net(rows, signed_exact=False):
    return [r + [(-1) ** i * (r[5] if signed_exact else r[5] // 3)] for i, r in enumerate(rows)]


def intraday_rows(times, seed=2):
    return [[t] + o for t, o in zip(times, ohlcv(len(times), seed))]


def ingest(run, path, name, **kw):
    return ingest_file(run, path, prof(name), **kw)


def test_all_example_profiles_are_valid(settings):
    from qmap.data_engine.profiles import check_profile_against_settings

    files = sorted(PROFILES.glob("*.toml"))
    assert len(files) >= 6
    for f in files:
        p = load_profile(f)
        check_profile_against_settings(p, settings)
        assert p.profile_version >= 1


def test_daily_dd_mm_yy_csv_with_net_volume(src, run, settings, db):
    rows = daily_rows(12)
    rows = [[datetime.fromisoformat(r[0]).strftime("%d-%m-%y")] + r[1:] for r in rows]
    p = write_delimited(src / "NSE_NIFTY_1D1.csv", NET_HEADER, with_net(rows))
    res = ingest(run, p, "example_csv_dd_mm_yy")
    assert res.outcome == "accepted", res.message
    assert [c for c in res.checks if c.name == "date_order_unverified"][0].passed  # a day > 12 proves day-first
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["session_date"][0].isoformat() == "2026-01-05" and g["timestamp_utc"][0] is None
    assert g["x_net_volume"][0] == str(with_net(rows)[0][6]) and g["volume"][0] == rows[0][5]
    assert db.one("SELECT symbol FROM instruments")["symbol"] == "NIFTY"


def test_daily_unix_seconds_csv_at_session_open(src, run, settings, db):
    days = weekdays(8)
    rows = [[int(datetime(d.year, d.month, d.day, 3, 45, tzinfo=timezone.utc).timestamp())] + r
            for d, r in zip(days, ohlcv(8))]
    rows = [r[:1] + r[1:] + [r[5] // 3] for r in rows]
    p = write_delimited(src / "NSE_NIFTY_1D2.csv", NET_HEADER, rows)
    res = ingest(run, p, "example_csv_unix_seconds", timeframe="1D")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["session_date"][0] == days[0] and g["timestamp_utc"][0].hour == 3 and g["timestamp_utc"][0].minute == 45


def test_one_minute_unix_seconds_where_net_volume_is_plus_or_minus_volume(src, run, settings, db):
    times = intraday_utc(375 + 100)
    rows = [[int(t.timestamp())] + o for t, o in zip(times, ohlcv(len(times), 4))]
    rows = with_net(rows, signed_exact=True)
    p = write_delimited(src / "NSE_NIFTY_11.csv", NET_HEADER, rows)
    res = ingest(run, p, "example_csv_unix_seconds", timeframe="1m")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert all(v > 0 for v in g["volume"])  # volume is never replaced by the signed Net Volume
    assert any(int(n) < 0 for n in g["x_net_volume"]) and "net_volume" not in " ".join(["volume"])
    partial = [c for c in res.checks if c.name == "partial_session"][0]
    assert not partial.passed and partial.severity == "warning"  # the second session is incomplete


def test_five_minute_iso_with_offset_and_partial_first_and_last_days(src, run, settings, db):
    times = intraday_utc(75 * 3, step_minutes=5)
    ist = [t.astimezone(IST) for t in times]
    ist = ist[1:-30]  # first day starts at 09:20 and the last day is cut short
    rows = [[t.isoformat()] + o for t, o in zip(ist, ohlcv(len(ist), 6))]
    p = write_delimited(src / "NSE_NIFTY_5.csv", NET_HEADER, with_net(rows))
    res = ingest(run, p, "example_csv_iso_offset", timeframe="5m")
    assert res.outcome == "accepted", res.message
    assert [c for c in res.checks if c.name == "timeframe_spacing"][0].passed
    assert not [c for c in res.checks if c.name == "partial_session"][0].passed
    prov = json.loads(db.one("SELECT datetime_rules_json FROM ingest_attempts")[0])["applied"]
    assert prov["source_utc_offsets"] == ["5:30:00"] and prov["session_date_derived"]


def test_headered_text_file_with_iso_dates_needs_the_instrument_supplied(src, run, settings, db):
    rows = [[r[0]] + r[1:] for r in daily_rows(6)]
    p = write_delimited(src / "661f-dateopenhighlowcloseVolume.txt", ["date", "open", "high", "low", "close", "Volume"], rows)
    res = ingest(run, p, "example_text_headered_iso_date")
    assert res.outcome == "rejected" and "instrument_declared" in failed_names(res)  # never guessed from the odd file name
    res2 = ingest(run, p, "example_text_headered_iso_date", exchange="nse", symbol="nifty")
    assert res2.outcome == "accepted", res2.message


def test_headerless_seven_column_file_with_duplicate_constant_volume_and_no_final_newline(src, run, settings, db):
    rows = [[r[0]] + r[1:5] + [38948210, 38948210] for r in daily_rows(9, start=datetime(2026, 1, 5).date())]
    p = write_delimited(src / "1995-11-03994.21000.91992.69100.txt", None, rows, final_newline=False)
    res = ingest(run, p, "example_text_headerless_seven_columns", exchange="NSE", symbol="TEST")
    assert res.outcome == "accepted", res.message
    chk = {c.name: c for c in res.checks}
    assert chk["constant_volume"].severity == "warning" and not chk["constant_volume"].passed
    assert chk["volume_mapping_resolved"].passed
    g = read_group(settings, db, res.dataset_ids[0])
    assert g["volume"][0] == 38948210.0  # counted once, not doubled
    assert g["x_col5"][0] == "38948210" and g["x_col6"][0] == "38948210"  # both original fields preserved
    assert db.one("SELECT volume_status FROM datasets WHERE layer='cleaned'")["volume_status"] == "mapped"


def parquet_frame(n=375 * 2, seed=8):
    times = [t.astimezone(IST).replace(tzinfo=None) for t in intraday_utc(n)]
    rows = ohlcv(n, seed)
    return times, rows


def write_sample_like_parquet(path, *, defects):
    import pyarrow as pa

    times, rows = parquet_frame()
    cols = {"Date": times, "Open": [r[0] for r in rows], "High": [r[1] for r in rows], "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows], "Volume": [r[4] for r in rows],
            "index": [None] * 375 + [float(i) for i in range(375)]}  # stray column, empty on the first block
    if defects:
        for i in (500, 501, 503):  # Low above Open/Close, like the problem rows in the real sample
            cols["Open"][i], cols["High"][i], cols["Low"][i], cols["Close"][i] = 1425.0, 1777.6, 1777.6, 1774.0
        for k in cols:  # a second pass of two days appended: duplicate timestamps, rows out of order
            cols[k] = cols[k] + cols[k][400:420]
        order = list(range(len(cols["Date"])))
        order[375:395], order[395:415] = order[395:415], order[375:395]
        for k in cols:
            cols[k] = [cols[k][i] for i in order]
    table = pa.table({**cols, "Date": pa.array(cols["Date"], type=pa.timestamp("ns"))})
    import pyarrow.parquet as pq

    pq.write_table(table, path)
    return path


def test_parquet_naive_timestamps_clean_variant_is_accepted_with_the_stray_column_preserved(src, run, settings, db):
    p = write_sample_like_parquet(src / "ONESOURCE_like.parquet", defects=False)
    res = ingest(run, p, "example_parquet_naive_timestamp", exchange="NSE", symbol="ONESRC")
    assert res.outcome == "accepted", res.message
    g = read_group(settings, db, res.dataset_ids[0])
    assert "x_index" in g and g["x_index"][0] is None and g["x_index"][400] == 25.0
    from qmap.storage.parquet_io import read_canonical_metadata

    meta = read_canonical_metadata(settings.data_path(db.one("SELECT relative_path FROM datasets WHERE layer='cleaned'")[0]))
    assert "x_index" not in meta["quant_columns"]  # preserved extra columns are not quantitative inputs
    assert g["timestamp_utc"][0].hour == 3 and g["session_date"][0].isoformat() == "2026-01-05"


def test_parquet_with_duplicates_unsorted_rows_and_bad_ohlc_is_rejected_with_a_full_report(src, run, settings, db):
    p = write_sample_like_parquet(src / "ONESOURCE_bad.parquet", defects=True)
    res = ingest(run, p, "example_parquet_naive_timestamp", exchange="NSE", symbol="ONESRC")
    assert res.outcome == "rejected"
    assert {"no_duplicate_timestamps", "low_le_open_close"} <= failed_names(res)
    with open(res.issues_report, newline="") as fh:
        report = list(csv.DictReader(fh))
    checks = {r["check"] for r in report}
    assert {"no_duplicate_timestamps", "low_le_open_close", "source_order"} <= checks
    dup_rows = {int(r["source_row"]) for r in report if r["check"] == "no_duplicate_timestamps"}
    assert len(dup_rows) == 40  # every row of the 20 repeated timestamps is listed, nothing dropped
    assert {int(r["source_row"]) for r in report if r["check"] == "low_le_open_close"} >= {501, 502, 504}
    assert not db.query("SELECT 1 FROM datasets WHERE layer='cleaned'")
    assert db.one("SELECT file_format FROM datasets WHERE layer='raw'")["file_format"] == "parquet"
    a = db.one("SELECT rows_read, rows_flagged FROM ingest_attempts")
    assert a["rows_read"] == 770 and a["rows_flagged"] >= 43


def test_parquet_naive_timestamps_without_the_zone_declared_cannot_be_read(src, run, db):
    import dataclasses

    p = write_sample_like_parquet(src / "ONESOURCE_like2.parquet", defects=False)
    base = prof("example_parquet_naive_timestamp")
    no_zone = dataclasses.replace(base, profile_id="no_zone", datetime=dataclasses.replace(base.datetime, timezone=None))
    res = ingest_file(run, p, no_zone, exchange="NSE", symbol="X")
    assert res.outcome == "rejected" and "E_TZ_REQUIRED" in res.message
