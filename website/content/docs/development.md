# Development and testing

opslens is open source (Apache-2.0): [github.com/devops-monk/opslens](https://github.com/devops-monk/opslens). Contributions are welcome; the shortest path is to add a template or fix a doc.

## Set up

```bash
git clone https://github.com/devops-monk/opslens && cd opslens
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
make test        # unit + integration, offline, a few seconds
make lint        # ruff
```

## Tests

Three tiers, so most checks run anywhere with no services:

| Tier | Needs | Run | Covers |
|---|---|---|---|
| `unit` | nothing | `make test` | the SQL guard, spec model, validator, renderer, catalogs, AI providers (with fakes), the Flowpipe client |
| `integration` | nothing | `make test` | the CLI end to end, the web API, packs, the demo database, the docs' own specs |
| `system` | Flowpipe, Steampipe, network | `OPSLENS_SYSTEM=1 pytest -m system` | every pack loads in the real Flowpipe; a real run and approval; a live planner eval (needs a provider) |

The safety properties (the guard refuses what it should, a change cannot skip its approval, a deploy needs the reviewed hash) all have tests, so a change that weakens one fails CI.

## Add a template

A template is one YAML file under `src/opslens/packs/<group>/`. It must validate cleanly, preview on the demo data, and load in Flowpipe:

```bash
opslens validate path/to/spec --no-load
OPSLENS_SYSTEM=1 pytest -m system tests/system/test_pack_loads_in_flowpipe.py
```

Anything that changes state must be `gated`. If it needs a sample table that the demo database lacks, add rows in `src/opslens/demo/data.py`.

## Regenerate things

| What | How |
|---|---|
| The table catalog | `scripts/build_table_catalog.py` (from plugin source) |
| The pipeline catalog | `scripts/build_pipeline_catalog.py` (uses Flowpipe's parser) |
| This site | `python scripts/build_site.py --check` (verifies every link) |
| The screenshots | `opslens serve --mode demo --port 8078 &` then `node scripts/screenshots.mjs` |

The docs pages for packs, the CLI and the catalogs are generated from the code, so they cannot drift from the version you install.

## Releasing

Tag `vX.Y.Z` (the version in `pyproject.toml` and a section in `CHANGELOG.md` must match). The release workflow builds the wheel and sdist, installs the wheel into a clean environment and runs it, publishes a multi-arch image (GitHub Container Registry, and Docker Hub when configured), uploads to PyPI through Trusted Publishing when enabled, and creates the GitHub release from the changelog.

## Security

See [the safety model](../safety/). Report vulnerabilities through GitHub's private reporting, not a public issue.
