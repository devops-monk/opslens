# Contributing

```bash
git clone https://github.com/devops-monk/opslens && cd opslens
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
make test        # unit + integration, offline
make lint        # ruff
```

- Tests are in tiers: `unit`, `integration` (both offline), and `system` (opt in with `OPSLENS_SYSTEM=1`; needs `flowpipe`, network,
  and for the planner eval an LLM provider).
- A new **pack** is one YAML under `src/opslens/packs/<group>/`. It must validate clean, preview on demo data, and load in Flowpipe
  (`OPSLENS_SYSTEM=1 pytest -m system tests/system/test_pack_loads_in_flowpipe.py`). Anything that changes state must be `gated`.
- Catalogs are generated: `scripts/build_table_catalog.py` and `scripts/build_pipeline_catalog.py`; do not hand-edit them.
- Keep changes small and tested; the safety properties (read-only SQL, approval before change, reviewed-hash deploys) have tests,
  so a change that weakens one should fail CI.

By contributing you agree your work is licensed under Apache-2.0.
