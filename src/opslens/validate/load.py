"""Load check: let Flowpipe's own parser judge a generated mod.

Flowpipe has no `validate` command, but loading a mod parses and type-checks all of it: `flowpipe pipeline list`
exits 0 on a good mod and non-zero (with file:line messages) on syntax, reference and type errors. This runs in a
scratch copy so the mod directory is never touched (Flowpipe would otherwise create .flowpipe/ inside it).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..spec.check import Issue


def load_check(mod_dir: Path, binary: str = "flowpipe") -> list[Issue]:
    if not shutil.which(binary):
        return [Issue("warning", "load-skipped", "flowpipe is not installed; the load check was skipped "
                      "(brew install turbot/tap/flowpipe)")]
    with tempfile.TemporaryDirectory() as tmp:
        work, data = Path(tmp) / "mod", Path(tmp) / "data"
        shutil.copytree(mod_dir, work, ignore=shutil.ignore_patterns(".flowpipe", ".git"))
        data.mkdir()
        if "mod \"github.com" in (work / "mod.fp").read_text():
            r = subprocess.run([binary, "mod", "install", "--data-dir", str(data)], cwd=work, check=False,
                               capture_output=True, text=True, timeout=300)
            if r.returncode:
                return [Issue("warning", "load-skipped", "could not install the library mods (offline?), so the load check "
                              f"was skipped: {(r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else ''}")]
        r = subprocess.run([binary, "pipeline", "list", "--output", "json", "--data-dir", str(data)], cwd=work, check=False,
                           capture_output=True, text=True, timeout=120)
        if r.returncode:
            msg = (r.stderr or r.stdout).strip().replace(str(work), ".")
            return [Issue("error", "load", f"Flowpipe rejected the mod: {msg}")]
        try:
            found = {p["name"].split(".")[-1] for p in json.loads(r.stdout)}
        except (ValueError, KeyError):
            return [Issue("warning", "load", "Flowpipe loaded the mod but its output could not be read")]
        return [] if found else [Issue("error", "load", "Flowpipe loaded the mod but found no pipelines")]
