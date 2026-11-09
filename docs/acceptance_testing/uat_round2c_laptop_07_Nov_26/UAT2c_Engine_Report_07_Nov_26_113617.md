# Q-MAP v0.1: UAT round 2c engine report

07-Nov-26, Claude Code on the owner's laptop. Tester role only. No code was changed, git was not used, nothing was pushed.

## Environment and build

| Item | Value |
|---|---|
| Windows | Microsoft Windows 11 Pro 10.0.26300 |
| Python | 3.12.10 (64-bit), the only Python installed. Python 3.11 is not installed, so the suite was run on 3.12 only |
| Packages | pandas 3.0.5, numpy 2.2.6, scipy 1.17.1, matplotlib 3.10.9, reportlab 4.5.1, pyarrow 24.0.0, openpyxl 3.1.5, tzdata 2026.2, pypdf 6.11.0. pytest 9.2.0 was installed for this test (brief allowed). xlrd is not installed (optional, `.xls` only) |
| Build label (`qmap.core.build.build_label()`) | `qmap 0.1.0rc1 / c2 build a202d43d78ed`. Source fingerprint `a202d43d78edb86db78bada3078e202e887e5a19d931dd6cf502c06176c9bea2`, git_commit null (ZIP download) |
| 2c checklist present | yes: `docs\acceptance_testing\Q-MAP_v0.1_UAT_Round2c_Owner_Screen_Checklist_07_Nov_26_050239.md` |

Evidence: `01_environment_and_build.txt`, `02_pytest_install.txt`.

## Regression suite (local, Python 3.12, Windows laptop; not CI)

Command, run from `Q-MAP_APP`: `python -m pytest -q -p no:cacheprovider --basetemp D:\Q-MAP_V01\UAT2c_Work\pytest_basetemp -rfEs`.
TEMP, TMP and QMAP_GUI_SETTINGS_DIR pointed into `UAT2c_Work`, and bytecode writing was off.

| Result | Laptop | CI on Windows (expected) |
|---|---|---|
| Passed | **1,348** | 1,355 |
| Failed | **0** | 0 |
| Skipped | **8** | 1 |
| Errors | 0 | 0 |
| Duration | 7 min 24 s, exit code 0 | — |
| GUI tests | 214 passed, 0 skipped (they opened real windows on this laptop) | — |

The 7 extra skips are environment-related, not failures (1,348 + 8 = 1,356 = 1,355 + 1):
- 1 × `test_ingest_formats.py:71`: xlrd is not installed (optional `.xls` reader).
- 6 × `test_data_root_containment.py:27`: "symbolic links cannot be created here: [WinError 1314] A required privilege is not held by the client". The user account lacks the Windows symlink privilege (Developer Mode off).
- 1 × `test_placement_and_migration.py:41`: "the hard-link fallback exists only on macOS/Linux". This is the 1 skip CI also has.

1 warning: `PytestRemovedIn10Warning` from the installed `anyio` pytest plugin (third-party, not Q-MAP).

**Unexpected but not a failure:** the output has 14 "Windows fatal exception: access violation" stack dumps from Python's
faulthandler. Every dump is at `multiprocessing\popen_spawn_win32.py` line 75, while child processes are started in 4
concurrency tests:
- `test_concurrent_processes_get_unique_ids`
- `test_many_processes_racing_for_one_destination_exactly_one_wins`
- `test_concurrent_processes_ingesting_the_same_file`
- `test_concurrent_processes_ingesting_identical_content`

All four tests passed and the run continued. These dumps are typical of faulthandler reporting handled Windows exceptions
during process start. Reviewers should still compare with the CI log. Full output: `03_pytest_py312_full_output.txt`.

## Engine checks (on copies)

All state-changing checks used `UAT2c_Work\Q-MAP_DATA_copy`, which was verified identical to the real Q-MAP_DATA when
copied, and `UAT2c_Work\Q-MAP_OUTPUT_copy`. The driver (`UAT2c_Work\scripts\uat2c.py`) calls the same tkinter-free
service functions the screens call and passes them the same arguments `sources.py` passes: decisions, recorded dataset
warnings (`dataset_warnings`) and restore times (`dataset_restore_times`).

| Check | Result | Evidence file | What was seen |
|---|---|---|---|
| Build check | PASS | `01_environment_and_build.txt` | `qmap 0.1.0rc1 / c2 build a202d43d78ed` |
| W2 | PASS | `04_W2_W14-W18_details.txt` | OLAELEC.xlsx: "Detected timeframe: 1 minute", "Status: Accepted by default", "Quality warnings recorded for dataset 11", "WARNING: Some dates/times have more than one different value" (183 timestamps / 366 observations). Also "Rows were not in date order" |
| W14 | PASS | same | RANDOMGAPS: only "Some days have fewer bars than usual" |
| W15 | PASS | same | EVERYOTHER: "Part of the file may have another bar interval", rows 1126-1163, "cannot show whether". Still 5 minutes |
| W16 | PASS | same | GENUINE3M (rows 2251-2375, 3-minute steps) and DAILY0000 (rows 2251-2285, "outside the times of the intraday bars"): "Part of the file has another bar interval" |
| W17 | PASS | same | DAILY0915: "may have another bar interval", "a time the intraday bars also use" |
| W18 | PASS | same | SPARSE: "Some days have fewer bars than usual" and "Long gaps between dates" 2025-04-04 -> 2025-04-14, with no bar-interval warning. The real `Q-MAP_OUTPUT\Data_Management\SCAN_20261106_174124\Scan_Report_*.csv`, read only, lists all six pattern files as Imported. Dataset Summary on NSE:EVERYOTHER: READY, "Validated with warnings ... interval_change_uncertain", completed |
| A4 / V14 | PASS | `05_A4_V14_rescan.txt`, `05b_A4_V14_list_as_screen.txt` | Rescan of the registered Market_Files source: summary "10 unchanged (imported earlier), 1 unchanged (rejected earlier)". The list shows 10 × "Unchanged (imported earlier)", including 5PAISA, VERANDA and UJJIVAN, and AKZOINDIA "Unchanged (rejected earlier)". 19 datasets before and after, none new. See note (a) |
| W5 | PASS (owner may reject) | `06_W5_identity_compare_reject_on_copy.txt` | RELIANCE_EQ.csv → NSE:RELIANCE (alias). Alias row `RELIANCE,RELIANCE EQ`. Datasets 13 (NSE:RELIANCE_EQ) and 18 (NSE:RELIANCE) have the same original file, the same 7,746 bars and 07-Nov-94 to 30-Dec-25, the same processing, settings and warnings, and identical data in all 8 columns. Dataset 13 has the lower number. Reversible reject of 13 **on the copy**: 18 stays Active, and the Workbench offers only `NSE:RELIANCE Daily (ds 18)`. Nothing differs except the intended name, so this does **not** argue against the owner's reject |
| W6 / W7 | PASS | `07_W6_W7_reject_restore_on_copy.txt` | Reject: "Rejected by you", and both leave the Workbench list. Restore: "Available again (restored by you)" and "...; nothing was imported again", and both are offered again. After the next scan the label is "Unchanged (imported earlier)" and the status "Accepted by default" |
| A5 | PASS | `08_A5_and_MAAF_runs.txt` | Dataset Summary NSE:ICICIBANK Daily, 02-Jan-98 to 02-Nov-26: Bars 7166, first close 7.86, last close 1387.4 |
| Build in report | PASS | `09_MAAF_reproducibility_and_build_in_pdf.txt` | MA Affinity, default settings (SMA, 10-250, 5,10,20,50). The PDF's first lines say "Q-MAP build: qmap 0.1.0rc1 / c2 build a202d43d78ed" in both runs |
| MA Affinity reproducibility | PASS | `09_...txt`, `09b_chart_pixel_differences.txt` | Two runs (MAAF_20261107_060021 and _060043) compared. See the list below |
| V1-V3, V6 layout, W8 window response, W11 originals pictures, W12 clean close, all screenshots | SCREEN ONLY | — | The owner must check these by eye (checklist 2c) |

### Reproducibility details: everything that differs between the two runs

- **Byte-identical:** `MA_Affinity_Candidates_*.csv` and `MA_Affinity_Interactions_*.csv` (the full result tables).
- **Workbook:** 2 cell values differ, both Run IDs: `Summary!B2` and `Data_Quality!B2`. The `.xlsx` container bytes also differ because of the file times inside the ZIP.
- **PDF:** 7 pages each. The only text difference is the Run ID in the page-1 header line.
- **Run_Metadata JSON:** `created_utc`, `run_id`, and the output file names, which carry a time stamp.
- **run_manifest.json:** `finished_at`, the output file names, and the charts' and workbook's sha256 and size.
- **run_log.txt:** time stamps and Run IDs only. The Top-5 is identical in both runs (SMA-243, 244, 245, 242, 246) and 43,579 interactions are recorded in both.
- **Charts (5 PNG):** the pixels differ **only in the title line, which contains the Run ID**:
  - In 4 charts, 99-100% of the differing pixels are in the top title band.
  - `chart_score_by_period` is 1 px narrower in run 2, because the shorter Run ID text changes the cropped width, and that shifts every pixel. Looking at both pictures, they are the same apart from the Run ID.
  - The PNG metadata is the same in both runs (Matplotlib 3.10.9).

## Notes requested by the owner

- **(a)** A4/V14 was checked by rescanning the **registered** Market_Files source, which reads the real `D:\Q-MAP_V01\Market_Files` **read only**. All Q-MAP state from that scan went to the copies. The copied registry records its folder sources at the real paths, so `Market_Files_copy` counts as a new source. Its scan was also run as the brief asks, and gave "Already loaded" (and "Rejected earlier (unchanged)" for AKZOINDIA), as expected for a new folder. Hashes show Market_Files unchanged (below).
- **(b)** The first "Available again (restored by you)" result for 5PAISA, VERANDA and UJJIVAN after a scan came from the **test script**, not from Q-MAP. The driver first called `file_row` without the restore times. `sources.py` passes `dataset_restore_times` (lines 289, 298, 328). With them passed, the rows show "Unchanged (imported earlier)" after the scan, as the screen would.
- **(c)** The MA Affinity charts of two runs differ only in the Run ID in their titles (see above).

## Safety proof: before/after hashes

| Folder | Files | Result |
|---|---|---|
| Real `D:\Q-MAP_V01\Q-MAP_DATA` | 38 | **identical** before and after (path, size, SHA-256) |
| Real `D:\Q-MAP_V01\Market_Files` | 11 | **identical** before and after |
| `D:\Q-MAP_V01\Q-MAP_APP` | 344 | no difference between the before and after lists, but see the deviation below |

Lists: `hashes\*_before.csv`, `hashes\*_after.csv`, `hashes\comparison_real_folders.txt`.

**Deviation to report:** the very first command, the build check at 11:27:18, ran Python with `-I`. That mode ignores
`PYTHONDONTWRITEBYTECODE`, so Python wrote 3 bytecode cache files into Q-MAP_APP:
- `Application\qmap\__pycache__\__init__.cpython-312.pyc`
- `Application\qmap\core\__pycache__\__init__.cpython-312.pyc`
- `Application\qmap\core\__pycache__\build.cpython-312.pyc`

The before-hash list was taken after that command, so it includes them. They are compiled caches, not program files, and
no source, test or document file changed. They were left in place (not deleted) for the owner to decide. All later runs set
`sys.dont_write_bytecode` before importing, and no further cache file appeared.

Also outside `D:\Q-MAP_V01`: pytest 9.2.0 was installed into the user's Python 3.12, as the brief allowed. Nothing else
was written outside `D:\Q-MAP_V01`. The owner's originals folder was not opened.

## Nothing failed

No FAIL. The items that need the owner are the SCREEN ONLY checks and the real W5 reject in the owner's own
Q-MAP_DATA (checklist step 13).
