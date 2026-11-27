#!/usr/bin/env python3
"""Build the Flowpipe pipeline catalog: every action opslens can compose into a generated pipeline.

    python scripts/build_pipeline_catalog.py ..                    # all ../flowpipe-mod-* directories
    python scripts/build_pipeline_catalog.py ../flowpipe-mod-jira  # one mod

Flowpipe's own parser is the source of truth: for each mod this runs `flowpipe pipeline list --output json` in a
scratch copy (your mod checkouts are never touched; dependencies are installed into the copy), then keeps what a
planner needs: name, title, description, typed params (type, enum, default, optional), outputs, step types, and a
read/write risk class. Writes src/opslens/catalog/data/pipelines.json.gz.

Risk class ("read" or "write") is what the validator uses to demand an approval gate before anything that changes
state. It is deliberately conservative: a pipeline is "read" only when its name starts with a read verb
(list_, get_, search_, describe_, ...); everything else, and any pipeline with a mutating step, is "write".
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "opslens" / "catalog" / "data" / "pipelines.json.gz"

READ_VERBS = ("list", "get", "describe", "search", "find", "lookup", "check", "count", "show", "read", "fetch",
              "query", "detect", "is", "has", "validate", "export", "download", "whoami")
MUTATING_HTTP = {"post", "put", "patch", "delete"}
CATEGORY_OF_MOD = {"aws": "aws", "aws_thrifty": "aws", "aws_tags": "aws"}


def risk_of(short: str, steps: list[dict]) -> str:
    """read | write. 'detect_*' pipelines only query, but 'detect_and_correct_*' act, so they are write."""
    if "correct" in short or "_and_" in short and any(v in short for v in ("delete", "update", "remove", "stop", "modify")):
        return "write"
    first = short.split("_", 1)[0]
    if first not in READ_VERBS:
        return "write"
    for s in steps:
        if s.get("step_type") == "http" and (s.get("method") or "post").lower() in MUTATING_HTTP and first not in (
                "search", "query", "list", "get", "find", "lookup"):
            return "write"
        if s.get("step_type") in ("container", "function"):
            # AWS CLI containers: reads are describe-*/list-*/get-*; trust the name verb already checked
            continue
    return "read"


def clean_param(p: dict) -> dict:
    out = {"name": p["name"], "type": p.get("type_string") or "any", "description": (p.get("description") or "").strip(),
           "optional": bool(p.get("optional")) or p.get("default") is not None}
    d = p.get("default")
    if isinstance(d, dict) and d.get("resource_type"):
        out["default"] = f"{d['resource_type']}.{d.get('type', '')}.{d.get('short_name', 'default')}".replace("..", ".")
    elif d is not None:
        out["default"] = d
    if p.get("enum"):
        out["enum"] = p["enum"]
    return out


def git_version(path: Path) -> str:
    r = subprocess.run(["git", "-C", str(path), "describe", "--tags", "--always"], check=False, capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def list_mod(mod_dir: Path, scratch: Path) -> tuple[list[dict], str]:
    work = scratch / mod_dir.name
    shutil.copytree(mod_dir, work, ignore=shutil.ignore_patterns(".git", ".flowpipe", ".github"))
    data = scratch / f"data-{mod_dir.name}"
    data.mkdir()
    if re.search(r'^\s*mod\s+"github', (work / "mod.fp").read_text(), re.MULTILINE):
        r = subprocess.run(["flowpipe", "mod", "install", "--data-dir", str(data)], cwd=work, check=False, capture_output=True,
                           text=True)
        if r.returncode:
            raise SystemExit(f"{mod_dir.name}: mod install failed:\n{r.stderr or r.stdout}")
    r = subprocess.run(["flowpipe", "pipeline", "list", "--output", "json", "--data-dir", str(data)], cwd=work,
                       check=False, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{mod_dir.name}: flowpipe failed:\n{r.stderr or r.stdout}")
    return json.loads(r.stdout), git_version(mod_dir)


def build(mod_dirs: list[Path]) -> dict:
    pipelines: dict[str, dict] = {}
    mods: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for d in mod_dirs:
            raw, version = list_mod(d, Path(tmp))
            own = d.name.removeprefix("flowpipe-mod-").replace("-", "_")
            mods[own] = version
            for p in raw:
                mod = p["mod"].removeprefix("mod.")
                if mod != own:  # dependency pipelines are catalogued from their own repo
                    continue
                short = p["name"].rsplit(".", 1)[-1]
                steps = [{"type": s.get("step_type"), "name": s.get("name"),
                          **({"method": s["method"]} if s.get("method") else {})} for s in p.get("steps", [])]
                tags = p.get("tags") or {}
                pipelines[p["name"]] = {
                    "name": p["name"], "mod": mod, "short": short, "title": p.get("title") or short.replace("_", " ").title(),
                    "description": (p.get("description") or "").strip(),
                    "tags": tags, "params": [clean_param(x) for x in p.get("params", [])],
                    "outputs": [{"name": o["name"], **({"description": o["description"]} if o.get("description") else {})}
                                for o in p.get("outputs", [])],
                    "steps": steps, "risk": risk_of(short, steps),
                    "folder": (tags.get("folder") or ""),
                }
    return {"mods": mods, "pipelines": dict(sorted(pipelines.items()))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", type=Path, help="A flowpipe-mod-* directory, or a directory containing several")
    a = ap.parse_args()
    p = a.path.expanduser().resolve()
    mods = sorted(p.glob("flowpipe-mod-*")) if not p.name.startswith("flowpipe-mod-") else [p]
    mods = [m for m in mods if (m / "mod.fp").exists()]
    if not mods:
        print("no flowpipe-mod-* directories found", file=sys.stderr)
        return 2
    cat = build(mods)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(json.dumps(cat, separators=(",", ":"), sort_keys=True).encode(), 9, mtime=0))
    n = cat["pipelines"]
    writes = sum(1 for x in n.values() if x["risk"] == "write")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(n)} pipelines from {len(cat['mods'])} mods "
          f"({writes} write, {len(n) - writes} read), {OUT.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
