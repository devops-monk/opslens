"""opslens.yaml schema, loader and parameter overrides.

Settings are resolved in layers, later layers win:

  1. built-in defaults
  2. config file: --config PATH | $OPSLENS_CONFIG | ./opslens.yaml | ~/.config/opslens/opslens.yaml
  3. environment:  OPSLENS__STEAMPIPE__PORT=9193      (double underscore = nesting)
  4. command line: --set steampipe.port=9193          (repeatable)

Values from env/--set are parsed as YAML, so lists work: --set 'catalog.plugins=[aws, jira]'.
Every layer is validated: unknown keys and wrong types fail fast, naming the key and the layer.
`opslens params` lists each parameter with its value, source and env-var name.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CONFIG_ENV = "OPSLENS_CONFIG"
ENV_PREFIX = "OPSLENS__"


class ConfigError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SteampipeConfig(_Strict):
    """Where read-only SQL runs. Default: the local Steampipe service (started on demand by `opslens`)."""
    host: str = "localhost"
    port: int = Field(9193, ge=1, le=65535)
    database: str = "steampipe"
    user: str = "steampipe"
    password: str | None = Field(None, description="Leave empty to read it from `steampipe service status`.")
    dsn: str | None = Field(None, description="Full connection string; overrides host/port/database/user/password.")
    statement_timeout_s: int = Field(60, ge=1, le=3600)
    max_rows: int = Field(1000, ge=1, le=1_000_000)
    auto_start: bool = Field(True, description="Start the data service when a live query needs it and it is not running.")


class FlowpipeConfig(_Strict):
    """The Flowpipe server opslens deploys to and runs pipelines on (Phase 2)."""
    url: str = "http://localhost:7103"
    binary: str = "flowpipe"
    workspace_dir: str = "generated"


class CatalogConfig(_Strict):
    plugins: list[str] | None = Field(None, description="Limit search to these plugins (default: all shipped).")
    default_results: int = Field(8, ge=1, le=100)


class LLMConfig(_Strict):
    """Phase 3: provider-agnostic planner. Everything works without it."""
    provider: Literal["none", "anthropic", "openai", "openai_compatible", "glm", "openrouter", "ollama", "litellm",
                      "azure", "bedrock"] = "none"
    model: str | None = Field(None, description="Model name. Defaults to claude-opus-5-5 for anthropic; required elsewhere.")
    base_url: str | None = Field(None, description="Endpoint for openai_compatible (and to override a preset).")
    api_key_env: str | None = Field(None, description="Name of the env var holding the API key (keys never go in config).")
    effort: Literal["low", "medium", "high", "xhigh", "max"] = Field("high", description="Anthropic thinking effort.")
    fallback: bool = Field(True, description="Anthropic: retry on a fallback model if safety classifiers decline.")
    max_attempts: int = Field(3, ge=1, le=6, description="Planner tries, feeding validation errors back each time.")
    redact: bool = True


class Config(_Strict):
    steampipe: SteampipeConfig = Field(default_factory=SteampipeConfig)
    flowpipe: FlowpipeConfig = Field(default_factory=FlowpipeConfig)
    catalog: CatalogConfig = Field(default_factory=CatalogConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    connections: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="Non-secret connection details (URLs, user names). Secrets: `opslens connect`.")

    @field_validator("connections")
    @classmethod
    def _no_secrets(cls, v: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        from .connections import ConnectionError_, validate_yaml

        try:
            validate_yaml(v)
        except ConnectionError_ as e:
            raise ValueError(str(e)) from e
        return v


# ------------------------------------------------------------------ layering


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _nest(path: str, value: Any) -> dict[str, Any]:
    out: Any = value
    for part in reversed(path.split(".")):
        out = {part: out}
    return out


def parse_set(items: list[str] | None) -> list[tuple[str, Any]]:
    out = []
    for item in items or []:
        key, sep, raw = item.partition("=")
        if not sep or not key.strip():
            raise ConfigError(f"--set expects key=value, got '{item}'")
        out.append((key.strip(), yaml.safe_load(raw)))
    return out


def config_path(explicit: str | None) -> Path | None:
    for cand in (explicit, os.environ.get(CONFIG_ENV), "opslens.yaml",
                 str(Path.home() / ".config" / "opslens" / "opslens.yaml")):
        if cand and Path(cand).expanduser().is_file():
            return Path(cand).expanduser()
    if explicit or os.environ.get(CONFIG_ENV):
        raise ConfigError(f"config file not found: {explicit or os.environ[CONFIG_ENV]}")
    return None


def _validate(data: dict[str, Any], layer: str) -> None:
    try:
        Config.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        raise ConfigError(f"{layer}: {'.'.join(str(x) for x in first['loc'])}: {first['msg']}") from e


def load_config(path: str | None = None, sets: list[str] | None = None) -> tuple[Config, dict[str, str]]:
    """Resolve the layers. Returns the config and a map of dotted key -> source layer for non-default values."""
    data: dict[str, Any] = {}
    source: dict[str, str] = {}

    def apply(layer_data: dict[str, Any], layer: str) -> None:
        nonlocal data
        _validate(_merge(data, layer_data), layer)
        data = _merge(data, layer_data)
        for k in flatten(layer_data):
            source[k] = layer

    p = config_path(path)
    if p:
        try:
            file_data = yaml.safe_load(p.read_text()) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{p}: invalid YAML: {e}") from e
        if not isinstance(file_data, dict):
            raise ConfigError(f"{p}: expected a mapping at the top level")
        file_data = {k: v for k, v in file_data.items() if v is not None}  # `section:` with nothing under it
        apply(file_data, f"file {p}")
    for name, raw in os.environ.items():
        if name.startswith(ENV_PREFIX):
            key = ".".join(part.lower() for part in name[len(ENV_PREFIX):].split("__"))
            apply(_nest(key, yaml.safe_load(raw)), f"env {name}")
    for key, value in parse_set(sets):
        apply(_nest(key, value), "--set")
    return Config.model_validate(data), source


def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def param_rows(cfg: Config, source: dict[str, str]) -> list[dict[str, Any]]:
    """Every parameter: key, value, source, env var, description."""
    rows = []
    flat = flatten(cfg.model_dump())
    for section_name, section in (("steampipe", SteampipeConfig), ("flowpipe", FlowpipeConfig),
                                  ("catalog", CatalogConfig), ("llm", LLMConfig)):
        for fname, finfo in section.model_fields.items():
            key = f"{section_name}.{fname}"
            val = flat[key]
            if fname == "password" and val:
                val = "***"
            rows.append({"key": key, "value": val, "source": source.get(key, "default"),
                         "env": f"{ENV_PREFIX}{section_name.upper()}__{fname.upper()}",
                         "description": finfo.description or ""})
    return rows


def template_text() -> str:
    return """# opslens configuration. Every key is optional; defaults shown. See `opslens params` for the full list.
steampipe:
  host: localhost
  port: 9193
  database: steampipe
  user: steampipe
  # password: leave empty: opslens reads it from `steampipe service status`
  statement_timeout_s: 60     # every query is cancelled after this long
  max_rows: 1000              # and capped at this many rows

flowpipe:
  url: http://localhost:7103
  workspace_dir: generated    # where generated mods are written (a git repo is recommended)

# connections:                  # non-secret details only; secrets go through `opslens connect <service>`
#   jira: {url: "https://your-domain.atlassian.net/", user: you@company.com}
#   gitlab: {url: "https://gitlab.company.com/api/v4"}

# catalog:
#   plugins: [aws, jira, gitlab, opsgenie, microsoft365]   # limit searches to these plugins

llm:
  provider: none              # none | anthropic | openai | openai_compatible | glm | openrouter | ollama | litellm
  # model: claude-opus-5-5    # required for every provider except anthropic
  # base_url: http://localhost:8000/v1   # openai_compatible
  # api_key_env: MY_KEY_VAR   # env var holding the key (keys never go in this file)
  redact: true                # scrub emails, account ids, ARNs, key-like strings from the requirement before sending
"""
