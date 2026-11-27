import os

import pytest

# Normal runs never read a developer's config or env, and never talk to cloud services.
# System runs (OPSLENS_SYSTEM=1) keep OPSLENS* so they can point at an isolated Steampipe.
SYSTEM = os.environ.get("OPSLENS_SYSTEM") == "1"
if not SYSTEM:
    for k in list(os.environ):
        if k.startswith("OPSLENS"):
            del os.environ[k]


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if not SYSTEM:
        monkeypatch.setenv("HOME", str(tmp_path))
