"""The migrated QLOPB engine is the original code: only import lines differ (Project Owner, 03-Nov-26: preserve the
calculation methodology; no formula or methodology change during the migration).

ORIGINAL holds the SHA-256 of every migrated file at BulluBhai/QLOPB commit 6cbadc7 (MA Affinity Scanner V2 + safeguards
S-1..S-3). Each migrated file, with `from qlopb.<package>` turned back into `from <package>`, must hash to the same value.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import qlopb

ROOT = Path(qlopb.__file__).resolve().parent
ORIGINAL = {
    "config/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "config/settings.py": "da07c55eb886ca96a3ff963604a18e2ca61cf0df90ee2c7e3130bb71a6d4cf63",
    "core/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "core/data_engine.py": "3e02ebe190e20f3e99defe13f0e2640f51201a7bd775c7598f79da8040a58e49",
    "core/research_engine.py": "2627ce4b533f65558823ba2c0141013ac750f80644863a759f79e8ab845bb216",
    "core/timeframe_engine.py": "656f111d2279be2d3989c66339a1b9996faff3c327c44cd26e3c81ca5742ea01",
    "core/validation.py": "150ad9093546d5341e2ef3a326b9ea8ccc965357fad9602e66622af028880af5",
    "references/__init__.py": "96bdfef10cab234754329c292bd43aab5257a0d349215a28aadbca92be9ab196",
    "references/bollinger_bands.py": "596cbf12e07212c5e7fa8b318418097b3e2661fdec855c99ffedb9908402fdd6",
    "references/camarilla.py": "aae932d1fcee79cea1606534444e1d54ccc9780fcaed584efc04a15570be94ff",
    "references/cpr.py": "cd97eb53cdb5bf8cda1074e928e1b2cf2366c64fdf594dfa900cb10c6ddc04c4",
    "references/moving_average.py": "a95915b67cfc33b93dfd36a2327ee5ab3c6e95701f0916953b6008b2f8951bed",
    "references/other_references.py": "ea4117e4c0500b70592e4564681ed4da9241497600c4a19c68bdbf4680d825e5",
    "references/pivot_points.py": "9ee23d3e683622681e9e693fe83debce841a24699ceda01f0ab20aee4b34ba2a",
    "references/previous_levels.py": "4e38e5a6dab777f4a2f2b560229a627ce750ecc0c602941606df51916a78024e",
    "analysis/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "analysis/affinity_engine.py": "6523da94232ebad5d16aeac6858d0a981f1976f5fdd2f26bfa31597892c7108c",
    "analysis/combination_engine.py": "ee3869cd991304e3e79deb8d743026ee6bd01e5eb1a703c9205c58540a480eba",
    "analysis/comparison_engine.py": "f3fc331b3c99b824e51feb72a42d9cfc93223a06f98f69fa5d6cd1e105cb4460",
    "analysis/interaction_engine.py": "8c6242800e10a29ecbf87b51063ff33c862637deb26b753ce38e90cc14e44c44",
    "validation/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "validation/is_oos.py": "cd699d936a91e5a7e789e3403b2a165a93ccc049130c55f7ed140e9341ba7853",
    "validation/robustness.py": "a46c036b267bd19391788bd2ed4b665ea6d59d4b6be8b51750876e4d013de95c",
    "validation/statistical_tests.py": "fa43b1427edc2f85dde8b30c4105b6a17aeee565bbe2a5749b70a6494ea17cbb",
    "storage/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "storage/file_provider.py": "7f6b606c6cd867f4924a4ad1d589208c80c98205444ae2d325683909d72a4e5d",
    "reports/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "reports/chart_report.py": "31cb42339633e5356de9e1c4b365a0493c49e3601da9fa168946bf04f1a33e64",
    "reports/excel_report.py": "7251ab516e6c8ef826b0fb17b2ba1c7464c5836aa58cfde4bd3f3d0d5699400c",
    "reports/pdf_report.py": "196c2a2eae374acb119f43f62a2fd24603d75ee4677942ba24d572c459f9f6f0",
    "gui/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "gui/research_controls.py": "e809c361108316ddbdc3fb91269cf6d2b6f8abe98646b37e6ba2611b76bf3a4b"
}
_IMPORT = re.compile(r"^(\s*)from qlopb\.(config|core|references|analysis|validation|storage|reports|gui)\b", re.M)


def _as_original(text: str) -> bytes:
    return _IMPORT.sub(r"\1from \2", text).encode("utf-8")


def test_every_migrated_file_matches_the_qlopb_original_apart_from_imports():
    for rel, sha in ORIGINAL.items():
        text = (ROOT / rel).read_bytes().decode("utf-8")
        assert hashlib.sha256(_as_original(text)).hexdigest() == sha, f"{rel} differs from QLOPB 6cbadc7"


def test_only_import_lines_were_touched():
    for rel in ORIGINAL:
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines():
            if "qlopb." in line and not line.lstrip().startswith("from qlopb."):
                raise AssertionError(f"{rel}: unexpected reference to the qlopb package: {line!r}")


def test_no_unlisted_python_file_in_the_engine():
    present = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts}
    assert present - set(ORIGINAL) == {"__init__.py"}, present - set(ORIGINAL)
    assert set(ORIGINAL) <= present


def test_standalone_window_is_not_migrated():
    assert not (ROOT / "gui" / "main_window.py").exists()
    assert qlopb.SOURCE_COMMIT.startswith("6cbadc7")
