"""Live checks against a real Steampipe service with the shipped plugins installed. Opt-in:

    OPSLENS_SYSTEM=1 OPSLENS__STEAMPIPE__PORT=9299 OPSLENS__STEAMPIPE__PASSWORD=... pytest -m system tests/system

(Use an isolated install: `steampipe plugin install aws@1.35.0 jira@2.0.5 microsoft365@1.3.0 theapsgroup/gitlab
jplanckeel/opsgenie --install-dir D` then `steampipe service start --install-dir D --database-port 9299`.)
"""

import os

import pytest

from opslens.catalog import tables
from opslens.config import load_config
from opslens.sql import client

pytestmark = [pytest.mark.system,
              pytest.mark.skipif(os.environ.get("OPSLENS_SYSTEM") != "1", reason="set OPSLENS_SYSTEM=1")]


@pytest.fixture(scope="module")
def cfg():
    return load_config()[0].steampipe


def test_catalog_matches_installed_plugins(cfg):
    cat = tables.load()
    merged = cat.with_live(client.live_columns(cfg, set(cat.plugins)))
    missing = sorted(n for n, t in merged.tables.items() if not t.live)
    assert not missing, f"catalog tables not in the installed plugins: {missing[:10]}"
    drift = {n: t.missing_live for n, t in merged.tables.items() if t.missing_live}
    assert not drift, f"column drift: {dict(list(drift.items())[:5])}"


def test_connection_is_read_only_with_timeout(cfg):
    r = client.run_live("select current_setting('default_transaction_read_only') as ro, "
                        "current_setting('statement_timeout') as t", cfg)
    assert r.rows[0]["ro"] == "on" and r.rows[0]["t"] != "0"


def test_row_cap(cfg):
    r = client.run_live("select generate_series(1, 50) as n", cfg, max_rows=10)
    assert len(r.rows) == 10 and r.truncated
