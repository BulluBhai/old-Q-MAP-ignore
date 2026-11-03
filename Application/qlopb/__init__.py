"""QLOPB (Quant Lens on Price Behaviour): the MA Affinity research engine, migrated into Q-MAP.

Source: repository BulluBhai/QLOPB, commit 6cbadc79fac6fb338eadfa7d260ff5cb459895f5 (branch
claude/youthful-bardeen-11wtok = MA Affinity Scanner V2 on `main` be6d945 plus the three owner-approved safeguards
S-1 infinite prices rejected, S-2 affinity weights validated, S-3 CSV rows with extra values rejected).

Migration rule (Project Owner, 03-Nov-26): the calculation methodology is preserved. The ONLY change to every migrated
file is its import lines (`from config...` -> `from qlopb.config...`); Tests/qlopb/test_qlopb_migration_identity.py proves
this file by file against the original SHA-256 values. Not migrated: QLOPB's own window (gui/main_window.py) and
launcher, because Q-MAP runs MA Affinity from the Analytical Workbench (qmap.analytical_engine.ma_affinity) on
registered datasets. QLOPB's own file loader (core/data_engine.py) is kept with its tests but the Workbench never calls
it: Q-MAP's Database Manager reads and validates source files. QLOPB's own D/W/M/Q aggregation is kept but the Workbench
always runs it with timeframe "as_loaded" (it uses Q-MAP's registered daily/weekly/monthly datasets).

Open methodology items stay open and are printed in every report: Directed IR, affinity weight scheme, incomplete
aggregated boundary bars, uncorrected p-values.
"""

SOURCE_REPOSITORY = "BulluBhai/QLOPB"
SOURCE_COMMIT = "6cbadc79fac6fb338eadfa7d260ff5cb459895f5"
METHOD_NAME = "MA Affinity Scanner V2"
