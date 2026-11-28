#!/usr/bin/env python3
# ruff: noqa: ISC004  (page text is written as adjacent string literals inside lists)
"""Build the static site (website/ -> website/dist/).

    python scripts/build_site.py            # build
    python scripts/build_site.py --check    # build, then verify every internal link and asset resolves

The explorer's data (data/*.json) is exported from the shipped catalogs, and the Templates, CLI and Catalogs pages are
generated from the code, so the site never drifts from what you install.
Docs = website/content/docs/*.md  +  docs/safety.md  +  CHANGELOG.md  +  the three generated pages.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import markdown
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from opslens import __version__
from opslens.catalog import pipelines as pcat
from opslens.catalog import tables as tcat

SITE = ROOT / "website"
DIST = SITE / "dist"
SITE_URL = "https://opslens.devops-monk.com"
REPO_URL = "https://github.com/devops-monk/opslens"

# ---------------------------------------------------------------- icons (24x24 monoline, currentColor)
_G = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "book": '<path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 5v16M8 7h7"/>',
    "play": '<circle cx="12" cy="12" r="9"/><path d="M10 8.5l5 3.5-5 3.5z"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 5.2a3.2 3.2 0 010 5.6M18 14.3c1.8.7 3 2.4 3 4.7"/>',
    "box": '<path d="M3 7.5L12 3l9 4.5v9L12 21l-9-4.5zM3 7.5l9 4.5 9-4.5M12 12v9"/>',
    "sliders": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4"/>',
    "layout": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18M9 9v11"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="2"/><rect x="13" y="4" width="7" height="7" rx="2"/><rect x="4" y="13" width="7" height="7" rx="2"/><rect x="13" y="13" width="7" height="7" rx="2"/>',
    "puzzle": '<path d="M10 4a2 2 0 014 0v2h4v4h-2a2 2 0 000 4h2v4h-4v-2a2 2 0 00-4 0v2H6v-4h2a2 2 0 000-4H6V6h4z"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/>',
    "flask": '<path d="M9 3h6M10 3v6L4.5 18.5A1.7 1.7 0 006 21h12a1.7 1.7 0 001.5-2.5L14 9V3M7 15h10"/>',
    "rocket": '<path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M14 4c3-1 6-1 6-1s0 3-1 6l-6 6-4-4zM9 12l-4-1 2-3 4-.5M12 15l1 4 3-2 .5-4"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    "wrench": '<path d="M14.5 6.5a4 4 0 005 5l-9 9a2.1 2.1 0 01-3-3zM15 5l4 4"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M7 9l3 3-3 3M13 15h4"/>',
    "db": '<path d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "flow": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 6H14a4 4 0 014 4v5.5M6 8.5V14a4 4 0 004 4h5.5"/>',
    "branch": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10M18 10c0 4-6 3-12 7"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 019.5 4 8.5 8.5 0 1020 14.5z"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "plug": '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4"/>',
}
ICON_SVG = {k: Markup(f'<svg {_G} aria-hidden="true">{v}</svg>') for k, v in ICONS.items()}

# ---------------------------------------------------------------- docs structure
NAV = [
    ("Get started", [("", "Introduction"), ("install", "Install"), ("quickstart", "Quick start"),
                     ("ways-to-run", "Ways to run"), ("hosting", "Host it for your team"), ("configuration", "Configuration"),
                     ("integrations", "Connect your services")]),
    ("Build automations", [("app", "The web app"), ("use-cases", "Use cases"), ("packs", "Templates"),
                           ("spec", "The spec format"), ("find", "Find tables and actions"), ("preview", "Preview and test"),
                           ("deploy", "Deploy, approve, audit"), ("ai", "AI planner")]),
    ("Trust and help", [("safety", "Safety model"), ("data-security", "Data and privacy"), ("troubleshooting", "Troubleshooting")]),
    ("Reference", [("cli", "CLI reference"), ("actions", "Actions reference"), ("catalog", "The catalogs"), ("architecture", "How it works"),
                   ("development", "Development"), ("changelog", "Changelog")]),
]
DOC_INFO = {
    "": ("book", "What opslens does, how it works in one paragraph, and the principles behind it."),
    "install": ("download", "One command for macOS and Linux, or pip, Docker and source."),
    "quickstart": ("play", "Five minutes on sample data: find, install a template, read it, preview it."),
    "ways-to-run": ("box", "Installer, hosted demo, local app, CLI, Docker and CI."),
    "hosting": ("users", "Run the full app for a team behind HTTPS, with sign-in and an audit trail."),
    "integrations": ("plug", "Teams, Slack, Jira, GitLab, Opsgenie and AWS: tokens, variables, and how to test each."),
    "actions": ("bolt", "Every Jira, Teams, Slack, Opsgenie, GitLab and AWS action, with its parameters."),
    "configuration": ("sliders", "Every setting, where it comes from, and its environment variable."),
    "app": ("layout", "The visual builder: templates, the flow, testing, YAML, and the demo."),
    "use-cases": ("grid", "Four real automations end to end, and how to build your own."),
    "packs": ("puzzle", "The ready-made templates, with their steps and specs."),
    "spec": ("code", "The small YAML format behind every automation, and what validation checks."),
    "find": ("search", "Search 670 tables and 443 actions in plain words."),
    "preview": ("flask", "See exactly what a run would do, with nothing sent."),
    "deploy": ("rocket", "Deploy the reviewed spec, approve changes, read the audit log."),
    "ai": ("sparkle", "Optional drafting from a sentence, with any provider."),
    "safety": ("shield", "How a wrong guess, by a person or a model, cannot change anything."),
    "data-security": ("lock", "What is read, what leaves your machine, and what is stored."),
    "troubleshooting": ("wrench", "The common errors and their fixes, in one place."),
    "cli": ("terminal", "Every command and option, generated from the installed version."),
    "catalog": ("db", "What is in the two catalogs, by plugin and library mod."),
    "architecture": ("flow", "The path from a requirement to an approved run."),
    "development": ("branch", "Set up, test, add a template, regenerate, release."),
    "changelog": ("clock", "What changed in each release."),
}
REPO_DOCS = {"safety": "safety.md"}


sys.path.insert(0, str(Path(__file__).parent))
import diagrams  # hand-built SVG for the Architecture page

PAGES = {  # top-level pages in the header: slug -> (icon, description)
    "commands": ("terminal", "Every useful CLI command, grouped by what you want to do."),
    "architecture": ("flow", "C4 context, container and component diagrams and sequence diagrams of how opslens works."),
}


def render_page(slug: str) -> dict:
    html, h1, toc, lead = render_md((SITE / "content" / "pages" / f"{slug}.md").read_text(), "../", slug)
    for name, svg in diagrams.all_diagrams().items():
        html = html.replace(f"<p>[[diagram:{name}]]</p>", str(svg))
    if "[[diagram:" in html:
        raise SystemExit(f"unknown diagram in {slug}.md")
    return {"html": Markup(html), "h1": h1, "toc": Markup(toc), "lead": Markup(lead), "icon": ICON_SVG[PAGES[slug][0]],
            "edit": f"{REPO_URL}/edit/main/website/content/pages/{slug}.md"}


def packs_md() -> str:
    from opslens import packs

    labels = {"finops-cleanup": "Cost", "governance": "Governance", "security": "Security", "incident": "Incident response",
              "chatops": "ChatOps", "engineering": "Engineering"}
    pc = pcat.load()
    rows = packs.list_packs()
    out = ["# Templates",
           f"{len(rows)} ready-made automations that work with no AI. Each is a small [spec](../spec/) you can read, test, change and deploy. "
           "Open one in the [app](../../app/), or install it with `opslens pack install <name>`. "
           "Everything here previews on the built-in sample data with no account.", "",
           "| template | what it does | asks before changing things |", "|---|---|---|"]
    specs = {r["pack"]: packs.get(r["pack"]) for r in rows}
    for r in rows:
        s = specs[r["pack"]]
        out.append(f"| [{s.title}](#{re.sub(r'[^a-z0-9]+', '-', s.title.lower()).strip('-')}) | {s.description} | {'yes' if s.gated_actions() else 'no, it never changes anything'} |")
    out.append("")
    for cat, label in labels.items():
        mine = [r for r in rows if r["pack"].split("/")[0] == cat]
        if not mine:
            continue
        out += [f"## {label}", ""]
        for row in mine:
            s = specs[row["pack"]]
            when = f"on a schedule ({s.trigger.schedule})" if s.trigger.kind == "schedule" else "on demand"
            out += [f"### {s.title}", f"`{row['pack']}` · runs {when} · [Open in the app](../../app/?pack={row['pack']})", "", s.description, ""]
            out += ["| step | action | effect | when |", "|---|---|---|---|"]
            for i, a in enumerate(s.actions, 1):
                p = pc.get(a.pipeline)
                out.append(f"| {i}. {a.title or a.pipeline} | `{a.pipeline}` | {p.effect if p else '?'} | "
                           f"{'after approval' if a.gated else 'automatic'} |")
            out += ["", f"Variables: {', '.join(f'`{k}`' for k in s.variables) or 'none'}.", "",
                    "```bash", f"opslens pack install {row['pack']}", "```", "", "<details markdown=\"1\"><summary>The spec</summary>", "",
                    "```yaml", s.to_yaml().rstrip(), "```", "", "</details>", ""]
    return "\n".join(out)


def cli_md() -> str:
    import typer.main

    from opslens.cli import app

    root = typer.main.get_command(app)
    out = ["# CLI reference", "Every command and option, generated from the command tree, so it always matches the installed "
           "version. Run `opslens <command> --help` for the same text in your terminal.", ""]

    def walk(cmd, path: str) -> None:
        if hasattr(cmd, "commands"):  # a group (duck-typed: typer may vendor click)
            for name in sorted(cmd.commands):
                walk(cmd.commands[name], f"{path} {name}")
            return
        help_ = " ".join((cmd.help or "").split())
        out.extend([f"## `{path}`", help_, ""])
        params = [x for x in cmd.params if x.name != "help" and x.param_type_name == "option"]
        args = [x for x in cmd.params if x.param_type_name == "argument"]
        if args:
            out.append("Arguments: " + ", ".join(f"`{a.name.upper()}`" for a in args) + "\n")
        if params:
            out.extend(["| option | description |", "|---|---|"])
            for x in params:
                out.append(f"| `{' / '.join(x.opts)}` | {' '.join((getattr(x, 'help', '') or '').split()).replace('|', '/')} |")
            out.append("")

    walk(root, "opslens")
    return "\n".join(out)


def actions_md() -> str:
    pc = pcat.load()
    order = [("jira", "Jira", "A `connection \"jira\"` (base URL, user, API token)"),
             ("teams", "Microsoft Teams", "A `credential \"teams\"` (a Microsoft Graph access token)"),
             ("slack", "Slack", "A `connection \"slack\"` (a token), or just a webhook URL for `post_message_to_webhook`"),
             ("opsgenie", "Opsgenie", "A `connection \"opsgenie\"` (alert and incident API keys)"),
             ("gitlab", "GitLab", "A `connection \"gitlab\"` (a personal access token)"),
             ("ipstack", "ipstack", "A `connection \"ipstack\"` (an access key)"),
             ("aws", "AWS", "A `connection \"aws\"` (profile or keys) **and a running Docker daemon**: these pipelines run the AWS CLI in a container")]
    mark = {"read": "read", "notify": "notify", "change": "**change**"}
    out = ["# Actions reference",
           "Every action opslens can put in an automation for the core services, with its parameters. A `*` marks a required parameter. "
           "**read** only fetches, **notify** adds a message or a record, **change** modifies or deletes something and therefore always "
           "waits for [approval](../deploy/). For one action's types and descriptions run `opslens describe pipeline <name>`; "
           "how to connect each service is in [Connect your services](../integrations/).", ""]
    for mod, label, needs in order:
        items = sorted((n, p) for n, p in pc.pipelines.items() if n.split(".")[0] == mod and ".pipeline.test_" not in n)
        out += [f"## {label}", "", f"{len(items)} actions. Needs: {needs}.", "", "| Action | Effect | Required | Optional |", "|---|---|---|---|"]
        for n, p in items:
            req = ", ".join(f"`{q.name}`" for q in p.params if not q.optional and q.name not in ("conn", "cred"))
            opt = ", ".join(f"`{q.name}`" for q in p.params if q.optional and q.name not in ("conn", "cred"))
            out.append(f"| `{n.replace('.pipeline.', '.')}` | {mark.get(p.effect, p.effect)} | {req or '-'} | {opt or '-'} |")
        out.append("")
    return "\n".join(out)


def catalog_md() -> str:
    tc, pc = tcat.load(), pcat.load()
    by_plugin: dict[str, list] = {}
    for t in tc.tables.values():
        by_plugin.setdefault(t.plugin, []).append(t)
    cols = sum(len(t.columns) for t in tc.tables.values())
    out = ["# The catalogs",
           f"opslens ships two catalogs, built offline from source and checked against the real plugins and library, so search, "
           f"validation and AI drafting never rely on a guess: **{len(tc.tables)} tables** with **{cols:,} typed columns**, and "
           f"**{len(pc.pipelines)} pipelines** from **{len(pc.mods)} library mods**.", "",
           "Browse them in your browser on the [Explore page](../../explore/), or on the command line with [`opslens search`](../find/).", "",
           "## Tables (Steampipe)", "", "| Plugin | Version | Tables | Columns | Notes |", "|---|---|---|---|---|"]
    note = {"aws": "EC2, EBS, S3, IAM, GuardDuty, Cost Explorer and more", "jira": "issues, projects, users, boards",
            "microsoft365": "Teams, users, groups, mail, calendar", "gitlab": "projects, merge requests, deployments, pipelines",
            "opsgenie": "alerts, teams, schedules, users"}
    for name, ver in sorted(tc.plugins.items()):
        ts = by_plugin.get(name, [])
        out.append(f"| `{name}` | {ver} | {len(ts)} | {sum(len(t.columns) for t in ts):,} | {note.get(name, '')} |")
    out += ["", "Each table has its columns and types, which filters are cheap or required, and worked examples. "
            "`opslens describe table <name>` shows them.", "",
            "## Pipelines (Flowpipe)", "", "| Library mod | Version | Pipelines | Read | Change or notify |", "|---|---|---|---|---|"]
    for r in pc.stats():
        out.append(f"| `{r['mod']}` | {r['version']} | {r['pipelines']} | {r['read']} | {r['write']} |")
    out += ["", "Every pipeline is tagged with its **effect**: `read`, `notify` (additive: a ticket, an alert, a message) or `change`. "
            "Only `change` must wait for approval. See the [spec format](../spec/#the-effect-model).", "",
            "## Pinned versions", "",
            "The installer pins the engines and plugins it was tested with, and `opslens catalog verify` compares your installed plugins "
            "with the catalog (using Steampipe's own metadata, with no API calls).", "",
            "```bash", "opslens catalog stats", "opslens catalog verify", "```"]
    return "\n".join(out)


# ---------------------------------------------------------------- markdown rendering
def _toc_html(tokens: list[dict]) -> str:
    def li(t: dict) -> str:
        kids = "".join(li(c) for c in t.get("children", []) if c["level"] <= 3)
        return f'<li><a href="#{t["id"]}">{t["name"]}</a>' + (f"<ul>{kids}</ul>" if kids else "") + "</li>"

    flat: list[dict] = []
    for t in tokens:  # drop the page's H1 (level 1); its children are the sections
        flat.extend(t["children"] if t["level"] == 1 else [t])
    return "<ul>" + "".join(li(t) for t in flat if t["level"] == 2) + "</ul>" if flat else ""


def _img_size(rel: str) -> tuple[int, int] | None:
    from PIL import Image

    f = SITE / "static" / rel
    if not f.is_file():
        return None
    with Image.open(f) as im:
        return im.size


def render_md(text: str, root: str, slug: str) -> tuple[str, str, str, str]:
    """-> (body html, h1, toc html, lead html). Figures for images, absolute-ish asset paths, index-page link fix."""
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "attr_list", "md_in_html"], extension_configs={"toc": {"toc_depth": "2-3"}})
    html = md.convert(text)
    toc = _toc_html(md.toc_tokens)
    m = re.match(r"\s*<h1[^>]*>(.*?)</h1>\s*", html, re.DOTALL)
    h1 = re.sub("<[^>]+>", "", m.group(1)) if m else ""
    html = html[m.end():] if m else html
    lead = ""
    m = re.match(r"\s*<p>(.*?)</p>\s*", html, re.DOTALL)
    if m and "<img" not in m.group(1):
        lead, html = m.group(1), html[m.end():]

    if slug == "":  # the docs home is /docs/, one level shallower than every other page
        html = re.sub(r'(href|src)="\.\./', r'\1="', html)

    def fig(mm: re.Match) -> str:
        alt, rel = mm.group(1), mm.group(2)
        size = _img_size(f"screens/{rel}")
        dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
        return (f'<figure class="shot"><div class="frame"><i></i><i></i><i></i></div><img src="{root}static/screens/{rel}" alt="{alt}"'
                f'{dims} loading="lazy"><figcaption>{alt}</figcaption></figure>')

    html = re.sub(r'<p><img alt="([^"]*)" src="screens/([^"]+)" ?/?></p>', fig, html)
    html = html.replace("<pre><code>", '<pre class="code"><code>')
    html = re.sub(r"<table>", '<div class="tbl"><table>', html)
    html = html.replace("</table>", "</table></div>")
    return html, h1, toc, lead


# ---------------------------------------------------------------- data for the explorer
def export_data() -> dict:
    tc, pc = tcat.load(), pcat.load()
    t = [{"n": x.name, "p": x.plugin, "s": x.service, "d": tcat.first_sentence(x.description or x.summary, 160),
          "c": [[c.name, c.type] for c in x.columns.values()], "f": sorted(x.filters), "r": x.required_text(),
          "ce": x.cost_explorer} for x in tc.tables.values()]
    p = [{"n": x.name, "m": x.mod, "s": x.short, "t": x.title, "d": pcat.first_sentence(x.description, 160),
          "k": x.risk, "e": x.effect, "rec": x.recommended,
          "p": [{"n": q.name, "t": q.type, "r": q.required, "d": pcat.first_sentence(q.description, 100)} for q in x.params]}
         for x in pc.pipelines.values()]
    cfg = {"stopwords": sorted(tcat.STOPWORDS), "synonyms": {k: v for k, v in tcat.SYNONYMS.items()},
           "verbs": pcat.VERBS, "write_words": sorted(pcat.WRITE_WORDS), "read_words": sorted(pcat.READ_WORDS),
           "destructive": sorted(pcat.DESTRUCTIVE)}
    out = SITE / "dist" / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in (("tables", t), ("pipelines", p), ("config", cfg)):
        (out / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")))
    return {"tables": len(t), "columns": sum(len(x["c"]) for x in t), "pipelines": len(p),
            "mods": len(pc.mods), "plugins": len(tc.plugins), "templates": len(__import__("opslens.packs", fromlist=["x"]).list_packs())}


def doc_sources() -> dict[str, str]:
    src: dict[str, str] = {}
    for f in (SITE / "content" / "docs").glob("*.md"):
        src["" if f.stem == "index" else f.stem] = f.read_text()
    for slug, fname in REPO_DOCS.items():
        src[slug] = (ROOT / "docs" / fname).read_text()
    src["packs"], src["cli"], src["catalog"], src["actions"] = packs_md(), cli_md(), catalog_md(), actions_md()
    src["changelog"] = (ROOT / "CHANGELOG.md").read_text()
    return src


def build() -> list[Path]:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(SITE / "static", DIST / "static")
    stats = export_data()
    env = Environment(loader=FileSystemLoader(SITE / "templates"), undefined=StrictUndefined, autoescape=True)
    env.globals["icon"] = lambda n: ICON_SVG[n]

    def shot(name: str) -> dict:
        size = _img_size(f"screens/{name}.webp") or (0, 0)
        return {"src": f"static/screens/{name}.webp", "w": size[0], "h": size[1]}

    env.globals["shot"] = shot
    common = {"version": __version__, "stats": stats, "title": "", "description": "", "page": "", "repo": REPO_URL}
    written: list[Path] = []

    def write(rel: str, tpl: str, **ctx) -> None:
        depth = len([p for p in rel.split("/") if p])
        f = DIST / rel / "index.html" if rel else DIST / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(env.get_template(tpl).render(**{**common, "root": "../" * depth, **ctx}))
        written.append(f)

    write("", "index.html")
    write("explore", "explore.html", title="Explore", page="explore",
          description=f"Search {stats['tables']} Steampipe tables and {stats['pipelines']} Flowpipe pipelines in your browser.")

    for slug, (_, desc) in PAGES.items():
        write(slug, "page.html", title=slug.capitalize(), page=slug, description=desc, pg=render_page(slug))

    sources = doc_sources()
    flat = [(s, t) for _, items in NAV for s, t in items]
    missing = [s for s, _ in flat if s not in sources]
    if missing:
        raise SystemExit(f"docs pages missing: {missing}")
    group_of = {s: g for g, items in NAV for s, _ in items}
    nav = [(g, [{"slug": s, "title": t, "icon": ICON_SVG[DOC_INFO[s][0]]} for s, t in items]) for g, items in NAV]
    topics = [(g, [{"slug": s, "title": t, "icon": ICON_SVG[DOC_INFO[s][0]], "desc": DOC_INFO[s][1]} for s, t in items if s])
              for g, items in NAV]
    for i, (slug, title) in enumerate(flat):
        root = "../../" if slug else "../"
        html, h1, toc, lead = render_md(sources[slug], root, slug)
        edit = {"cli": None, "packs": None, "catalog": None, "changelog": f"{REPO_URL}/edit/main/CHANGELOG.md"}.get(
            slug, f"{REPO_URL}/edit/main/docs/{REPO_DOCS[slug]}" if slug in REPO_DOCS else
            f"{REPO_URL}/edit/main/website/content/docs/{slug or 'index'}.md")
        page = {"slug": slug, "title": title, "html": Markup(html), "toc": Markup(toc), "h1": h1 or title, "lead": Markup(lead),
                "group": group_of[slug], "icon": ICON_SVG[DOC_INFO[slug][0]], "edit": edit}
        prev = {"slug": flat[i - 1][0], "title": flat[i - 1][1]} if i > 0 else None
        nxt = {"slug": flat[i + 1][0], "title": flat[i + 1][1]} if i + 1 < len(flat) else None
        write(f"docs/{slug}".rstrip("/"), "doc.html", title=f"{h1 or title} · docs", page="docs", description=DOC_INFO[slug][1],
              doc=page, nav=nav, topics=topics, prev=prev, next=nxt)

    now = datetime.now(UTC).date().isoformat()
    urls = [SITE_URL + "/" + str(p.relative_to(DIST).parent).replace(".", "").strip("/") for p in written]
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                      + "".join(f"<url><loc>{u.rstrip('/')}/</loc><lastmod>{now}</lastmod></url>" for u in urls)
                                      + "</urlset>\n")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    shutil.copy(ROOT / "install.sh", DIST / "install.sh")  # curl -fsSL https://opslens.devops-monk.com/install.sh | sh
    return written


def check() -> int:
    bad = 0
    for f in DIST.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"#?]+)', f.read_text()):
            if re.match(r"(https?:|mailto:|data:)", ref) or re.fullmatch(r"(\.\./)*app/", ref):
                continue  # /app/ is the demo web app, proxied by nginx (not part of the static build)
            t = (f.parent / ref).resolve()
            if not (t.is_file() or (t / "index.html").is_file()):
                print(f"BROKEN {f.relative_to(DIST)} -> {ref}")
                bad += 1
    print("links ok" if not bad else f"{bad} broken link(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    build()
    sys.exit(check() if "--check" in sys.argv else 0)
