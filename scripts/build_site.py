#!/usr/bin/env python3
"""Build the static site (website/ -> website/dist/).

    python scripts/build_site.py            # build
    python scripts/build_site.py --check    # build, then verify every internal link and asset resolves

The explorer's data (data/*.json) is exported from the shipped catalogs, so the site never drifts from the CLI.
Docs = website/content/docs/*.md + docs/safety.md (single source of truth).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import markdown
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from opslens import __version__
from opslens.catalog import pipelines as pcat
from opslens.catalog import tables as tcat

SITE = ROOT / "website"
DIST = SITE / "dist"
DOCS = [("getting-started", "Getting started", SITE / "content/docs/getting-started.md"),
        ("safety", "Safety", ROOT / "docs/safety.md")]


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
            "mods": len(pc.mods), "plugins": len(tc.plugins)}


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(SITE / "static", DIST / "static")
    stats = export_data()
    env = Environment(loader=FileSystemLoader(SITE / "templates"), undefined=StrictUndefined, autoescape=True)
    common = {"version": __version__, "stats": stats, "title": "", "description": "", "page": ""}

    def write(rel: str, tpl: str, depth: int, **ctx) -> None:
        f = DIST / rel / "index.html" if rel else DIST / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(env.get_template(tpl).render(**{**common, "root": "../" * depth, **ctx}))

    write("", "index.html", 0)
    write("explore", "explore.html", 1, title="Explore", page="explore",
          description="Search 670 Steampipe tables and 443 Flowpipe pipelines in your browser.")
    docs = [{"slug": s, "title": t, "url": "docs/" if s == "getting-started" else f"docs/{s}/"} for s, t, _ in DOCS]
    for slug, title, src in DOCS:
        html = markdown.markdown(src.read_text(), extensions=["fenced_code", "tables", "toc"])
        html = re.sub(r"<pre><code>", '<pre class="code"><code>', html)
        rel = "docs" if slug == "getting-started" else f"docs/{slug}"
        write(rel, "doc.html", rel.count("/") + 1, title=title, page="docs", docs=docs, slug=slug, content=html)
    (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n")


def check() -> int:
    bad = 0
    for f in DIST.rglob("*.html"):
        for ref in re.findall(r'(?:href|src)="([^"#?]+)', f.read_text()):
            if re.match(r"(https?:|mailto:|data:)", ref):
                continue
            t = (f.parent / ref).resolve()
            if not (t.is_file() or (t / "index.html").is_file()):
                print(f"BROKEN {f.relative_to(DIST)} -> {ref}")
                bad += 1
    print("links ok" if not bad else f"{bad} broken link(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    build()
    sys.exit(check() if "--check" in sys.argv else 0)
