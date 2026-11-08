"""Shared fixtures: temporary code/data/output roots, a migrated database and a run."""

from __future__ import annotations

import pytest

from qmap.core.config import load_settings
from qmap.core.runs import finish_run, start_run
from qmap.storage.db import open_database


@pytest.fixture
def roots(tmp_path):
    code, data, out = tmp_path / "code", tmp_path / "data", tmp_path / "output"
    for p in (code, data, out):
        p.mkdir()
    return {"code": code, "data": data, "output": out, "src": tmp_path / "src"}


@pytest.fixture
def settings(roots):
    roots["src"].mkdir(exist_ok=True)
    return load_settings(
        None,
        env={"QMAP_DATA_ROOT": str(roots["data"]), "QMAP_OUTPUT_ROOT": str(roots["output"])},
        code_root=roots["code"],
    )


@pytest.fixture
def db(settings):
    database = open_database(settings.db_path)
    yield database
    database.close()


@pytest.fixture
def run(settings, db):
    r = start_run(settings, db, "FOUND", area="Ingestion", module_name="Foundation", params={"test": True})
    yield r
    finish_run(r, "completed")


@pytest.fixture
def src(roots):
    folder = roots["src"]
    folder.mkdir(exist_ok=True)
    return folder
