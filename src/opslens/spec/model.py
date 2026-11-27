"""The mod spec: a small, typed description of one detect-and-act automation.

A spec is what the planner (Phase 3) emits and what packs ship. It is deliberately *not* HCL: the renderer turns a
validated spec into Flowpipe HCL deterministically, so a model never writes `.fp` syntax and whole classes of invalid
or unsafe output cannot exist.

    name: unattached-volume-cleanup
    detect:  {sql: "select volume_id, region from aws_ebs_volume where state = 'available'"}
    actions:
      - pipeline: jira.create_issue
        args: {project_key: "{var.project_key}", issue_type: Task, summary: "Unattached volume {volume_id}"}
      - pipeline: aws.delete_ebs_volume
        args: {volume_id: "{volume_id}", region: "{region}"}
        gated: true

Argument templates: `{column}` is a column of the detect query, `{var.name}` a spec variable. Everything else is a
literal and is escaped when rendered.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")


class _BlockDumper(yaml.SafeDumper):
    """Multi-line strings (the detect SQL) are written as readable `|` blocks, not escaped one-liners."""


def _str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    clean = "\n" in data and data == data.rstrip() + ("\n" if data.endswith("\n") else "") and \
        not any(line != line.rstrip() for line in data.splitlines())
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if clean else None)


_BlockDumper.add_representer(str, _str)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Variable(_Strict):
    default: str | int | float | bool
    description: str = ""


class Trigger(_Strict):
    kind: Literal["manual", "schedule"] = "manual"
    schedule: str = Field("daily", description="hourly | daily | weekly | 15m ... 24h | a cron expression")


class Detect(_Strict):
    sql: str = Field(min_length=7)
    max_items: int = Field(50, ge=1, le=500, description="Hard cap on rows acted on per run.")


class Action(_Strict):
    pipeline: str = Field(description="A catalogued Flowpipe pipeline, e.g. jira.create_issue")
    args: dict[str, str | int | float | bool] = Field(default_factory=dict)
    gated: bool = Field(False, description="Runs only after the approval step. Required for write pipelines.")
    title: str = ""


class Approval(_Strict):
    prompt: str = "Approve the gated actions for these items?"


class Spec(_Strict):
    name: str
    title: str
    description: str = ""
    request: str = Field("", description="The plain-English request this spec answers (kept for the audit trail).")
    variables: dict[str, Variable] = Field(default_factory=dict)
    trigger: Trigger = Field(default_factory=Trigger)
    detect: Detect
    notify: bool = Field(True, description="Post a one-line summary through the notifier when items are found.")
    approval: Approval = Field(default_factory=Approval)
    actions: list[Action] = Field(min_length=1)
    auto_apply: bool = Field(False, description="Allow write actions without approval. Flagged loudly by lint.")

    @field_validator("name")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("must be a lowercase identifier: letters, digits, underscores, starting with a letter")
        return v

    def gated_actions(self) -> list[Action]:
        return [a for a in self.actions if a.gated]

    def to_yaml(self) -> str:
        return yaml.dump(self.model_dump(exclude_defaults=False, mode="json"), Dumper=_BlockDumper, sort_keys=False, width=110)


def load_spec(text: str) -> Spec:
    data: Any = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise TypeError("a spec must be a YAML mapping")
    return Spec.model_validate(data)


def placeholders(value: Any) -> list[str]:
    return PLACEHOLDER.findall(value) if isinstance(value, str) else []
