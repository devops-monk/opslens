"""Flowpipe's own parser is the Phase 2 validator's load check. Pin the behaviour it relies on (needs `flowpipe`).

    OPSLENS_SYSTEM=1 pytest -m system tests/system/test_flowpipe_load.py
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.system,
              pytest.mark.skipif(os.environ.get("OPSLENS_SYSTEM") != "1", reason="set OPSLENS_SYSTEM=1"),
              pytest.mark.skipif(shutil.which("flowpipe") is None, reason="flowpipe not installed")]
MODS = Path(__file__).resolve().parents[1] / "fixtures" / "mods"


def load(name, tmp_path):
    work = tmp_path / name
    shutil.copytree(MODS / name, work)  # never create .flowpipe inside the repo
    data = tmp_path / f"data-{name}"
    data.mkdir()
    return subprocess.run(["flowpipe", "pipeline", "list", "--output", "json", "--data-dir", str(data)], cwd=work,
                          check=False, capture_output=True, text=True)


def test_good_mod_loads_and_exposes_a_typed_interface(tmp_path):
    r = load("good", tmp_path)
    assert r.returncode == 0
    p = json.loads(r.stdout)[0]
    assert p["name"] == "good.pipeline.hello" and p["params"][0]["type_string"] == "string"


@pytest.mark.parametrize("bad,why", [("bad_syntax", "Invalid expression"), ("bad_ref", "does not exist"),
                                     ("bad_type", "type specification")])
def test_broken_mods_fail_with_a_readable_reason(bad, why, tmp_path):
    r = load(bad, tmp_path)
    assert r.returncode != 0 and why in (r.stdout + r.stderr)
