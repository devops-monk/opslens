"""The planner: plain English -> a validated spec. The model never writes HCL or runs anything.

Flow: retrieve the catalog entries relevant to the requirement (offline search), show them to the model as the ONLY
tables, columns and pipelines it may use, ask for a spec YAML, then run the same validator packs go through. Errors are
fed back for up to `max_attempts` rounds. What comes out is a spec for a human to review, preview and approve:
`auto_apply` is forced off, and nothing is deployed.

Privacy: only the requirement text and public catalog metadata (table/column names, pipeline params) are sent. No cloud
data, no credentials. With llm.redact on, emails, 12-digit account ids, ARNs and key-like strings are scrubbed first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources

import yaml

from ..catalog import pipelines as pcat
from ..catalog import search
from ..catalog import tables as tcat
from ..spec import check
from ..spec.model import Spec, load_spec
from .providers import LLMError, Provider

FENCE = re.compile(r"```(?:ya?ml)?\s*\n(.*?)```", re.DOTALL)
REDACTIONS = [
    (re.compile(r"arn:aws[a-z-]*:[A-Za-z0-9:/_\-.*]+"), "<arn>"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "<aws-key>"),
    (re.compile(r"\b(?:sk|pk|xox[bp]|ghp|glpat)[-_][A-Za-z0-9_\-]{16,}\b"), "<secret>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\b\d{12}\b"), "<account-id>"),
]


def redact(text: str) -> str:
    for rx, rep in REDACTIONS:
        text = rx.sub(rep, text)
    return text


class PlannerError(RuntimeError):
    pass


@dataclass
class Plan:
    spec: Spec
    yaml: str
    issues: list[check.Issue]
    attempts: int
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


def system_prompt() -> str:
    return resources.files("opslens.ai").joinpath("prompt.md").read_text()


def context_for(requirement: str, k: int = 4) -> str:
    """The catalog slice the model may use: candidate tables (with columns) and pipelines (with params)."""
    tc, pc = tcat.load(), pcat.load()
    found = search.find(requirement, k=k)
    out = ["## Tables you may query (Postgres SQL via Steampipe)"]
    for t in found["tables"]:
        tab = tc.get(t["table"])
        cols = ", ".join(f"{c.name} {c.pg_type}" for c in tab.columns.values() if c.name not in tcat.HELPER_COLUMNS)
        req = f"\nREQUIRED filters: {tab.required_text()}" if tab.required or tab.any_of else ""
        out.append(f"### {tab.name}\n{tcat.first_sentence(tab.description, 140)}{req}\ncolumns: {cols}")
    out.append("\n## Pipelines you may call (use the short name, e.g. jira.create_issue)")
    seen: set[str] = set()
    for a in found["actions"]:
        for hit in a["pipelines"]:
            p = pc.get(hit["pipeline"])
            if not p or p.name in seen:
                continue
            seen.add(p.name)
            params = []
            for x in p.params:
                if x.type.startswith("connection.") or x.type == "notifier":
                    continue
                flag = "" if x.optional else " REQUIRED"
                en = f" one of {x.enum}" if x.enum else ""
                params.append(f"  - {x.name}: {x.type}{flag}{en}")
            out.append(f"### {p.mod}.{p.short}  [{p.effect}]\n{tcat.first_sentence(p.description, 140)}\n" + "\n".join(params))
    return "\n".join(out)


def extract_yaml(text: str) -> str:
    m = FENCE.findall(text)
    return (m[-1] if m else text).strip()


def feedback(issues: list[check.Issue]) -> str:
    lines = "\n".join(f"- {i}" for i in issues if i.level == "error")
    return ("The spec failed validation:\n" + lines + "\n\nFix every error and reply with the complete corrected spec in one "
            "```yaml block. Use only the tables, columns and pipelines listed above.")


def plan(requirement: str, provider: Provider, *, max_attempts: int = 3, do_redact: bool = True) -> Plan:
    requirement = requirement.strip()
    if len(requirement) < 8:
        raise PlannerError("describe what you want in a sentence or two")
    sent = redact(requirement) if do_redact else requirement
    messages = [{"role": "user", "content": f"{context_for(sent)}\n\n## Requirement\n{sent}\n\nReply with the spec only."}]
    usage: dict[str, int] = {}
    last_issues: list[check.Issue] = []
    for attempt in range(1, max_attempts + 1):
        try:
            reply = provider.complete(system_prompt(), messages)
        except LLMError as e:
            raise PlannerError(str(e)) from e
        for k, v in reply.usage.items():
            usage[k] = usage.get(k, 0) + v
        if reply.refused:
            raise PlannerError("the model declined this request (safety filter). Reword it, or write the spec by hand.")
        text = extract_yaml(reply.text)
        try:
            spec = load_spec(text)
        except (ValueError, TypeError, yaml.YAMLError) as e:  # yaml / pydantic errors: all become feedback
            last_issues = [check.Issue("error", "spec", f"not a valid spec: {str(e)[:400]}")]
        else:
            spec.auto_apply = False  # the model cannot waive approval
            spec.request = requirement
            last_issues = check.validate(spec)
            if not check.errors(last_issues):
                return Plan(spec, spec.to_yaml(), last_issues, attempt, usage, reply.model or provider.model)
        messages += [{"role": "assistant", "content": reply.text}, {"role": "user", "content": feedback(last_issues)}]
    raise PlannerError(f"no valid spec after {max_attempts} attempts. Last errors:\n"
                       + "\n".join(f"  {i}" for i in last_issues if i.level == "error"))
