import json

import pytest
from typer.testing import CliRunner

from opslens.cli import app

pytestmark = pytest.mark.integration
runner = CliRunner()
PACK = "finops-cleanup/unattached-volumes"


def run(*a):
    return runner.invoke(app, list(a))


def install(tmp_path):
    r = run("pack", "install", PACK, "--out", str(tmp_path), "--var", "jira_project=INFRA")
    assert r.exit_code == 0, r.output
    return tmp_path / "unattached_volume_cleanup"


def test_pack_list_and_show():
    assert PACK in run("pack", "list", "-f", "json").stdout
    assert "jira_project" in run("pack", "show", PACK).stdout


def test_install_writes_the_mod_and_refuses_to_overwrite(tmp_path):
    d = install(tmp_path)
    assert {p.name for p in d.iterdir()} == {"mod.fp", "pipelines.fp", "triggers.fp", "spec.yaml", "README.md"}
    assert "INFRA" in (d / "pipelines.fp").read_text()
    assert run("pack", "install", PACK, "--out", str(tmp_path)).exit_code == 1
    assert run("pack", "install", PACK, "--out", str(tmp_path), "--force").exit_code == 0


def test_validate_passes_then_catches_a_hand_edit(tmp_path):
    d = install(tmp_path)
    assert run("validate", str(d), "--no-load").exit_code == 0
    (d / "pipelines.fp").write_text((d / "pipelines.fp").read_text().replace("limit 50", "limit 5000"))
    r = run("validate", str(d), "--no-load")
    assert r.exit_code == 1 and "drift" in r.output


def test_validate_rejects_an_unsafe_spec(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("name: bad_one\ntitle: Bad\ndetect: {sql: 'select volume_id, region from aws_ebs_volume'}\n"
                 "actions:\n  - pipeline: aws.delete_ebs_volume\n    args: {volume_id: '{volume_id}', region: '{region}'}\n")
    r = run("validate", str(f), "--no-load")
    assert r.exit_code == 1 and "ungated-write" in r.output


def test_render_refuses_an_invalid_spec_and_writes_nothing(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("name: bad_one\ntitle: Bad\ndetect: {sql: 'select * from aws_ebs_volume'}\n"
                 "actions:\n  - pipeline: jira.create_issue\n    args: {project_key: A, issue_type: B, summary: C}\n")
    r = run("render", str(f), "--out", str(tmp_path / "out"))
    assert r.exit_code == 1 and not (tmp_path / "out").exists()


def test_preview_demo_reports_blast_radius_and_changes_nothing(tmp_path):
    d = install(tmp_path)
    r = run("preview", str(d), "--source", "demo", "-f", "json")
    assert r.exit_code == 0
    out = json.loads(r.stdout)
    assert out["items"] == 8 and len(out["actions"]) == 2
    assert [a["effect"] for a in out["actions"]] == ["notify", "change"] and out["actions"][1]["gated"] is True
    assert out["actions"][0]["calls"][0]["project_key"] == "INFRA"
    assert "0" in run("preview", str(d), "--source", "demo").output.split("state change(s)")[1][:60]


def test_deploy_refuses_without_the_approved_hash_and_shows_what_to_review(tmp_path):
    d = install(tmp_path)
    r = run("deploy", str(d))
    assert r.exit_code == 2
    assert "review before deploying" in r.output and "--approve" in r.output and "aws.delete_ebs_volume" in r.output
    r = run("deploy", str(d), "--approve", "0000000000000000")  # a hash you did not review
    assert r.exit_code == 2


def test_deploy_refuses_a_drifted_mod(tmp_path):
    d = install(tmp_path)
    (d / "pipelines.fp").write_text((d / "pipelines.fp").read_text().replace("limit 50", "limit 5000"))
    r = run("deploy", str(d), "--approve", "x")
    assert r.exit_code == 1 and "drift" in r.output


def test_run_requires_a_deployment(tmp_path):
    d = install(tmp_path)
    assert run("run", str(d)).exit_code == 1
    assert run("undeploy", str(d)).exit_code == 1
