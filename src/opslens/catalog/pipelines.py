"""The pipeline catalog: every Flowpipe library pipeline opslens can compose, with its typed interface.

Built offline by scripts/build_pipeline_catalog.py using Flowpipe's own parser (so params, types, enums and outputs
are what Flowpipe will actually enforce). Each pipeline carries a risk class: "read" (only reads) or "write"
(changes state somewhere). The validator uses it to require an approval gate before a write step runs.
"""

from __future__ import annotations

import difflib
import gzip
import json
import re
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

from .tables import STOPWORDS, SYNONYMS, stem, tokens

# words that mean "I want to change something" -> prefer write pipelines when searching
WRITE_WORDS = {"create", "open", "file", "raise", "post", "send", "notify", "page", "delete", "remove", "update",
               "tag", "transition", "close", "resolve", "assign", "add", "snapshot", "stop", "start", "terminate",
               "comment", "alert", "message"}
# pipeline-name token aliases: how people say it -> how mods name it
VERBS = {"open": ["create"], "raise": ["create"], "file": ["create"], "page": ["create", "alert"],
         "notify": ["post", "send", "message"], "post": ["post", "send", "message"], "send": ["send", "post", "message"],
         "ticket": ["issue"], "close": ["close", "resolve"], "tag": ["tag"]}


READ_WORDS = {"list", "get", "describe", "search", "find", "lookup", "check", "count", "show", "read", "fetch", "query"}
DESTRUCTIVE = {"delete", "remove", "terminate", "detach", "disassociate", "revoke", "drop", "purge", "reopen"}


def short_type(t: str, n: int = 28) -> str:
    """list(object({ title = string ... })) -> a one-line, bounded form for tables."""
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def first_sentence(text: str, n: int = 150) -> str:
    s = re.split(r"(?<=[.!?])\s", (text or "").strip(), maxsplit=1)[0]
    return s if len(s) <= n else s[: n - 1] + "…"


NOTIFY_MODS = {"slack", "teams", "jira", "opsgenie", "gitlab", "clickup"}
# additive, non-destructive writes: creating a ticket / alert / message / comment. Everything else that writes is a change.
NOTIFY_NAME = re.compile(r"^(create|post|send|add|reply)_.*(issue|alert|incident|message|comment|task)(?!.*(user|group|member))")


def effect_of(mod: str, short: str, risk: str) -> str:
    """read | notify | change. Only `change` must sit behind an approval gate."""
    if risk == "read":
        return "read"
    return "notify" if mod in NOTIFY_MODS and NOTIFY_NAME.match(short) else "change"


@dataclass
class Param:
    name: str
    type: str
    description: str = ""
    optional: bool = False
    default: Any = None
    enum: list[Any] | None = None

    @property
    def required(self) -> bool:
        return not self.optional


@dataclass
class Pipeline:
    name: str  # fully qualified: jira.pipeline.create_issue
    mod: str
    short: str
    title: str
    description: str
    params: list[Param]
    outputs: list[dict[str, str]]
    steps: list[dict[str, str]]
    risk: str
    tags: dict[str, str] = field(default_factory=dict)
    folder: str = ""

    @property
    def effect(self) -> str:
        return effect_of(self.mod, self.short, self.risk)

    @property
    def recommended(self) -> bool:
        return self.tags.get("recommended") == "true"

    def required_params(self) -> list[Param]:
        return [p for p in self.params if p.required]


class PipelineCatalog:
    def __init__(self, raw: dict[str, Any]):
        self.mods: dict[str, str] = raw["mods"]
        self.pipelines: dict[str, Pipeline] = {}
        for name, p in raw["pipelines"].items():
            self.pipelines[name] = Pipeline(
                name=name, mod=p["mod"], short=p["short"], title=p["title"], description=p["description"],
                params=[Param(x["name"], x["type"], x.get("description", ""), x.get("optional", False),
                              x.get("default"), x.get("enum")) for x in p["params"]],
                outputs=p["outputs"], steps=p["steps"], risk=p["risk"], tags=p.get("tags", {}), folder=p.get("folder", ""))
        self._index = {n: (set(tokens(p.short)), {p.mod} | set(tokens(p.mod)),
                           set(tokens(f"{p.title} {p.description}")) - STOPWORDS,
                           {t for x in p.params for t in tokens(x.name)}) for n, p in self.pipelines.items()}

    def get(self, name: str) -> Pipeline | None:
        """Accepts jira.pipeline.create_issue, jira.create_issue, or (if unambiguous) create_issue."""
        n = (name or "").strip()
        if n in self.pipelines:
            return self.pipelines[n]
        if n.count(".") == 1 and "pipeline." not in n:
            mod, _, short = n.partition(".")
            return self.pipelines.get(f"{mod}.pipeline.{short}")
        hits = [p for p in self.pipelines.values() if p.short == n]
        return hits[0] if len(hits) == 1 else None

    def similar(self, name: str, n: int = 5) -> list[str]:
        short = {p.short: p.name for p in self.pipelines.values()}
        pool = list(self.pipelines) + list(short)
        return [short.get(m, m) for m in difflib.get_close_matches(name.lower(), pool, n=n, cutoff=0.6)]

    def find(self, text: str, k: int = 8, mods: set[str] | None = None, risk: str | None = None) -> list[dict[str, Any]]:
        words = [w for w in tokens(text) if w not in STOPWORDS - WRITE_WORDS]
        query: dict[str, float] = {}
        for w in words:
            query[w] = max(query.get(w, 0), 1.0)
            for s in SYNONYMS.get(w, []) + VERBS.get(w, []):
                query[stem(s)] = max(query.get(stem(s), 0), 0.7)
        wants_write = any(w in WRITE_WORDS for w in words)
        intent = {stem(v) for w in words if w in WRITE_WORDS | READ_WORDS for v in [w, *VERBS.get(w, [])]}
        mentioned_destructive = bool(intent & DESTRUCTIVE)
        scored = []
        for name, (ntok, mod, desc, params) in self._index.items():
            p = self.pipelines[name]
            if (mods and p.mod not in mods) or (risk and p.risk != risk):
                continue
            score, why = 0.0, []
            for w, wt in query.items():
                if w in ntok:
                    score += 6 * wt
                    why.append(w)
                elif w in mod:
                    score += 8 * wt if wt == 1.0 else 3 * wt  # a mod named outright (jira, teams) beats loose matches
                elif w in desc:
                    score += 1.5 * wt
                elif w in params:
                    score += 0.5 * wt
            if score <= 0:
                continue
            verb = p.short.split("_", 1)[0]
            if verb in intent:
                score += 6  # the pipeline's verb is the verb the user used (post -> post_*, create -> create_*)
            elif verb in DESTRUCTIVE and not mentioned_destructive:
                score -= 5  # never lead with delete/remove/detach unless the user asked for it
            if p.recommended:
                score += 1.0
            if wants_write and p.risk == "write":
                score += 1.0
            if p.mod in ("aws_thrifty", "aws_tags") and not any(w in query for w in ("thrifty", "tags", "tag", "detect", "correct")):
                score -= 3  # big detect-and-correct families: offer on request, not as the default answer
            score -= 0.1 * max(len(ntok) - 3, 0)
            scored.append((score, name, why))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [self.brief(n, why) for _, n, why in scored[:k]]

    def brief(self, name: str, why: list[str] | None = None) -> dict[str, Any]:
        p = self.pipelines[name]
        out: dict[str, Any] = {"pipeline": p.name, "mod": p.mod, "risk": p.risk, "title": p.title,
                               "description": first_sentence(p.description or p.title),
                               "requires": [f"{x.name}:{short_type(x.type)}" for x in p.required_params()
                                            if not x.type.startswith("connection.")]}
        if why:
            out["matched"] = sorted(set(why))
        return out

    def describe(self, name: str) -> dict[str, Any]:
        p = self.pipelines[name]
        return {
            "pipeline": p.name, "mod": p.mod, "title": p.title, "description": p.description, "risk": p.risk,
            "effect": p.effect,
            "params": [{"name": x.name, "type": x.type, "required": x.required,
                        **({"description": x.description} if x.description else {}),
                        **({"default": x.default} if x.default is not None else {}),
                        **({"enum": x.enum} if x.enum else {})} for x in p.params],
            "outputs": p.outputs, "steps": [f"{s['type']}.{s['name']}" + (f" ({s['method'].upper()})" if s.get("method") else "")
                                            for s in p.steps],
            "usage": usage(p),
        }

    def stats(self) -> list[dict[str, Any]]:
        rows = []
        for m, v in sorted(self.mods.items()):
            ps = [p for p in self.pipelines.values() if p.mod == m]
            rows.append({"mod": m, "version": v, "pipelines": len(ps), "read": sum(p.risk == "read" for p in ps),
                         "write": sum(p.risk == "write" for p in ps)})
        return rows


def usage(p: Pipeline) -> str:
    """The Flowpipe step that calls this pipeline, with required params as placeholders."""
    args = [f"    {x.name} = <{x.type}>" for x in p.required_params() if not x.type.startswith("connection.")]
    body = "\n".join(["  args = {", *args, "  }"]) if args else ""
    label = p.short
    return f'step "pipeline" "{label}" {{\n  pipeline = {p.mod}.pipeline.{p.short}\n{body}\n}}'.replace("\n\n}", "\n}")


@cache
def load() -> PipelineCatalog:
    data = resources.files("opslens.catalog").joinpath("data", "pipelines.json.gz").read_bytes()
    return PipelineCatalog(json.loads(gzip.decompress(data)))
