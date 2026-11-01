"""SQLite schema, as numbered migrations. Never edit an applied migration; add a new one."""

from __future__ import annotations

MIGRATION_1 = """
CREATE TABLE instruments (
  instrument_id INTEGER PRIMARY KEY,
  exchange TEXT NOT NULL, symbol TEXT NOT NULL,
  name TEXT, sector TEXT, active INTEGER NOT NULL DEFAULT 1, valid_from TEXT, valid_to TEXT,
  UNIQUE (exchange, symbol),
  CHECK (length(exchange) > 0 AND exchange = upper(trim(exchange))),
  CHECK (length(symbol)   > 0 AND symbol   = upper(trim(symbol))));

CREATE TABLE modules (module_code TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');

CREATE TABLE runs (
  run_id TEXT PRIMARY KEY, module_code TEXT NOT NULL REFERENCES modules(module_code),
  status TEXT NOT NULL CHECK (status IN ('created','running','completed','failed','cancelled')),
  started_at TEXT, finished_at TEXT, params_json TEXT, code_version TEXT, output_path TEXT,
  parent_run_id TEXT REFERENCES runs(run_id), error_message TEXT);

CREATE TABLE run_outputs (
  run_id TEXT NOT NULL REFERENCES runs(run_id), relative_path TEXT NOT NULL,
  kind TEXT, sha256 TEXT, size_bytes INTEGER, PRIMARY KEY (run_id, relative_path));

CREATE TABLE source_profiles (
  profile_id TEXT NOT NULL, profile_version INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
  content_text TEXT NOT NULL, first_used_at TEXT NOT NULL, PRIMARY KEY (profile_id, profile_version));

CREATE TABLE ingest_events (
  event_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  received_at TEXT NOT NULL,
  original_path TEXT NOT NULL, original_filename TEXT NOT NULL, original_extension TEXT,
  file_size INTEGER, file_mtime TEXT, source_label TEXT, note TEXT,
  sha256 TEXT, detected_format TEXT, intended_relative_path TEXT,
  status TEXT NOT NULL CHECK (status IN ('started','registered_new','reused_existing','unsupported','failed')),
  raw_dataset_id INTEGER REFERENCES datasets(dataset_id),
  detail TEXT,
  CHECK (status NOT IN ('registered_new','reused_existing') OR raw_dataset_id IS NOT NULL));

CREATE TABLE datasets (
  dataset_id INTEGER PRIMARY KEY,
  layer TEXT NOT NULL CHECK (layer IN ('raw','cleaned','timeframe')),
  instrument_id INTEGER REFERENCES instruments(instrument_id),
  timeframe TEXT,
  file_format TEXT CHECK (file_format IN ('parquet','xlsx','xls','delimited_text')),
  relative_path TEXT NOT NULL UNIQUE,
  sha256 TEXT NOT NULL,
  row_count INTEGER, date_from TEXT, date_to TEXT,
  parent_dataset_id INTEGER REFERENCES datasets(dataset_id),
  processing_version TEXT,
  canonical_schema_version INTEGER,
  volume_status TEXT CHECK (volume_status IN ('absent','mapped','derived_sum')),
  requirement_set TEXT,
  created_by_attempt_id INTEGER REFERENCES ingest_attempts(attempt_id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  superseded_by_dataset_id INTEGER REFERENCES datasets(dataset_id),
  created_at TEXT NOT NULL,
  CHECK (layer <> 'raw' OR (file_format IS NOT NULL AND parent_dataset_id IS NULL
        AND processing_version IS NULL AND created_by_attempt_id IS NULL)),
  CHECK (layer = 'raw' OR (parent_dataset_id IS NOT NULL AND instrument_id IS NOT NULL
        AND timeframe IS NOT NULL AND created_by_attempt_id IS NOT NULL
        AND volume_status IS NOT NULL AND requirement_set IS NOT NULL
        AND processing_version IS NOT NULL AND length(trim(processing_version)) > 0)),
  CHECK (layer <> 'cleaned' OR processing_version GLOB '?*@?*+?*'));

CREATE UNIQUE INDEX ux_datasets_raw_sha256 ON datasets(sha256) WHERE layer = 'raw';
CREATE UNIQUE INDEX ux_datasets_derivation ON datasets(layer, parent_dataset_id, processing_version, instrument_id, timeframe) WHERE layer <> 'raw';
CREATE UNIQUE INDEX ux_datasets_one_active ON datasets(layer, parent_dataset_id, instrument_id, timeframe) WHERE layer <> 'raw' AND status = 'active';
CREATE INDEX ix_datasets_sha256 ON datasets(sha256);

CREATE TABLE ingest_attempts (
  attempt_id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES ingest_events(event_id),
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  raw_dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id),
  outcome TEXT NOT NULL CHECK (outcome IN ('accepted','rejected','reused')),
  profile_id TEXT NOT NULL, profile_version INTEGER NOT NULL,
  processing_version TEXT NOT NULL CHECK (length(trim(processing_version)) > 0),
  detected_format TEXT NOT NULL, extension_matches INTEGER NOT NULL, reader TEXT NOT NULL, reader_version TEXT,
  source_columns_json TEXT, column_mapping_json TEXT, datetime_rules_json TEXT, volume_rule_json TEXT,
  transformations_json TEXT, field_provenance_json TEXT,
  rows_read INTEGER, rows_accepted INTEGER, rows_flagged INTEGER, issues_report_path TEXT,
  revalidation_of_attempt_id INTEGER REFERENCES ingest_attempts(attempt_id),
  reused_of_attempt_id INTEGER REFERENCES ingest_attempts(attempt_id),
  force_reason TEXT,
  ingest_request_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (profile_id, profile_version) REFERENCES source_profiles(profile_id, profile_version),
  CHECK (outcome <> 'reused' OR reused_of_attempt_id IS NOT NULL),
  CHECK (force_reason IS NULL OR length(trim(force_reason)) > 0));

CREATE TABLE quality_checks (
  check_id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
  attempt_id INTEGER REFERENCES ingest_attempts(attempt_id), dataset_id INTEGER REFERENCES datasets(dataset_id),
  check_name TEXT NOT NULL, severity TEXT NOT NULL CHECK (severity IN ('error','warning','info')),
  passed INTEGER NOT NULL, rows_failed INTEGER, detail TEXT, checked_at TEXT NOT NULL,
  CHECK (attempt_id IS NOT NULL OR dataset_id IS NOT NULL));

CREATE TABLE run_inputs (
  run_id TEXT NOT NULL REFERENCES runs(run_id), dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id),
  PRIMARY KEY (run_id, dataset_id));

CREATE TABLE research_records (
  research_id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
  module_code TEXT NOT NULL REFERENCES modules(module_code), title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('Hypothesis','Research complete','OOS validated','Strategy validated','Superseded')),
  superseded_by INTEGER REFERENCES research_records(research_id), created_at TEXT NOT NULL);

CREATE TRIGGER trg_attempts_no_update BEFORE UPDATE ON ingest_attempts BEGIN SELECT RAISE(ABORT,'ingest_attempts is append-only'); END;
CREATE TRIGGER trg_attempts_no_delete BEFORE DELETE ON ingest_attempts BEGIN SELECT RAISE(ABORT,'ingest_attempts is append-only'); END;
CREATE TRIGGER trg_checks_no_update   BEFORE UPDATE ON quality_checks  BEGIN SELECT RAISE(ABORT,'quality_checks is append-only'); END;
CREATE TRIGGER trg_checks_no_delete   BEFORE DELETE ON quality_checks  BEGIN SELECT RAISE(ABORT,'quality_checks is append-only'); END;
CREATE TRIGGER trg_events_no_delete   BEFORE DELETE ON ingest_events   BEGIN SELECT RAISE(ABORT,'ingest_events is never deleted'); END;
CREATE TRIGGER trg_events_identity BEFORE UPDATE ON ingest_events
WHEN NEW.run_id IS NOT OLD.run_id OR NEW.received_at IS NOT OLD.received_at OR NEW.original_path IS NOT OLD.original_path
  OR NEW.original_filename IS NOT OLD.original_filename OR NEW.sha256 IS NOT OLD.sha256
BEGIN SELECT RAISE(ABORT,'ingest_events identity columns are immutable'); END;
CREATE TRIGGER trg_datasets_no_delete BEFORE DELETE ON datasets BEGIN SELECT RAISE(ABORT,'datasets are never deleted'); END;
CREATE TRIGGER trg_datasets_identity BEFORE UPDATE ON datasets
WHEN NEW.layer IS NOT OLD.layer OR NEW.sha256 IS NOT OLD.sha256 OR NEW.relative_path IS NOT OLD.relative_path
  OR NEW.parent_dataset_id IS NOT OLD.parent_dataset_id OR NEW.processing_version IS NOT OLD.processing_version
  OR NEW.instrument_id IS NOT OLD.instrument_id OR NEW.timeframe IS NOT OLD.timeframe
  OR NEW.created_by_attempt_id IS NOT OLD.created_by_attempt_id
  OR (OLD.superseded_by_dataset_id IS NOT NULL AND NEW.superseded_by_dataset_id IS NOT OLD.superseded_by_dataset_id)
  OR (OLD.status = 'superseded' AND NEW.status <> 'superseded')
BEGIN SELECT RAISE(ABORT,'dataset identity columns are immutable'); END;
"""

# Added by the independent PR #1 review (31-Oct-26). Migration 1 is left exactly as it was.
MIGRATION_2 = """
ALTER TABLE ingest_attempts ADD COLUMN validation_settings_json TEXT;

CREATE TRIGGER trg_events_final BEFORE UPDATE ON ingest_events
WHEN OLD.status <> 'started' AND (NEW.status IS NOT OLD.status OR NEW.raw_dataset_id IS NOT OLD.raw_dataset_id)
BEGIN SELECT RAISE(ABORT,'a finished ingest_events receipt cannot change its outcome'); END;
CREATE TRIGGER trg_profiles_no_update BEFORE UPDATE ON source_profiles BEGIN SELECT RAISE(ABORT,'source_profiles snapshots are immutable'); END;
CREATE TRIGGER trg_profiles_no_delete BEFORE DELETE ON source_profiles BEGIN SELECT RAISE(ABORT,'source_profiles snapshots are immutable'); END;
CREATE TRIGGER trg_runs_no_delete BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT,'runs are never deleted'); END;
CREATE TRIGGER trg_instruments_no_delete BEFORE DELETE ON instruments BEGIN SELECT RAISE(ABORT,'instruments are never deleted'); END;
CREATE TRIGGER trg_instruments_identity BEFORE UPDATE ON instruments
WHEN NEW.exchange IS NOT OLD.exchange OR NEW.symbol IS NOT OLD.symbol
BEGIN SELECT RAISE(ABORT,'instrument identity (exchange, symbol) is immutable'); END;
"""

# Validation settings become part of the processing identity (Project Owner decision, 31-Oct-26).
# The processing_version text is unchanged; the fingerprint is a separate identity component.
MIGRATION_3 = """
ALTER TABLE ingest_attempts ADD COLUMN config_fingerprint TEXT;
ALTER TABLE datasets ADD COLUMN config_fingerprint TEXT;

DROP INDEX ux_datasets_derivation;
CREATE UNIQUE INDEX ux_datasets_derivation
  ON datasets(layer, parent_dataset_id, processing_version, instrument_id, timeframe, config_fingerprint) WHERE layer <> 'raw';

DROP TRIGGER trg_datasets_identity;
CREATE TRIGGER trg_datasets_identity BEFORE UPDATE ON datasets
WHEN NEW.layer IS NOT OLD.layer OR NEW.sha256 IS NOT OLD.sha256 OR NEW.relative_path IS NOT OLD.relative_path
  OR NEW.parent_dataset_id IS NOT OLD.parent_dataset_id OR NEW.processing_version IS NOT OLD.processing_version
  OR NEW.instrument_id IS NOT OLD.instrument_id OR NEW.timeframe IS NOT OLD.timeframe
  OR NEW.created_by_attempt_id IS NOT OLD.created_by_attempt_id
  OR NEW.config_fingerprint IS NOT OLD.config_fingerprint
  OR (OLD.superseded_by_dataset_id IS NOT NULL AND NEW.superseded_by_dataset_id IS NOT OLD.superseded_by_dataset_id)
  OR (OLD.status = 'superseded' AND NEW.status <> 'superseded')
BEGIN SELECT RAISE(ABORT,'dataset identity columns are immutable'); END;
"""

# Every NEW cleaned dataset and attempt must carry its fingerprint: a NULL would escape the derivation-uniqueness
# index (SQLite treats NULLs as distinct). Rows written before migration 3 keep their NULL (never rewritten).
MIGRATION_4 = """
CREATE TRIGGER trg_datasets_fingerprint_required BEFORE INSERT ON datasets
WHEN NEW.layer <> 'raw' AND (NEW.config_fingerprint IS NULL OR length(trim(NEW.config_fingerprint)) = 0)
BEGIN SELECT RAISE(ABORT,'a derived dataset must record its configuration fingerprint'); END;
CREATE TRIGGER trg_attempts_fingerprint_required BEFORE INSERT ON ingest_attempts
WHEN NEW.config_fingerprint IS NULL OR length(trim(NEW.config_fingerprint)) = 0
BEGIN SELECT RAISE(ABORT,'an ingest attempt must record its configuration fingerprint'); END;
"""

# Database Manager / Analytical Workbench separation (01-Nov-26): Permanent/Temporary storage classification,
# user-controlled deletion of a TEMPORARY dataset's file (its registry record and provenance are kept for ever),
# an audit trail of every storage action, and the provenance of derived timeframes.
MIGRATION_5 = """
ALTER TABLE datasets ADD COLUMN storage_class TEXT NOT NULL DEFAULT 'permanent'
  CHECK (storage_class IN ('permanent','temporary'));
ALTER TABLE datasets ADD COLUMN file_deleted_at TEXT;

CREATE TABLE storage_actions (
  action_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id),
  action TEXT NOT NULL CHECK (action IN ('move','delete_file')),
  from_class TEXT NOT NULL CHECK (from_class IN ('permanent','temporary')),
  to_class TEXT CHECK (to_class IS NULL OR to_class IN ('permanent','temporary')),
  from_path TEXT NOT NULL,
  to_path TEXT,
  reason TEXT,
  status TEXT NOT NULL CHECK (status IN ('started','completed','failed')),
  started_at TEXT NOT NULL, finished_at TEXT, detail TEXT,
  CHECK (action <> 'move' OR (to_class IS NOT NULL AND to_path IS NOT NULL AND to_class <> from_class)));
CREATE INDEX ix_storage_actions_open ON storage_actions(status) WHERE status = 'started';

CREATE TRIGGER trg_storage_actions_no_delete BEFORE DELETE ON storage_actions
BEGIN SELECT RAISE(ABORT,'storage_actions is append-only'); END;
CREATE TRIGGER trg_storage_actions_final BEFORE UPDATE ON storage_actions
WHEN OLD.status <> 'started' OR NEW.action_id IS NOT OLD.action_id OR NEW.run_id IS NOT OLD.run_id
  OR NEW.dataset_id IS NOT OLD.dataset_id OR NEW.action IS NOT OLD.action OR NEW.from_class IS NOT OLD.from_class
  OR NEW.to_class IS NOT OLD.to_class OR NEW.from_path IS NOT OLD.from_path OR NEW.to_path IS NOT OLD.to_path
  OR NEW.reason IS NOT OLD.reason OR NEW.started_at IS NOT OLD.started_at
BEGIN SELECT RAISE(ABORT,'a storage action can only be finished once, and its identity cannot change'); END;

CREATE TABLE dataset_derivations (
  dataset_id INTEGER PRIMARY KEY REFERENCES datasets(dataset_id),
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  method TEXT NOT NULL,
  method_version INTEGER NOT NULL,
  source_dataset_id INTEGER NOT NULL REFERENCES datasets(dataset_id),
  source_sha256 TEXT NOT NULL,
  parameters_json TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE TRIGGER trg_derivations_no_update BEFORE UPDATE ON dataset_derivations
BEGIN SELECT RAISE(ABORT,'dataset_derivations is append-only'); END;
CREATE TRIGGER trg_derivations_no_delete BEFORE DELETE ON dataset_derivations
BEGIN SELECT RAISE(ABORT,'dataset_derivations is append-only'); END;

-- The registered path may now change, but ONLY together with a change of storage class (a recorded move).
DROP TRIGGER trg_datasets_identity;
CREATE TRIGGER trg_datasets_identity BEFORE UPDATE ON datasets
WHEN NEW.layer IS NOT OLD.layer OR NEW.sha256 IS NOT OLD.sha256
  OR (NEW.relative_path IS NOT OLD.relative_path AND NEW.storage_class IS OLD.storage_class)
  OR NEW.parent_dataset_id IS NOT OLD.parent_dataset_id OR NEW.processing_version IS NOT OLD.processing_version
  OR NEW.instrument_id IS NOT OLD.instrument_id OR NEW.timeframe IS NOT OLD.timeframe
  OR NEW.created_by_attempt_id IS NOT OLD.created_by_attempt_id
  OR NEW.config_fingerprint IS NOT OLD.config_fingerprint
  OR (OLD.superseded_by_dataset_id IS NOT NULL AND NEW.superseded_by_dataset_id IS NOT OLD.superseded_by_dataset_id)
  OR (OLD.status = 'superseded' AND NEW.status <> 'superseded')
BEGIN SELECT RAISE(ABORT,'dataset identity columns are immutable'); END;

-- Raw (original source) files are never re-classified or deleted; only a TEMPORARY dataset's file may be deleted;
-- once deleted, the record is final.
CREATE TRIGGER trg_datasets_storage BEFORE UPDATE ON datasets
WHEN (NEW.storage_class IS NOT OLD.storage_class AND (OLD.layer = 'raw' OR OLD.file_deleted_at IS NOT NULL))
  OR (OLD.file_deleted_at IS NOT NULL AND (NEW.file_deleted_at IS NOT OLD.file_deleted_at
                                           OR NEW.relative_path IS NOT OLD.relative_path))
  OR (OLD.file_deleted_at IS NULL AND NEW.file_deleted_at IS NOT NULL
      AND (OLD.layer = 'raw' OR OLD.storage_class <> 'temporary' OR NEW.storage_class <> 'temporary'))
BEGIN SELECT RAISE(ABORT,'this storage change is not allowed (raw files and deleted datasets are final; only temporary datasets can be deleted)'); END;
CREATE TRIGGER trg_datasets_storage_insert BEFORE INSERT ON datasets
WHEN NEW.file_deleted_at IS NOT NULL OR (NEW.layer = 'raw' AND NEW.storage_class <> 'permanent')
BEGIN SELECT RAISE(ABORT,'a new dataset must be stored, and a raw file is always permanent'); END;
"""

# (version, description, sql)
MIGRATIONS = [
    (1, "Stage 2 foundation: instruments, runs, registry, ingest provenance, quality checks", MIGRATION_1),
    (2, "Review fixes: validation settings provenance; final receipts, profile snapshots, runs and instruments protected",
     MIGRATION_2),
    (3, "Validation-settings fingerprint is part of the processing identity (reuse and derivation uniqueness)",
     MIGRATION_3),
    (4, "New derived datasets and attempts must record their configuration fingerprint", MIGRATION_4),
    (5, "Permanent/Temporary storage classification, storage-action audit trail and derived-timeframe provenance",
     MIGRATION_5),
]

LATEST_VERSION = MIGRATIONS[-1][0]
