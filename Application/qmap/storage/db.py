"""SQLite access: one connection per thread, explicit short write transactions, migrations."""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..core.errors import QmapError
from .schema import LATEST_VERSION, MIGRATIONS

BUSY_TIMEOUT_MS = 30_000


class DatabaseError(QmapError):
    code = "E_DB"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Database:
    """Wraps a SQLite file. Safe to share between threads (each gets its own connection).

    Separate processes simply create their own Database for the same file.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._local = threading.local()

    # ---- connections -------------------------------------------------------
    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @contextlib.contextmanager
    def transaction(self):
        """Short write transaction. BEGIN IMMEDIATE takes the write lock up front."""
        conn = self.connection()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.connection().execute(sql, params).fetchall()

    def one(self, sql: str, params=()):
        return self.connection().execute(sql, params).fetchone()

    # ---- migrations --------------------------------------------------------
    def current_version(self) -> int:
        conn = self.connection()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT)"
        )
        row = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_version").fetchone()
        return int(row["v"])

    def migrate(self) -> int:
        """Apply any missing migrations, each in one transaction. Safe if two processes start at the same time.

        A failing migration is rolled back completely (nothing half-applied is recorded as done), and a
        database written by a NEWER Q-MAP is refused rather than used by code that does not understand it.
        """
        latest = MIGRATIONS[-1][0]
        if self.current_version() > latest:
            raise DatabaseError(
                f"The metadata database {self.path} has schema version {self.current_version()}, which is newer than "
                f"this Q-MAP understands (version {latest}).", code="E_DB_NEWER",
                action="Use the Q-MAP version that created it (update this copy of the code).")
        for version, description, sql in MIGRATIONS:
            if self.current_version() >= version:
                continue
            conn = self.connection()
            script = (
                "BEGIN IMMEDIATE;\n" + sql
                + f"\nINSERT INTO schema_version(version, applied_at, description) "
                  f"VALUES ({version}, '{utc_now_iso()}', '{description.replace(chr(39), chr(39) * 2)}');\nCOMMIT;"
            )
            try:
                conn.executescript(script)
            except sqlite3.Error:
                if conn.in_transaction:
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute("ROLLBACK")
                # Another process may have applied it while we waited for the lock.
                if self.current_version() >= version:
                    continue
                raise
        return self.current_version()


def open_database(path: str | Path, *, migrate: bool = True) -> Database:
    db = Database(path)
    if migrate:
        db.migrate()
    return db


__all__ = ["Database", "DatabaseError", "open_database", "utc_now_iso", "LATEST_VERSION"]
