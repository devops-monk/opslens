"""Packs: curated, versioned specs that work with no AI. `opslens pack install <name>` renders one into a mod.

A pack is a spec YAML under packs/<group>/<name>.yaml. Its variables (thresholds, project keys, ...) can be
overridden at install time with `--var name=value`.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

from ..spec.model import Spec, load_spec


def _files() -> list[tuple[str, Any]]:
    root = resources.files("opslens.packs")
    out = []
    for group in sorted(root.iterdir(), key=lambda p: p.name):
        if group.is_dir() and not group.name.startswith("_"):
            for f in sorted(group.iterdir(), key=lambda p: p.name):
                if f.name.endswith(".yaml"):
                    out.append((f"{group.name.replace('_', '-')}/{f.name[:-5].replace('_', '-')}", f))
    return out


def list_packs() -> list[dict[str, Any]]:
    rows = []
    for name, f in _files():
        s = load_spec(f.read_text())
        rows.append({"pack": name, "title": s.title, "trigger": s.trigger.kind,
                     "actions": ", ".join(a.pipeline for a in s.actions), "variables": ", ".join(s.variables)})
    return rows


def get(name: str, overrides: dict[str, str] | None = None) -> Spec:
    for pack, f in _files():
        if pack == name:
            spec = load_spec(f.read_text())
            for k, v in (overrides or {}).items():
                if k not in spec.variables:
                    raise KeyError(f"pack {name} has no variable '{k}' (variables: {', '.join(spec.variables) or 'none'})")
                cur = spec.variables[k].default
                spec.variables[k].default = type(cur)(v) if not isinstance(cur, bool) else v.lower() in ("1", "true", "yes")
            return spec
    raise KeyError(f"unknown pack '{name}' (see `opslens pack list`)")
