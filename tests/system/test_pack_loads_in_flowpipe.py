"""Every shipped pack must load in the real Flowpipe (installs the library mods from GitHub: needs network)."""

import os
import shutil

import pytest

from opslens import packs
from opslens.spec import render
from opslens.validate.load import load_check

pytestmark = [pytest.mark.system,
              pytest.mark.skipif(os.environ.get("OPSLENS_SYSTEM") != "1", reason="set OPSLENS_SYSTEM=1"),
              pytest.mark.skipif(shutil.which("flowpipe") is None, reason="flowpipe not installed")]


@pytest.mark.parametrize("pack", [p["pack"] for p in packs.list_packs()])
def test_pack_loads(pack, tmp_path):
    for name, text in render.render(packs.get(pack)).items():
        (tmp_path / name).write_text(text)
    issues = load_check(tmp_path)
    assert not [i for i in issues if i.level == "error"], [str(i) for i in issues]
    assert not [i for i in issues if i.code == "load-skipped"], "load check was skipped (network?)"
