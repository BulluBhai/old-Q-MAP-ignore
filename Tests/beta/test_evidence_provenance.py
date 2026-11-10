"""Provenance of the committed worked-example evidence (10-Nov-26 restructure; runs without a window).

- The FROZEN V1 evidence (09-Nov-26 folder) still names the clean build the owner-tested beta was made from.
- The release candidate's evidence, once its acceptance package exists on the branch, comes from a clean checkout of
  exactly the program code under test (regenerate it after any program change)."""

from __future__ import annotations

import json

import pytest

from fixtures import beta_example as B


def test_the_frozen_v1_evidence_names_the_owner_tested_build():
    B.check_frozen_v1_evidence(json.loads((B.FROZEN_V1_OUT / "Run_Metadata.json").read_text(encoding="utf-8")))


def test_the_release_candidate_evidence_names_a_clean_build_of_this_code():
    if not B.RELEASE_V1_OUT.exists():
        pytest.skip("no release-candidate evidence on this branch yet (it is added with the MA Affinity V2 release "
                    "candidate's acceptance package)")
    B.check_evidence_provenance(json.loads((B.RELEASE_V1_OUT / "Run_Metadata.json").read_text(encoding="utf-8")))
