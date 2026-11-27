import pytest

from opslens.catalog import pipelines as pcat
from opslens.catalog import search as csearch
from opslens.catalog import tables as tcat
from opslens.demo import TABLES

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def tc():
    return tcat.load()


@pytest.fixture(scope="module")
def pc():
    return pcat.load()


def test_shipped_catalog_size(tc, pc):
    assert set(tc.plugins) == {"aws", "jira", "gitlab", "microsoft365", "opsgenie"}
    assert len(tc.tables) > 650 and len(pc.pipelines) > 400 and len(pc.mods) >= 14


@pytest.mark.parametrize("text,table", [
    ("unattached ebs volumes", "aws_ebs_volume"),
    ("elastic ip addresses", "aws_vpc_eip"),
    ("jira issues", "jira_issue"),
    ("opsgenie alerts", "opsgenie_alert"),
    ("who deleted the bucket", "aws_cloudtrail_lookup_event"),
])
def test_table_search_finds_the_obvious_table(tc, text, table):
    assert table in [h["table"] for h in tc.find(text, k=5)]


@pytest.mark.parametrize("text,pipeline", [
    ("create jira issue", "jira.pipeline.create_issue"),
    ("create opsgenie alert", "opsgenie.pipeline.create_alert"),
    ("send teams channel message", "teams.pipeline.send_channel_message"),
    ("post slack message", "slack.pipeline.post_message"),
])
def test_pipeline_search_ranks_the_right_action_first_or_second(pc, text, pipeline):
    assert pipeline in [h["pipeline"] for h in pc.find(text, k=2)]


def test_destructive_pipelines_do_not_lead_unless_asked(pc):
    assert not pc.find("teams channel message", k=1)[0]["pipeline"].endswith("delete_channel_message")
    assert pc.find("delete teams channel message", k=1)[0]["pipeline"].endswith("delete_channel_message")


def test_risk_classes(pc):
    assert pc.get("jira.create_issue").risk == "write"
    assert pc.get("jira.pipeline.list_issues").risk == "read"
    assert pc.get("aws.pipeline.delete_ebs_volume").risk == "write"
    assert pc.get("aws_thrifty.pipeline.detect_and_correct_ebs_volumes_if_unattached").risk == "write"
    assert all(p.risk in ("read", "write") for p in pc.pipelines.values())


def test_pipeline_lookup_forms(pc):
    full = pc.get("jira.pipeline.create_issue")
    assert full and pc.get("jira.create_issue") is full
    assert pc.get("nope") is None and "jira.pipeline.create_issue" in pc.similar("jira.create_isue")


def test_pipeline_interface_is_typed(pc):
    d = pc.describe("jira.pipeline.create_issue")
    assert {"project_key", "issue_type", "summary"} <= {p["name"] for p in d["params"] if p["required"]}
    assert "step \"pipeline\"" in d["usage"] and "jira.pipeline.create_issue" in d["usage"]


def test_requirement_is_split_into_data_and_action(tc):
    res = csearch.find("unattached ebs volumes older than 14 days, then open a jira ticket and post to teams", k=3)
    assert res["tables"][0]["table"] == "aws_ebs_volume"
    assert [a["clause"] for a in res["actions"]] == ["open a jira ticket", "post to teams"]
    assert res["actions"][0]["pipelines"][0]["pipeline"] == "jira.pipeline.create_issue"
    assert res["actions"][1]["pipelines"][0]["pipeline"].startswith("teams.")


def test_plugin_filter(tc):
    assert {h["plugin"] for h in tc.find("issue", k=10, plugins={"jira"})} == {"jira"}


def test_demo_tables_and_columns_exist_in_the_real_catalog(tc):
    for name, rows in TABLES.items():
        t = tc.get(name)
        assert t is not None, f"demo table {name} is not in the catalog"
        unknown = set(rows[0]) - set(t.columns)
        assert not unknown, f"demo columns not in {name}: {unknown}"


def test_doctor_parses_steampipe_plugin_list():
    """Real `steampipe plugin list --output json` output (the key is `installed`, not `plugins`)."""
    from opslens.doctor import installed_plugins

    text = ('{"installed":[{"name":"hub.steampipe.io/plugins/jplanckeel/opsgenie@latest","version":"0.0.2",'
            '"connections":["opsgenie"]},{"name":"hub.steampipe.io/plugins/turbot/aws@1.35.0","version":"1.35.0",'
            '"connections":["aws"]}]}')
    assert installed_plugins(text) == {"opsgenie": "0.0.2", "aws": "1.35.0"}


def test_shipped_catalog_versions_match_the_pinned_plugins():
    """versions.PLUGINS (what install.sh and the Dockerfile install) must be what the catalogs were built from."""
    from opslens import versions

    cat = tcat.load()
    for plugin, meta in versions.PLUGINS.items():
        pinned = meta["install"].split("@")[1] if "@" in meta["install"] else None
        if pinned:
            assert cat.plugins[plugin] == pinned, f"{plugin}: catalog {cat.plugins[plugin]} vs pinned {pinned}"
