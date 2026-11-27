import copy

import pytest

from opslens import packs
from opslens.spec import check, render
from opslens.spec.model import Spec, load_spec

pytestmark = pytest.mark.unit

BASE = {
    "name": "t_spec", "title": "T",
    "detect": {"sql": "select volume_id, region, size from aws_ebs_volume where state = 'available'"},
    "actions": [{"pipeline": "jira.create_issue",
                 "args": {"project_key": "OPS", "issue_type": "Task", "summary": "Volume {volume_id} in {region}"}}],
}


def spec(**over):
    d = copy.deepcopy(BASE)
    d.update(over)
    return Spec.model_validate(d)


def codes(s):
    return {i.code for i in check.validate(s) if i.level == "error"}


def test_clean_spec_has_no_errors():
    assert codes(spec()) == set()


def test_pack_validates_and_renders():
    s = packs.get("finops-cleanup/unattached-volumes")
    assert not check.errors(check.validate(s))
    files = render.render(s)
    assert {"mod.fp", "pipelines.fp", "triggers.fp", "spec.yaml", "README.md"} <= set(files)


@pytest.mark.parametrize("sql,code", [
    ("select * from aws_ebs_volume", "sql-star"),
    ("select volume_id from aws_iam_nope", "sql"),
    ("select volume_id from aws_ebs_volume; drop table x", "sql"),
    ("delete from aws_ebs_volume", "sql"),
    ("select pg_sleep(9)", "sql"),
])
def test_detect_query_rules(sql, code):
    assert code in codes(spec(detect={"sql": sql}))


def test_change_pipeline_must_be_gated():
    acts = [{"pipeline": "aws.delete_ebs_volume", "args": {"volume_id": "{volume_id}", "region": "{region}"}}]
    assert "ungated-write" in codes(spec(actions=acts))
    acts[0]["gated"] = True
    assert not codes(spec(actions=acts))


def test_auto_apply_downgrades_to_a_warning():
    acts = [{"pipeline": "aws.delete_ebs_volume", "args": {"volume_id": "{volume_id}", "region": "{region}"}}]
    issues = check.validate(spec(actions=acts, auto_apply=True))
    assert not check.errors(issues) and any(i.code == "auto-apply" for i in issues)


def test_notify_pipelines_need_no_gate():
    assert "ungated-write" not in codes(spec())  # jira.create_issue is additive


@pytest.mark.parametrize("args,code", [
    ({"project_key": "OPS", "issue_type": "Task"}, "arg-missing"),
    ({"project_key": "OPS", "issue_type": "Task", "summary": "x", "nope": "y"}, "arg-unknown"),
    ({"project_key": "OPS", "issue_type": "Task", "summary": "{not_a_column}"}, "placeholder"),
    ({"project_key": "{var.undeclared}", "issue_type": "Task", "summary": "x"}, "placeholder"),
])
def test_argument_rules(args, code):
    assert code in codes(spec(actions=[{"pipeline": "jira.create_issue", "args": args}]))


def test_unknown_pipeline_suggests():
    issues = check.validate(spec(actions=[{"pipeline": "jira.create_isue", "args": {}}]))
    assert any("jira.pipeline.create_issue" in i.message for i in issues)


def test_inline_secrets_are_refused():
    acts = [{"pipeline": "slack.post_message", "args": {"channel": "#ops", "token": "xoxb-123"}}]
    assert "inline-secret" in codes(spec(actions=acts))


@pytest.mark.parametrize("sched,ok", [("daily", True), ("15m", True), ("1m", False), ("*/10 * * * *", True),
                                      ("whenever", False)])
def test_schedule_rules(sched, ok):
    assert (not (codes(spec(trigger={"kind": "schedule", "schedule": sched})) & {"schedule"})) is ok


def test_name_must_be_a_slug():
    with pytest.raises(ValueError):
        spec(name="Bad Name!")


def test_unknown_spec_keys_are_rejected():
    with pytest.raises(ValueError):
        load_spec("name: x_y\ntitle: t\ndetect: {sql: 'select 1 from aws_ebs_volume'}\nactions: []\nbogus: 1\n")


# ---- rendering


def test_render_is_deterministic():
    s = packs.get("finops-cleanup/unattached-volumes")
    assert render.render(s) == render.render(s) and render.spec_hash(s) == render.spec_hash(s)


def test_gated_actions_sit_behind_the_approval_step():
    hcl = render.render(packs.get("finops-cleanup/unattached-volumes"))["pipelines.fp"]
    approve = hcl.index('step "input" "approve"')
    delete = hcl.index('step "pipeline" "act_2_delete_ebs_volume"')
    assert approve < delete and 'if       = step.input.approve.value == "approve"' in hcl[delete:]
    create = hcl.index('step "pipeline" "act_1_create_issue"')
    assert 'step.input.approve' not in hcl[create:approve]


def test_detect_is_capped_and_schedule_is_off_by_default():
    files = render.render(packs.get("finops-cleanup/unattached-volumes"))
    assert "limit 50" in files["pipelines.fp"]
    assert 'variable "trigger_enabled"' in files["pipelines.fp"] and "default     = false" in files["pipelines.fp"]


def test_values_cannot_inject_hcl():
    evil = 'x" } step "http" "pwn" { url = "http://evil" } #${file("/etc/passwd")}%{if true}'
    s = spec(actions=[{"pipeline": "jira.create_issue",
                       "args": {"project_key": "OPS", "issue_type": "Task", "summary": evil + " {volume_id}"}}])
    hcl = render.render(s)["pipelines.fp"]
    assert 'step "http" "pwn"' not in hcl.replace('\\"', "")
    assert "$${file(" in hcl and "%%{if" in hcl  # template openers are neutralised
    assert hcl.count('step "http"') == 0


def test_renderer_never_inlines_connections_or_secrets():
    hcl = render.render(packs.get("finops-cleanup/unattached-volumes"))["pipelines.fp"]
    assert "connection.steampipe.default" in hcl and "notifier.default" in hcl
    assert "api_token" not in hcl and "password" not in hcl.lower()


def test_mod_requires_only_the_mods_used():
    mod = render.render(packs.get("finops-cleanup/unattached-volumes"))["mod.fp"]
    assert "flowpipe-mod-aws\"" in mod and "flowpipe-mod-jira" in mod and "flowpipe-mod-slack" not in mod


def test_pack_variable_overrides():
    assert packs.get("finops-cleanup/unattached-volumes", {"jira_project": "INFRA"}).variables["jira_project"].default == "INFRA"
    with pytest.raises(KeyError):
        packs.get("finops-cleanup/unattached-volumes", {"nope": "1"})
    with pytest.raises(KeyError):
        packs.get("no/such-pack")
