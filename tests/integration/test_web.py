import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from opslens import packs
from opslens.config import Config
from opslens.web.app import create_app

pytestmark = pytest.mark.integration
PACK = "finops-cleanup/unattached-volumes"


def make(mode="local", tmp_path=None, **kw):
    app = create_app(Config(), mode=mode, workspace=tmp_path, token="T", **kw)
    return TestClient(app)


def H(extra=None):
    return {"X-Opslens-Token": "T", **(extra or {})}


@pytest.fixture
def local(tmp_path):
    return make("local", tmp_path)


@pytest.fixture
def demo(tmp_path):
    return make("demo", tmp_path)


def pack_yaml(name=PACK):
    return packs.get(name).to_yaml()


def test_ui_and_meta(local):
    r = local.get("/")
    assert r.status_code == 200 and "opslens" in r.text and r.headers["content-security-policy"].startswith("default-src 'self'")
    m = local.get("/api/meta").json()
    assert m["mode"] == "local" and m["tables"] > 600 and m["pipelines"] > 400 and m["token"] == "T" and m["ai"] is False
    assert local.get("/static/app.js").status_code == 200


def test_search_and_describe(local):
    r = local.get("/api/search", params={"q": "unattached ebs volumes then open a jira ticket"}).json()
    assert r["tables"][0]["table"] == "aws_ebs_volume"
    assert r["actions"][0]["pipelines"][0]["pipeline"] == "jira.pipeline.create_issue" and r["actions"][0]["pipelines"][0]["effect"] == "notify"
    t = local.get("/api/table/aws_ebs_volume").json()
    assert any(c["name"] == "volume_id" for c in t["columns"])
    p = local.get("/api/pipeline/aws.delete_ebs_volume").json()
    assert p["effect"] == "change" and "step" in p["usage"]
    assert local.get("/api/table/nope").status_code == 404 and local.get("/api/pipeline/x.y").status_code == 404
    assert local.get("/api/search", params={"q": ""}).json()["tables"] == []


def test_validate_explain_and_errors(local):
    v = local.post("/api/validate", json={"yaml": pack_yaml()}).json()
    assert v["ok"] and v["hash"] and v["gated"] == ["aws.delete_ebs_volume"] and any("approval" in x for x in v["explain"])
    bad = pack_yaml().replace("aws_ebs_volume", "aws_ebs_nope")
    v = local.post("/api/validate", json={"yaml": bad}).json()
    assert not v["ok"] and v["hash"] is None and any(i["code"] == "sql" for i in v["issues"])
    assert local.post("/api/validate", json={"yaml": "- just a list"}).status_code == 422
    assert local.post("/api/validate", json={"yaml": "x" * 30000}).status_code == 422  # size cap


def test_preview_and_query_on_demo_data(local):
    p = local.post("/api/preview", json={"yaml": pack_yaml(), "source": "demo"}).json()
    assert p["items"] == 8 and p["changes"] == 8 and {a["effect"] for a in p["actions"]} == {"notify", "change"}
    q = local.post("/api/query", json={"sql": "select count(*) as n from aws_ebs_volume", "source": "demo"}).json()
    assert q["rows"][0]["n"] == 24
    assert local.post("/api/query", json={"sql": "delete from aws_ebs_volume", "source": "demo"}).status_code == 422
    assert local.post("/api/query", json={"sql": "select 1; select 2", "source": "demo"}).status_code == 422
    assert local.post("/api/preview", json={"yaml": pack_yaml(), "source": "bogus"}).status_code == 422


def test_state_changing_calls_need_the_token(local):
    assert local.post("/api/mods", json={"yaml": pack_yaml()}).status_code == 403
    assert local.post("/api/mods", json={"yaml": pack_yaml()}, headers={"X-Opslens-Token": "wrong"}).status_code == 403
    assert local.post("/api/mods", json={"yaml": pack_yaml()}, headers=H()).status_code == 200


def test_save_list_and_overwrite(local, tmp_path):
    r = local.post("/api/mods", json={"yaml": pack_yaml()}, headers=H()).json()
    assert r["name"] == "unattached_volume_cleanup" and (tmp_path / r["name"] / "pipelines.fp").is_file()
    assert local.post("/api/mods", json={"yaml": pack_yaml()}, headers=H()).status_code == 409
    assert local.post("/api/mods", json={"yaml": pack_yaml(), "force": True}, headers=H()).status_code == 200
    mods = local.get("/api/mods", headers=H()).json()
    assert mods[0]["hash"] == r["hash"] and mods[0]["deployed"] is False and mods[0]["gated"] == ["aws.delete_ebs_volume"]
    bad = pack_yaml().replace("aws_ebs_volume", "aws_ebs_nope")
    assert local.post("/api/mods", json={"yaml": bad}, headers=H()).status_code == 422


def test_deploy_requires_the_reviewed_hash_and_no_drift(local, tmp_path):
    name = local.post("/api/mods", json={"yaml": pack_yaml()}, headers=H()).json()["name"]
    r = local.post(f"/api/mods/{name}/deploy", json={"spec_hash": "0000"}, headers=H())
    assert r.status_code == 409 and "review it again" in r.json()["detail"]
    f = tmp_path / name / "pipelines.fp"
    f.write_text(f.read_text().replace("limit 50", "limit 5000"))
    r = local.post(f"/api/mods/{name}/deploy", json={"spec_hash": "x"}, headers=H())
    assert r.status_code == 422 and "drift" in r.json()["detail"]
    assert local.post("/api/mods/nope/deploy", json={"spec_hash": "x"}, headers=H()).status_code == 404
    assert local.post(f"/api/mods/{name}/run", json={}, headers=H()).status_code == 409  # not deployed


def test_mod_names_cannot_escape_the_workspace(local):
    assert local.post("/api/mods/..%2f..%2fetc/run", json={}, headers=H()).status_code in (404, 409)
    assert local.get("/api/mods/%2e%2e/audit", headers=H()).status_code == 404


def test_host_header_allow_list_blocks_rebinding(local):
    assert local.get("/api/meta", headers={"host": "evil.example.com"}).status_code == 400
    assert local.get("/api/meta", headers={"host": "localhost:8077"}).status_code == 200


def test_generate_without_provider_is_a_clear_error(local):
    r = local.post("/api/generate", json={"requirement": "stop idle ec2 instances"}, headers=H())
    assert r.status_code == 422 and "llm.provider" in r.json()["detail"]


# ---- demo mode: the public, sample-data-only variant

def test_demo_mode_disables_everything_with_side_effects(demo, tmp_path):
    assert demo.get("/api/meta").json()["mode"] == "demo"
    for method, path, body in [("post", "/api/mods", {"yaml": pack_yaml()}), ("post", "/api/generate", {"requirement": "stop idle ec2"}),
                               ("get", "/api/mods", None), ("post", "/api/mods/x/deploy", {"spec_hash": "x"}),
                               ("post", "/api/mods/x/run", {})]:
        r = getattr(demo, method)(path, headers=H(), **({"json": body} if body is not None else {}))
        assert r.status_code == 403, path
    assert not list(tmp_path.iterdir())


def test_demo_mode_forces_sample_data_even_if_live_is_requested(demo):
    p = demo.post("/api/preview", json={"yaml": pack_yaml(), "source": "live"}).json()
    assert p["source"] != "steampipe" and p["items"] == 8
    q = demo.post("/api/query", json={"sql": "select count(*) as n from aws_ebs_volume", "source": "live"}).json()
    assert q["rows"][0]["n"] == 24


def test_demo_mode_rate_limits(tmp_path):
    c = make("demo", tmp_path, rate_per_minute=5)
    codes = [c.get("/api/meta").status_code for _ in range(8)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429] * 3


def test_demo_mode_never_exposes_a_real_provider(demo):
    assert demo.get("/api/meta").json()["ai"] is False


# ---- the visual builder sends the spec as an object; these endpoints back it


def pack_spec(name=PACK):
    return packs.get(name).model_dump(mode="json")


def test_validate_accepts_a_structured_spec_and_returns_what_the_builder_needs(demo):
    v = demo.post("/api/validate", json={"spec": pack_spec()}).json()
    assert v["ok"] and v["hash"] and v["columns"][:2] == ["volume_id", "region"]
    assert v["spec"]["name"] == "unattached_volume_cleanup" and "name: unattached_volume_cleanup" in v["yaml"]
    assert v["gated"] == ["aws.delete_ebs_volume"] and v["explain"]


def test_validate_reports_a_half_built_spec_instead_of_failing(demo):
    half = {"name": "x_y", "title": "T", "detect": {"sql": "select volume_id from aws_ebs_volume"}, "actions": []}
    r = demo.post("/api/validate", json={"spec": half})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["issues"][0]["code"] == "spec"
    bad = demo.post("/api/validate", json={"spec": {**half, "actions": [{"pipeline": "jira.create_issue", "args": {}}]}}).json()
    assert not bad["ok"] and {i["code"] for i in bad["issues"]} == {"arg-missing"}
    assert demo.post("/api/validate", json={}).status_code == 422  # neither yaml nor spec: still a hard error


def test_structured_and_yaml_forms_give_the_same_hash(demo):
    a = demo.post("/api/validate", json={"spec": pack_spec()}).json()["hash"]
    b = demo.post("/api/validate", json={"yaml": pack_yaml()}).json()["hash"]
    assert a == b


def test_a_write_still_needs_its_gate_in_the_structured_form(demo):
    s = pack_spec()
    for a in s["actions"]:
        a["gated"] = False
    v = demo.post("/api/validate", json={"spec": s}).json()
    assert not v["ok"] and any(i["code"] == "ungated-write" for i in v["issues"])


def test_preview_and_save_take_a_structured_spec(local, tmp_path):
    p = local.post("/api/preview", json={"spec": pack_spec(), "source": "demo"}).json()
    assert p["items"] > 0 and p["changes"] > 0
    assert local.post("/api/mods", json={"spec": pack_spec()}, headers=H()).status_code == 200
    got = local.get("/api/mods/unattached_volume_cleanup", headers=H()).json()
    assert got["spec"]["title"] and got["hash"] and "name:" in got["yaml"]
    assert local.get("/api/mods/nope", headers=H()).status_code == 404


def test_pack_list_has_what_the_gallery_shows(demo):
    rows = {r["pack"]: r for r in demo.get("/api/packs").json()}
    r = rows[PACK]
    assert r["category"] == "finops-cleanup" and r["apps"] == ["aws", "jira"] and r["schedule"] == "daily" and r["description"]
    assert [(s["effect"], s["gated"]) for s in r["steps"]] == [("notify", False), ("change", True)]
    assert rows["incident/incident-copilot"]["apps"] == ["gitlab", "jira", "opsgenie", "teams"]
    assert rows["incident/incident-copilot"]["schedule"] == ""


def test_action_picker_and_column_helper(demo):
    hits = demo.get("/api/pipelines?q=open a jira ticket").json()
    assert hits[0]["pipeline"] == "jira.create_issue" and {p["name"] for p in hits[0]["params"]} >= {"project_key", "summary"}
    assert all(not p["name"].startswith("cnx") for h in hits for p in h["params"])
    assert demo.get("/api/pipelines").json()  # a useful starter list with no query
    core = {"aws", "aws_tags", "aws_thrifty", "gitlab", "jira", "opsgenie", "teams"}
    assert {h["mod"] for h in demo.get("/api/pipelines?q=send a message").json()} <= core  # supported services only by default
    assert any(h["mod"] == "slack" for h in demo.get("/api/pipelines?q=slack send message&other=true").json())
    ok = demo.post("/api/columns", json={"sql": "select volume_id as v, region from aws_ebs_volume"}).json()
    assert ok == {"ok": True, "columns": ["v", "region"], "error": ""}
    assert "SELECT *" in demo.post("/api/columns", json={"sql": "select * from aws_ebs_volume"}).json()["error"]
    assert not demo.post("/api/columns", json={"sql": "drop table aws_ebs_volume"}).json()["ok"]
    assert not demo.post("/api/columns", json={"sql": "select a from not_a_table"}).json()["ok"]


def test_structured_spec_size_is_limited(demo):
    s = pack_spec()
    s["description"] = "x" * 25_000
    assert demo.post("/api/validate", json={"spec": s}).status_code in (200, 422)
    assert demo.post("/api/preview", json={"spec": s, "source": "demo"}).status_code == 422
