import json

import pytest
from typer.testing import CliRunner

from opslens import __version__
from opslens.cli import app

pytestmark = pytest.mark.integration
runner = CliRunner()


def run(*args, **kw):
    return runner.invoke(app, list(args), **kw)


def test_version():
    r = run("--version")
    assert r.exit_code == 0 and __version__ in r.output


def test_find_tables_json():
    r = run("find", "tables", "jira", "issues", "-f", "json", "-n", "3")
    assert r.exit_code == 0
    assert json.loads(r.stdout)[0]["table"] == "jira_issue"


def test_find_pipelines_writes_only():
    r = run("find", "pipelines", "jira", "issue", "--writes", "-f", "json")
    assert r.exit_code == 0 and all(h["risk"] == "write" for h in json.loads(r.stdout))


def test_describe_unknown_suggests():
    r = run("describe", "table", "aws_ebs_volum")
    assert r.exit_code == 1 and "aws_ebs_volume" in r.output


def test_describe_pipeline_shows_usage_and_risk():
    r = run("describe", "pipeline", "jira.create_issue")
    assert r.exit_code == 0 and "project_key" in r.output and "write" in r.output


def test_query_demo_json():
    r = run("query", "--source", "demo", "select count(*) as n from aws_ebs_volume where state = 'available'", "-f", "json")
    assert r.exit_code == 0 and json.loads(r.stdout)[0]["n"] == 8


@pytest.mark.parametrize("sql", ["drop table aws_ebs_volume", "select 1; select 2", "select pg_sleep(5)"])
def test_query_refusals_exit_3(sql):
    r = run("query", "--source", "demo", sql)
    assert r.exit_code == 3 and "refused" in r.output


def test_query_row_cap_reports_truncation():
    r = run("query", "--source", "demo", "select volume_id from aws_ebs_volume", "-n", "2", "-f", "csv")
    assert r.exit_code == 0 and len(r.stdout.strip().splitlines()) == 3 and "truncated" in r.output


def test_query_without_steampipe_fails_clearly(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *_: None)
    r = run("query", "select 1", "--any-table")
    assert r.exit_code == 1 and "Steampipe is not running" in r.output


def test_init_then_params_and_config():
    assert run("init").exit_code == 0
    assert run("init").exit_code == 1  # refuses to overwrite
    r = run("params", "--filter", "port", "-f", "json")
    assert json.loads(r.stdout)[0]["key"] == "steampipe.port"
    r = run("params", "--set", "steampipe.port=1234", "-f", "json", "--filter", "steampipe.port")
    assert json.loads(r.stdout)[0]["value"] == 1234


def test_bad_set_is_exit_2():
    assert run("config", "--set", "steampipe.port=nope").exit_code == 2


def test_doctor_offline_runs():
    r = run("doctor", "--offline")
    assert r.exit_code == 0 and "table catalog" in r.output


def test_catalog_stats():
    r = run("catalog", "stats", "-f", "json")
    assert r.exit_code == 0


def test_generate_without_a_provider_explains_how_to_enable_it():
    r = run("generate", "stop idle ec2 instances and tell the team")
    assert r.exit_code == 1 and "llm.provider" in r.output


def test_explain_works_without_ai(tmp_path):
    r = run("explain", str(__import__("opslens").__path__[0] + "/packs/governance/tag_enforcement.yaml"))
    flat = " ".join(r.output.split())
    assert r.exit_code == 0 and "Only on approval" in flat and "aws.tag_resources" in flat


def test_show_context_prints_what_would_be_sent_and_redacts():
    r = run("generate", "unattached ebs volumes owned by bob@example.com", "--show-context")
    assert r.exit_code == 0 and "aws_ebs_volume" in r.output and "bob@example.com" not in r.output and "<email>" in r.output


def test_query_with_plain_words_points_to_search():
    from typer.testing import CliRunner

    from opslens.cli import app

    r = CliRunner().invoke(app, ["query", "Get information about an IP address", "--source", "demo"])
    assert r.exit_code == 3
    assert "opslens search" in r.output
