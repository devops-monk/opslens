import json
import os
import stat

import pytest

from opslens import connections as c
from opslens.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("OPSLENS_CONNECTIONS_FILE", str(tmp_path / "sub" / "connections.json"))
    for var in ("JIRA_URL", "JIRA_USER", "JIRA_TOKEN", "JIRA_API_TOKEN", "SLACK_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    c.activate({})
    return tmp_path / "sub" / "connections.json"


def test_save_is_private_and_never_in_status(store):
    c.save("jira", {"url": "https://x.atlassian.net/", "user": "a@b.c", "token": "SECRET-123"})
    assert stat.S_IMODE(store.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.parent.stat().st_mode) == 0o700
    assert json.loads(store.read_text())["jira"]["token"] == "SECRET-123"
    jira = next(s for s in c.status() if s.name == "jira")
    assert jira.state == "connected" and "SECRET-123" not in repr(jira)


def test_child_env_feeds_both_sides_and_real_env_wins(monkeypatch):
    c.save("jira", {"url": "https://x.atlassian.net/", "user": "a@b.c", "token": "T1"})
    env = c.child_env()
    assert env["JIRA_TOKEN"] == "T1" and env["JIRA_API_TOKEN"] == "T1" and env["JIRA_URL"] == "https://x.atlassian.net/"
    monkeypatch.setenv("JIRA_TOKEN", "FROM-ENV")
    env = c.child_env()
    assert env["JIRA_TOKEN"] == "FROM-ENV" and env["JIRA_API_TOKEN"] == "FROM-ENV"  # one real variable fills the other name too


def test_required_fields_and_unknown_service_and_field():
    with pytest.raises(c.ConnectionError_, match="needs"):
        c.save("jira", {"url": "u"})
    with pytest.raises(c.ConnectionError_, match="unknown service"):
        c.service("nope")
    with pytest.raises(c.ConnectionError_, match="no field"):
        c.save("slack", {"toke": "x"})
    with pytest.raises(c.ConnectionError_, match="profile"):
        c.save("aws", {"region": "us-east-1"})
    c.save("aws", {"profile": "dev"})


def test_defaults_applied_for_opsgenie():
    c.save("opsgenie", {"token": "k"})
    assert c.load_store()["opsgenie"]["url"] == "api.opsgenie.com"


def test_yaml_allows_non_secrets_and_refuses_secrets(tmp_path):
    f = tmp_path / "opslens.yaml"
    f.write_text("connections:\n  jira: {url: 'https://x.atlassian.net/', user: a@b.c}\n")
    cfg, _ = load_config(str(f))
    c.activate(cfg.connections)
    assert c.child_env()["JIRA_USER"] == "a@b.c"
    f.write_text("connections:\n  jira: {token: abc}\n")
    with pytest.raises(ConfigError, match="secret"):
        load_config(str(f))


def test_remove(store):
    c.save("slack", {"token": "xoxb-1"})
    assert c.remove("slack") and not c.remove("slack")
    assert "slack" not in c.load_store()
    assert os.path.exists(store)
