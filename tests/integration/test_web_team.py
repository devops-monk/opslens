"""Team mode: the full workflow hosted for a team, which must never be reachable without signing in."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from opslens import packs
from opslens.config import Config
from opslens.web.app import create_app, team_settings_problems

pytestmark = pytest.mark.integration
PW = "correct horse battery"
SECRET = "proxy-secret-0123456789"
HOST = {"Host": "ops.example.com"}


def team(tmp_path, **kw):
    kw = {"auth": "password", "password": PW, "allow_hosts": ("ops.example.com",), "secure_cookies": False, **kw}
    return TestClient(create_app(Config(), mode="team", workspace=tmp_path, token="T", **kw), base_url="http://ops.example.com")


def login(c, user="alice", password=PW):
    return c.post("/api/login", json={"user": user, "password": password})


# ---------------------------------------------------------------- it refuses to start unsafe
def test_refuses_to_start_without_auth_or_host(tmp_path):
    for kw in ({}, {"auth": "password"}, {"auth": "password", "password": "short", "allow_hosts": ("h",)},
               {"auth": "proxy", "allow_hosts": ("h",)}, {"auth": "password", "password": PW}):
        with pytest.raises(ValueError):
            create_app(Config(), mode="team", workspace=tmp_path, **kw)
    assert not team_settings_problems(auth="password", password=PW, proxy_secret=None, allow_hosts=("h",))
    assert not team_settings_problems(auth="proxy", password=None, proxy_secret=SECRET, allow_hosts=("h",))


# ---------------------------------------------------------------- password sign-in
def test_everything_needs_sign_in(tmp_path):
    c = team(tmp_path)
    for path in ("/api/meta", "/api/packs", "/api/mods", "/api/search?q=x"):
        assert c.get(path).status_code == 401, path
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "login"
    assert c.get("/healthz").json()["ok"] is True  # health checks and the login assets are public
    assert "Sign in" in c.get("/login").text and c.get("/static/login.js").status_code == 200


def test_wrong_password_and_bad_name_are_refused(tmp_path):
    c = team(tmp_path)
    assert login(c, password="nope").status_code == 401
    assert login(c, user="<script>").status_code == 422
    assert c.get("/api/meta").status_code == 401


def test_sign_in_sets_a_hardened_cookie_and_unlocks_the_app(tmp_path):
    c = team(tmp_path, secure_cookies=True)
    r = login(c)
    assert r.status_code == 200 and r.json()["user"] == "alice"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
    c.cookies.set("opslens_session", r.cookies["opslens_session"], domain="ops.example.com")
    m = c.get("/api/meta").json()
    assert m["mode"] == "team" and m["user"] == "alice" and m["auth"] == "password" and m["live"] is True
    assert c.get("/api/meta").headers["cache-control"] == "no-store"
    assert c.get("/login", follow_redirects=False).status_code == 303  # already signed in


def test_session_cookie_cannot_be_forged_or_replayed_with_another_secret(tmp_path):
    c = team(tmp_path, session_secret="A" * 32)
    login(c)
    good = c.cookies.get("opslens_session")
    other = team(tmp_path, session_secret="B" * 32)  # a different server secret rejects it
    other.cookies.set("opslens_session", good)
    assert other.get("/api/meta").status_code == 401
    body, mac = good.rsplit(".", 1)
    for bad in (body + "." + "0" * len(mac), "x." + mac, "", "garbage"):
        c.cookies.clear()
        c.cookies.set("opslens_session", bad)
        assert c.get("/api/meta").status_code == 401, bad


def test_mutating_calls_still_need_the_token(tmp_path):
    c = team(tmp_path)
    login(c)
    y = packs.get("finops-cleanup/unattached-volumes").to_yaml()
    assert c.post("/api/mods", json={"yaml": y}).status_code == 403  # signed in, but no CSRF token
    assert c.post("/api/mods", json={"yaml": y}, headers={"X-Opslens-Token": "T"}).status_code == 200
    assert c.get("/api/mods").json()  # and what was saved is visible


def test_logout_ends_the_session(tmp_path):
    c = team(tmp_path)
    login(c)
    assert c.get("/api/meta").status_code == 200
    c.post("/api/logout")
    assert c.get("/api/meta").status_code == 401


def test_sign_in_attempts_are_rate_limited(tmp_path):
    c = team(tmp_path)
    codes = [login(c, password="wrong").status_code for _ in range(12)]
    assert 429 in codes and login(c).status_code == 429  # even the right password waits


def test_host_allow_list_still_applies(tmp_path):
    c = team(tmp_path)
    assert c.get("/healthz", headers={"Host": "evil.example.net"}).status_code == 400


def test_audit_log_records_who_acted(tmp_path):
    from opslens.runs.store import Audit
    from opslens.web.app import actor_var

    c = team(tmp_path)
    login(c, user="carol")
    # the audit actor is taken from the signed-in user for every request
    seen = []
    app = c.app

    @app.get("/api/_who")
    def _who():  # test-only route, registered after the middleware
        seen.append(actor_var.get())
        return {}

    c.get("/api/_who")
    assert seen == ["carol"]
    Audit(tmp_path).log("deploy", "m", "h", "x", actor=seen[0])
    assert Audit(tmp_path).events("m")[0]["actor"] == "carol"


# ---------------------------------------------------------------- identity-proxy sign-in
def proxy(tmp_path):
    return team(tmp_path, auth="proxy", password=None, proxy_secret=SECRET)


def test_proxy_mode_trusts_the_identity_header_only_with_the_shared_secret(tmp_path):
    c = proxy(tmp_path)
    assert c.get("/api/meta", headers={"X-Forwarded-Email": "mallory@example.com"}).status_code == 401  # forged, no secret
    assert c.get("/api/meta", headers={"X-Forwarded-Email": "mallory@example.com", "X-Opslens-Proxy-Secret": "wrong"}).status_code == 401
    assert c.get("/api/meta", headers={"X-Opslens-Proxy-Secret": SECRET}).status_code == 401  # vouched, but no identity
    ok = c.get("/api/meta", headers={"X-Forwarded-Email": "dana@example.com", "X-Opslens-Proxy-Secret": SECRET})
    assert ok.status_code == 200 and ok.json()["user"] == "dana@example.com" and ok.json()["auth"] == "proxy"
    assert c.post("/api/login", json={"user": "x", "password": PW}).status_code in (401, 404)  # no password door in proxy mode


# ---------------------------------------------------------------- the other modes are unchanged
def test_local_and_demo_have_no_sign_in(tmp_path):
    for mode in ("local", "demo"):
        c = TestClient(create_app(Config(), mode=mode, workspace=tmp_path, token="T"))
        assert c.get("/api/meta").json()["user"] is None
        assert c.post("/api/login", json={"user": "a", "password": "b"}).status_code == 404


# ---------------------------------------------------------------- the command line
def test_cli_refuses_unsafe_team_and_local_setups(monkeypatch):
    from typer.testing import CliRunner

    from opslens.cli import app

    for k in ("OPSLENS_TEAM_PASSWORD", "OPSLENS_PROXY_SECRET"):
        monkeypatch.delenv(k, raising=False)
    r = CliRunner().invoke(app, ["serve", "--mode", "team", "--host", "0.0.0.0"])
    assert r.exit_code == 2 and "will not start without sign-in" in r.output
    monkeypatch.setenv("OPSLENS_TEAM_PASSWORD", "short")
    r = CliRunner().invoke(app, ["serve", "--mode", "team", "--auth", "password", "--allow-host", "h"])
    assert r.exit_code == 2 and "at least 12 characters" in " ".join(r.output.split())
    r = CliRunner().invoke(app, ["serve", "--host", "0.0.0.0"])  # local mode still refuses, and points at team mode
    assert r.exit_code == 2 and "--mode team" in " ".join(r.output.split())
    r = CliRunner().invoke(app, ["serve", "--auth", "password"])
    assert r.exit_code == 2 and "only applies to --mode team" in " ".join(r.output.split())
