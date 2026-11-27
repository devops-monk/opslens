"""The table catalog: every table the shipped Steampipe plugins offer, so nobody (human or model) has to guess.

Built offline from plugin source by scripts/build_table_catalog.py into data/tables_<plugin>.json.gz: per table the
plugin, description, columns (type + description), required filters, optional fast filters (pushed down to the API)
and examples. `with_live()` merges an installed plugin's real column list (information_schema, no API calls): the
live list decides which columns exist; the catalog adds descriptions, filters and examples.

Search is deterministic keyword + synonym ranking (no embeddings, no AI). Adapted from spendlens (Apache-2.0).
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

PG_TYPES = {"STRING": "text", "INT": "bigint", "DOUBLE": "double precision", "BOOL": "boolean", "JSON": "jsonb",
            "TIMESTAMP": "timestamptz", "IPADDR": "inet", "CIDR": "cidr", "INET": "inet", "LTREE": "ltree",
            "DATETIME": "timestamptz", "UNKNOWN": "text"}

HELPER_COLUMNS = {"sp_connection_name", "sp_ctx", "_ctx"}  # injected by Steampipe; older plugins lack them

STOPWORDS = {"a", "an", "and", "any", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "get", "give",
             "has", "have", "how", "i", "in", "is", "it", "its", "list", "me", "my", "of", "on", "or", "our", "show",
             "that", "the", "their", "there", "these", "this", "those", "to", "us", "was", "we", "what", "when",
             "where", "which", "who", "why", "with", "all", "many", "much", "per", "find", "tell", "see", "about",
             "each", "into", "than", "then", "them", "they", "your", "you", "every", "open", "create", "send", "post",
             "notify", "ticket", "if", "after", "before", "over", "older", "newer", "days", "day", "week", "month"}

# question words -> table/pipeline name tokens (plural/singular are handled by _stem)
SYNONYMS: dict[str, list[str]] = {
    # AWS compute / storage / data
    "volume": ["ebs"], "disk": ["ebs", "volume"], "snapshot": ["snapshot"], "bucket": ["s3"], "object": ["s3"],
    "instance": ["ec2", "instance"], "server": ["ec2", "instance"], "vm": ["ec2", "instance"],
    "machine": ["ec2", "instance"], "database": ["rds", "dynamodb"], "db": ["rds"], "postgres": ["rds"],
    "mysql": ["rds"], "aurora": ["rds"], "function": ["lambda"], "serverless": ["lambda"],
    "container": ["ecs", "eks"], "kubernetes": ["eks"], "k8s": ["eks"], "balancer": ["lb", "elb", "load"],
    "loadbalancer": ["lb", "elb"], "alb": ["application", "lb"], "nlb": ["network", "lb"], "ip": ["eip", "ip"],
    "elastic": ["eip"], "firewall": ["security", "group"], "sg": ["security", "group"], "port": ["security", "group"],
    "user": ["iam", "user"], "role": ["iam", "role"], "policy": ["iam", "policy"], "mfa": ["iam", "mfa"],
    "key": ["kms", "key", "access"], "secret": ["secretsmanager"], "certificate": ["acm"], "cert": ["acm"],
    "dns": ["route53"], "domain": ["route53"], "cdn": ["cloudfront"], "queue": ["sqs"], "topic": ["sns"],
    "log": ["cloudwatch", "log"], "alarm": ["cloudwatch"], "cpu": ["cpu", "utilization", "metric"],
    "trail": ["cloudtrail"], "audit": ["cloudtrail"], "cost": ["cost"], "spend": ["cost"], "billing": ["cost"],
    "budget": ["budgets"], "savings": ["savingsplans", "costoptimizationhub"], "tag": ["tags", "tagging"],
    "untagged": ["tags", "tagging"], "cache": ["elasticache"], "redis": ["elasticache"], "network": ["vpc"],
    "subnet": ["vpc", "subnet"], "nat": ["nat", "gateway"], "image": ["ami", "ecr"], "registry": ["ecr"],
    "unattached": ["ebs", "volume"], "unused": ["unused"], "vulnerability": ["inspector2", "finding"],
    "threat": ["guardduty", "finding"], "finding": ["securityhub", "guardduty", "inspector2"],
    "compliance": ["config"], "backup": ["backup"], "encrypted": ["encryption", "encrypted"], "public": ["public"],
    # Jira
    "issue": ["issue", "jira"], "bug": ["issue", "jira"], "task": ["issue", "task"], "sprint": ["sprint"],
    "epic": ["epic", "issue"], "board": ["board"], "backlog": ["backlog", "issue"], "jql": ["issue", "jira"],
    # GitLab
    "mr": ["merge", "request"], "merge": ["merge", "request"], "pr": ["merge", "request"], "repo": ["project"],
    "repository": ["project", "repository"], "deploy": ["deployment"], "deployment": ["deployment"],
    "release": ["deployment"], "pipeline": ["pipeline"], "ci": ["pipeline", "job"], "commit": ["commit"],
    "branch": ["branch"], "gitlab": ["gitlab"],
    # Opsgenie / incidents
    "alert": ["alert", "opsgenie"], "oncall": ["team", "alert"], "incident": ["alert", "incident"],
    "page": ["alert"], "opsgenie": ["opsgenie"],
    # Microsoft 365 / Teams
    "teams": ["team", "microsoft365"], "channel": ["team"], "mailbox": ["mail", "message"], "email": ["mail"],
    "mail": ["mail", "message"], "calendar": ["calendar"], "sharepoint": ["site"], "onedrive": ["drive"],
    "microsoft": ["microsoft365"], "m365": ["microsoft365"], "entra": ["user", "group"],
}

CLOUDTRAIL_NOTES = {
    "aws_cloudtrail_lookup_event": (
        "CloudTrail LookupEvents: management events of the last 90 days, no setup needed. ALWAYS set "
        "start_time = <from> AND end_time = <to> (both '=': they are sent to the API; a filter on event_time is not, "
        "and AWS would page through 90 days at 2 calls/second). Add one of event_name, resource_name, username, "
        "event_source, resource_type or read_only with '=' to narrow it. No data events (S3 object reads/writes)."),
    "aws_cloudtrail_trail_event": (
        "The trail's CloudWatch Logs log group: longer history, error codes, source IPs. Needs log_group_name (read it "
        "from aws_cloudtrail_trail.log_group_arn) and a timestamp range, e.g. timestamp >= now() - interval '24 hours'."),
}
ACTIVITY = re.compile(r"\b(who|whom|whose|cloudtrail|audit|activity|api calls?|log ?ins?|logged in|sign ?ins?|"
                      r"deleted?|deleting|deletion|removed|terminated|modified|changed|updated|attached|detached|"
                      r"assumed)\b", re.IGNORECASE)
EVENT_TABLES = ("aws_cloudtrail_lookup_event", "aws_cloudtrail_trail_event")


def stem(word: str) -> str:
    """Plural to singular: policies->policy, addresses->address, boxes->box, instances->instance."""
    w = word.lower()
    if len(w) <= 3 or not w.endswith("s") or w.endswith(("ss", "us", "is")):
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("sses", "ches", "shes", "xes", "zes")):
        return w[:-2]
    return w[:-1]


def first_sentence(text: str, n: int = 150) -> str:
    s = re.split(r"(?<=[.!?])\s", (text or "").strip(), maxsplit=1)[0]
    return s if len(s) <= n else s[: n - 1] + "…"


def tokens(text: str) -> list[str]:
    return [stem(t) for t in re.split(r"[^a-zA-Z0-9]+", text or "") if t]


@dataclass
class Column:
    name: str
    type: str
    description: str = ""

    @property
    def pg_type(self) -> str:
        return PG_TYPES.get(self.type, "text")


@dataclass
class Table:
    name: str
    plugin: str
    service: str
    description: str
    summary: str
    guide: str
    columns: dict[str, Column]
    required: list[str]
    any_of: list[str]
    filters: dict[str, list[str]]
    get_keys: list[str]
    examples: list[dict[str, str]]
    cost_explorer: bool = False
    time_series: bool = False
    live: bool = False  # column list confirmed by the installed plugin
    missing_live: list[str] = field(default_factory=list)  # catalog columns the installed plugin lacks

    def required_text(self) -> str:
        parts = [f"{c} = <value>" for c in self.required]
        if self.any_of:
            parts.append("one of: " + " / ".join(f"{c} = <value>" for c in self.any_of))
        return " AND ".join(parts)


class TableCatalog:
    def __init__(self, raws: list[dict[str, Any]]):
        self.plugins: dict[str, str] = {}  # plugin -> version
        self.tables: dict[str, Table] = {}
        for raw in raws:
            plugin = raw["plugin"]
            self.plugins[plugin] = raw.get("version", "")
            for name, t in raw["tables"].items():
                self.tables[name] = Table(
                    name=name, plugin=plugin, service=t["service"], description=t["description"], summary=t["summary"],
                    guide=t["guide"], columns={c[0]: Column(*c) for c in t["columns"]}, required=t["required"],
                    any_of=t["any_of"], filters=t["filters"], get_keys=t["get_keys"], examples=t["examples"],
                    cost_explorer=t["cost_explorer"], time_series=t["time_series"])
        self._index = {n: self._index_of(t) for n, t in self.tables.items()}

    @staticmethod
    def _index_of(t: Table) -> tuple[set[str], set[str], set[str], set[str]]:
        short = t.name[len(t.plugin) + 1:] if t.name.startswith(t.plugin + "_") else t.name
        return (set(tokens(short)), set(tokens(t.service)) | {t.plugin},
                set(tokens(f"{t.description} {t.summary} {t.guide}")) - STOPWORDS,
                {p for c in t.columns for p in tokens(c)})

    # ----- lookup

    def get(self, name: str) -> Table | None:
        return self.tables.get((name or "").lower().split(".")[-1].strip('"'))

    def similar(self, name: str, n: int = 5) -> list[str]:
        return difflib.get_close_matches(name.lower(), list(self.tables), n=n, cutoff=0.6)

    def names(self) -> frozenset[str]:
        return frozenset(self.tables)

    def with_live(self, live: dict[str, list[tuple[str, str]]]) -> TableCatalog:
        """A copy where each table's columns are the installed plugin's (live wins; descriptions kept)."""
        new = object.__new__(TableCatalog)
        new.plugins, new._index, new.tables = self.plugins, self._index, dict(self.tables)
        for name, cols in live.items():
            base = self.tables.get(name)
            if base is None:
                continue  # a table the catalog does not know: left out on purpose (it is not allow-listed)
            merged = {c: base.columns.get(c) or Column(c, _from_pg(t)) for c, t in cols}
            new.tables[name] = Table(**{**base.__dict__, "columns": merged, "live": True,
                                        "missing_live": [c for c in base.columns if c not in merged and c not in HELPER_COLUMNS]})
        return new

    # ----- search

    def find(self, text: str, k: int = 8, plugins: set[str] | None = None) -> list[dict[str, Any]]:
        """Tables most likely to answer `text`, best first, with why they matched."""
        words = [w for w in tokens(text) if w not in STOPWORDS]
        exact = [w for w in re.findall(r"[a-z0-9]+_[a-z0-9_]+", text.lower()) if w in self.tables]
        query: dict[str, float] = {}
        for w in words:
            query[w] = max(query.get(w, 0), 1.0)
            for s in SYNONYMS.get(w, []):
                query[stem(s)] = max(query.get(stem(s), 0), 0.7)
        activity = bool(ACTIVITY.search(text))
        wants_metric = any(w in query for w in ("metric", "cpu", "utilization", "memory", "idle"))
        wants_cost = "cost" in query
        scored = []
        for name, (ntok, svc, desc, cols) in self._index.items():
            t = self.tables[name]
            if plugins and t.plugin not in plugins:
                continue
            score, why = 0.0, []
            for w, wt in query.items():
                if w in ntok:
                    score += 6 * wt
                    why.append(w)
                elif w in svc:
                    score += 3 * wt
                elif w in desc:
                    score += 1.5 * wt
                elif w in cols:
                    score += 0.8 * wt
            if name in exact:
                score += 100
            if name in EVENT_TABLES and activity:
                score += 20 if name == EVENT_TABLES[0] else 16
            if score <= 0:
                continue
            extra = sum(1 for x in ntok if x not in query)
            score -= 0.7 * extra  # prefer the general table (jira_issue) over narrow ones (jira_backlog_issue)
            if "metric" in ntok and not wants_metric:
                score -= 4
            if t.cost_explorer and not wants_cost:
                score -= 4
            scored.append((score, name, why))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [self.brief(n, why) for _, n, why in scored[:k]]

    def brief(self, name: str, why: list[str] | None = None) -> dict[str, Any]:
        t = self.tables[name]
        out: dict[str, Any] = {"table": name, "plugin": t.plugin, "service": t.service,
                               "description": first_sentence(t.summary or t.description)}
        if t.required or t.any_of:
            out["required_filters"] = t.required_text()
        if name in CLOUDTRAIL_NOTES:
            out["note"] = CLOUDTRAIL_NOTES[name]
        elif t.cost_explorer:
            out["note"] = "Cost Explorer: about $0.01 per request; always bound period_start/period_end"
        elif t.time_series:
            out["note"] = "time series: filter on a time range"
        if why:
            out["matched"] = sorted(set(why))
        return out

    def describe(self, name: str, *, examples: bool = True) -> dict[str, Any]:
        t = self.tables[name]
        req = set(t.required) | set(t.any_of)
        out: dict[str, Any] = {
            "table": name, "plugin": t.plugin, "service": t.service, "description": t.summary or t.description,
            "columns": [{"name": c.name, "type": c.pg_type,
                         **({"description": c.description[:240]} if c.description else {}),
                         **({"required_filter": True} if c.name in req else {}),
                         **({"fast_filter": t.filters[c.name]} if c.name in t.filters else {})}
                        for c in t.columns.values() if c.name not in ("_ctx", "sp_ctx")],
        }
        if t.required or t.any_of:
            out["required_filters"] = (f"Every query on {name} MUST have WHERE {t.required_text()}. Valid values are "
                                       "in each column's description.")
        if t.filters:
            out["fast_filters"] = ("Filtering on these columns in WHERE is pushed down to the API (faster, fewer "
                                   f"calls): {', '.join(sorted(t.filters))}")
        if t.cost_explorer:
            out["cost_note"] = ("Cost Explorer bills about $0.01 per API request: always filter period_start / "
                                "period_end to the range you need")
        elif t.time_series:
            out["time_note"] = "Time series: always filter on a time range (e.g. timestamp >= now() - interval '7 days')"
        if name in CLOUDTRAIL_NOTES:
            out["note"] = CLOUDTRAIL_NOTES[name]
        if t.get_keys:
            out["lookup_keys"] = t.get_keys
        if examples and t.examples:
            out["examples"] = t.examples
        if t.live:
            out["schema"] = "columns confirmed against the installed plugin"
            if t.missing_live:
                out["missing_in_installed_plugin"] = t.missing_live
        return out

    def stats(self) -> list[dict[str, Any]]:
        rows = []
        for p, v in sorted(self.plugins.items()):
            ts = [t for t in self.tables.values() if t.plugin == p]
            rows.append({"plugin": p, "version": v, "tables": len(ts),
                         "columns": sum(len(t.columns) for t in ts), "examples": sum(len(t.examples) for t in ts)})
        return rows


def _from_pg(pg: str) -> str:
    p = (pg or "").lower()
    return ("JSON" if "json" in p else "BOOL" if p == "boolean" else "INT" if "int" in p else
            "DOUBLE" if p in ("double precision", "real", "numeric") else "TIMESTAMP" if "timestamp" in p else
            "IPADDR" if p == "inet" else "CIDR" if p == "cidr" else "STRING")


@cache
def load() -> TableCatalog:
    root = resources.files("opslens.catalog").joinpath("data")
    raws = [json.loads(gzip.decompress(p.read_bytes())) for p in sorted(root.iterdir(), key=lambda p: p.name)
            if p.name.startswith("tables_") and p.name.endswith(".json.gz")]
    return TableCatalog(raws)
