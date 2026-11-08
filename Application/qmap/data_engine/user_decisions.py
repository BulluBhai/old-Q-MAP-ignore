"""Reversible user decisions on datasets (owner instruction DQ-7..DQ-10, section 7.2, 03-Nov-26).

Imports are accepted by default. The user may REJECT a dataset afterwards (a wrong detected timeframe, a wrong
identity, unwanted data) and may RESTORE it later. A rejection never deletes, moves or changes anything: the dataset,
its file and the original source file stay exactly as they are; the dataset is only kept out of analyses (the
Workbench does not offer it and readiness refuses it with the reason). Every decision is appended to
dataset_user_decisions (schema migration 10) with its reason and where it was made, so the history is complete.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import QmapError
from ..storage.db import Database, utc_now_iso

REJECTED, RESTORED = "rejected", "restored"


class DecisionError(QmapError):
    pass


@dataclass
class DecisionResult:
    changed: list  # dataset ids whose decision was recorded
    unchanged: list  # (dataset id, why nothing was recorded)


def current_decision(db: Database, dataset_id: int) -> str | None:
    row = db.one("SELECT decision FROM dataset_user_decisions WHERE dataset_id = ? ORDER BY decision_id DESC LIMIT 1",
                 (dataset_id,))
    return row["decision"] if row else None


def history(db: Database, dataset_id: int) -> list:
    return db.query("SELECT * FROM dataset_user_decisions WHERE dataset_id = ? ORDER BY decision_id", (dataset_id,))


def _record(db: Database, ids, decision: str, reason: str | None, origin: str, run_id: str | None) -> DecisionResult:
    out = DecisionResult([], [])
    now = utc_now_iso()
    with db.transaction() as conn:
        for ds in dict.fromkeys(int(i) for i in ids):
            row = conn.execute("SELECT layer FROM datasets WHERE dataset_id = ?", (ds,)).fetchone()
            if row is None:
                out.unchanged.append((ds, "not registered"))
                continue
            if row["layer"] == "raw":
                out.unchanged.append((ds, "an original source file is never rejected"))
                continue
            last = conn.execute("SELECT decision FROM dataset_user_decisions WHERE dataset_id = ? ORDER BY decision_id "
                                "DESC LIMIT 1", (ds,)).fetchone()
            now_rejected = last is not None and last["decision"] == REJECTED
            if decision == REJECTED and now_rejected:
                out.unchanged.append((ds, "already rejected"))
                continue
            if decision == RESTORED and not now_rejected:
                out.unchanged.append((ds, "not rejected"))
                continue
            conn.execute("INSERT INTO dataset_user_decisions(dataset_id, decision, reason, origin, run_id, decided_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)", (ds, decision, (reason or "").strip() or None, origin, run_id, now))
            out.changed.append(ds)
    return out


def reject_datasets(db: Database, dataset_ids, *, reason: str | None = None, origin: str = "user",
                    run_id: str | None = None) -> DecisionResult:
    """Mark datasets as rejected by the user (reversible). Nothing is deleted or changed."""
    return _record(db, dataset_ids, REJECTED, reason, origin, run_id)


def restore_datasets(db: Database, dataset_ids, *, reason: str | None = None, origin: str = "user",
                     run_id: str | None = None) -> DecisionResult:
    """Undo a rejection: the datasets are offered to analyses again."""
    return _record(db, dataset_ids, RESTORED, reason, origin, run_id)
