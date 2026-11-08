"""The one definition of where Q-MAP stores a managed (standardised or derived) dataset when it is created.

Used when files are written (ingest, derive) and by recovery to reconstruct a dataset's ORIGINAL path from registry
records that cannot be changed (decision D2-19: the file name carries its lineage and the creating Run ID).
Changing these formulas changes where NEW files go; existing registry paths are never rewritten.
"""

from __future__ import annotations

import hashlib


def _version_hash(processing_version: str) -> str:
    return hashlib.sha256(processing_version.encode()).hexdigest()[:8]


def cleaned_relative_path(exchange: str, symbol: str, timeframe: str, raw_sha256: str, processing_version: str,
                          run_id: str) -> str:
    return (f"Cleaned_Data/{exchange}/{symbol}/{timeframe}/"
            f"{raw_sha256[:12]}_{_version_hash(processing_version)}_{run_id}.parquet")


def derived_relative_path(exchange: str, symbol: str, timeframe: str, source_sha256: str, processing_version: str,
                          run_id: str) -> str:
    return (f"Timeframe_Data/{exchange}/{symbol}/{timeframe}/"
            f"{source_sha256[:12]}_{_version_hash(processing_version)}_{run_id}.parquet")
