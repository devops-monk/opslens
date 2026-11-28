"""opslens-owned credentials for the services it talks to (Jira, Teams, Slack, GitLab, Opsgenie, AWS, ipstack).

Users should not have to know which helper program reads what, or edit the helpers' config files. `opslens connect <service>`
saves the values in one file only the current user can read; opslens then hands them to the programs it starts as environment
variables. Where a value can live, strongest first:

  1. a real environment variable (always wins, e.g. in a container),
  2. the opslens credentials file (`opslens connect`),
  3. `connections:` in opslens.yaml, for non-secret values only (URLs, user names). Secrets are refused there: that file is
     normally committed to git.

Secrets are stored in plain text, protected by file permissions (like ~/.aws/credentials). They are never printed.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STORE_ENV = "OPSLENS_CONNECTIONS_FILE"


@dataclass(frozen=True)
class Field:
    key: str
    prompt: str
    env: tuple[str, ...]            # environment variables the underlying programs read
    secret: bool = False
    required: bool = True
    default: str | None = None


@dataclass(frozen=True)
class Service:
    label: str
    fields: tuple[Field, ...]
    read_check: str | None = None   # a one-row query that proves the read side works (None: no table to read)
    note: str = ""
    extra_check: Any = None         # callable(values) -> problem text or None


def _aws_check(v: dict[str, str]) -> str | None:
    if v.get("profile") or (v.get("access_key_id") and v.get("secret_access_key")):
        return None
    return "give a profile, or both an access key id and a secret access key"


SERVICES: dict[str, Service] = {
    "jira": Service("Jira", (
        Field("url", "Jira URL, e.g. https://your-domain.atlassian.net/", ("JIRA_URL",)),
        Field("user", "Account email", ("JIRA_USER",)),
        Field("token", "API token (Atlassian account, security, API tokens)", ("JIRA_TOKEN", "JIRA_API_TOKEN"), secret=True),
    ), read_check="select key from jira_issue limit 1"),
    "teams": Service("Microsoft Teams", (
        Field("access_token", "Microsoft Graph access token for posting (expires in about an hour)", ("TEAMS_ACCESS_TOKEN",),
              secret=True),
        Field("tenant_id", "Tenant id (to look up teams and users; optional)", ("AZURE_TENANT_ID",), required=False),
        Field("client_id", "App client id (optional)", ("AZURE_CLIENT_ID",), required=False),
        Field("client_secret", "App client secret (optional)", ("AZURE_CLIENT_SECRET",), secret=True, required=False),
    ), read_check="select id from microsoft365_team limit 1",
        note="The read check needs the tenant, client id and client secret."),
    "slack": Service("Slack", (
        Field("token", "Bot token (xoxb-...) with chat:write", ("SLACK_TOKEN",), secret=True),
    ), note="Posting only: there is nothing to read, so `connections --test` skips it."),
    "gitlab": Service("GitLab", (
        Field("token", "Personal access token (read_api; api to change things)", ("GITLAB_TOKEN",), secret=True),
        Field("url", "API URL for self-managed GitLab, e.g. https://gitlab.company.com/api/v4 (leave empty for gitlab.com)",
              ("GITLAB_ADDR",), required=False),
    ), read_check="select id from gitlab_project limit 1"),
    "opsgenie": Service("Opsgenie", (
        Field("token", "API key", ("OPSGENIE_TOKEN", "OPSGENIE_ALERT_API_KEY"), secret=True),
        Field("url", "API host (api.eu.opsgenie.com for an EU account)", ("OPSGENIE_URL",), required=False,
              default="api.opsgenie.com"),
        Field("incident_api_key", "Incident API key (optional)", ("OPSGENIE_INCIDENT_API_KEY",), secret=True, required=False),
    ), read_check="select id from opsgenie_alert limit 1"),
    "aws": Service("AWS", (
        Field("profile", "Profile name (or leave empty and give keys)", ("AWS_PROFILE",), required=False),
        Field("access_key_id", "Access key id", ("AWS_ACCESS_KEY_ID",), required=False),
        Field("secret_access_key", "Secret access key", ("AWS_SECRET_ACCESS_KEY",), secret=True, required=False),
        Field("session_token", "Session token (temporary credentials only)", ("AWS_SESSION_TOKEN",), secret=True, required=False),
        Field("region", "Default region (optional)", ("AWS_REGION",), required=False),
    ), read_check="select instance_id from aws_ec2_instance limit 1", extra_check=_aws_check,
        note="Actions on AWS (stop, delete, tag) also need a running Docker daemon."),
    "ipstack": Service("ipstack", (
        Field("access_key", "ipstack access key", ("IPSTACK_ACCESS_KEY",), secret=True),
    ), note="Look-ups only; there is nothing to read."),
}

_YAML: dict[str, dict[str, str]] = {}   # non-secret values from opslens.yaml, set by activate()


class ConnectionError_(ValueError):
    pass


# ------------------------------------------------------------------ the credentials file
def store_path() -> Path:
    explicit = os.environ.get(STORE_ENV)
    return Path(explicit).expanduser() if explicit else Path.home() / ".config" / "opslens" / "connections.json"


def load_store() -> dict[str, dict[str, str]]:
    p = store_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise ConnectionError_(f"{p} is not readable JSON ({e}); fix or remove it") from e
    return {k: {f: str(v) for f, v in vals.items()} for k, vals in data.items() if isinstance(vals, dict)}


def _write_store(data: dict[str, dict[str, str]]) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".connections-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def service(name: str) -> Service:
    try:
        return SERVICES[name]
    except KeyError:
        raise ConnectionError_(f"unknown service '{name}'; choose one of: {', '.join(SERVICES)}") from None


def save(name: str, values: dict[str, str]) -> Path:
    svc = service(name)
    known = {f.key for f in svc.fields}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ConnectionError_(f"{name} has no field(s) {', '.join(unknown)}; its fields are {', '.join(sorted(known))}")
    values = {k: v for k, v in values.items() if v != ""}
    for f in svc.fields:
        if f.default and f.key not in values:
            values[f.key] = f.default
    missing = [f.key for f in svc.fields if f.required and not values.get(f.key)]
    if missing:
        raise ConnectionError_(f"{name} needs: {', '.join(missing)}")
    if svc.extra_check and (problem := svc.extra_check(values)):
        raise ConnectionError_(f"{name}: {problem}")
    data = load_store()
    data[name] = values
    _write_store(data)
    return store_path()


def remove(name: str) -> bool:
    service(name)
    data = load_store()
    if name not in data:
        return False
    del data[name]
    _write_store(data)
    return True


# ------------------------------------------------------------------ opslens.yaml (non-secret values only)
def validate_yaml(conns: dict[str, dict[str, Any]]) -> None:
    for name, vals in conns.items():
        svc = service(name)
        by_key = {f.key: f for f in svc.fields}
        for key in vals:
            if key not in by_key:
                raise ConnectionError_(f"connections.{name}.{key}: unknown field; {name} has {', '.join(by_key)}")
            if by_key[key].secret:
                raise ConnectionError_(
                    f"connections.{name}.{key} is a secret and must not be written in opslens.yaml (it is usually committed to "
                    f"git). Run `opslens connect {name}` instead, or set the environment variable {by_key[key].env[0]}")


def activate(conns: dict[str, dict[str, Any]] | None) -> None:
    """Remember the non-secret values from opslens.yaml so child programs get them."""
    _YAML.clear()
    for name, vals in (conns or {}).items():
        _YAML[name] = {k: str(v) for k, v in vals.items()}


# ------------------------------------------------------------------ resolving
def _resolved(name: str) -> dict[str, tuple[str, str]]:
    """field -> (value, source) with the winning source: env, store or yaml."""
    svc, stored, out = service(name), load_store().get(name, {}), {}
    for f in svc.fields:
        env_hit = next((e for e in f.env if os.environ.get(e)), None)
        if env_hit:
            out[f.key] = (os.environ[env_hit], f"env {env_hit}")
        elif f.key in stored:
            out[f.key] = (stored[f.key], "opslens connect")
        elif f.key in _YAML.get(name, {}):
            out[f.key] = (_YAML[name][f.key], "opslens.yaml")
    return out


def child_env() -> dict[str, str]:
    """The environment for the programs opslens starts: the real environment plus every stored or yaml value."""
    env = dict(os.environ)
    for name, svc in SERVICES.items():
        for key, (value, _source) in _resolved(name).items():
            for var in next(f for f in svc.fields if f.key == key).env:
                env.setdefault(var, value)
    return env


@dataclass
class Status:
    name: str
    label: str
    state: str                       # connected | partial | not set
    sources: dict[str, str] = field(default_factory=dict)   # field -> where it comes from (never the value)
    missing: list[str] = field(default_factory=list)


def status() -> list[Status]:
    out = []
    for name, svc in SERVICES.items():
        have = _resolved(name)
        values = {k: v for k, (v, _) in have.items()}
        missing = [f.key for f in svc.fields if f.required and f.key not in values]
        if svc.extra_check and svc.extra_check(values):
            missing = missing or ["profile or keys"]
        state = "not set" if not have else ("connected" if not missing else "partial")
        out.append(Status(name, svc.label, state, {k: s for k, (_, s) in have.items()}, missing))
    return out
