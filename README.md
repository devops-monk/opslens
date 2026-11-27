<h1 align="center">opslens</h1>

<p align="center"><b>Say what you want done. Get a pipeline you can read, review and trust.</b></p>

<p align="center">
  opslens turns plain-English ops requirements into reviewable
  <a href="https://flowpipe.io">Flowpipe</a> pipelines. It knows every
  <a href="https://steampipe.io">Steampipe</a> table (what you can <i>ask</i>) and every Flowpipe pipeline (what you
  can <i>do</i>) across AWS, GitLab, Jira, Opsgenie and Microsoft Teams, so nothing is guessed. It works without AI.
</p>

<p align="center"><b>🛡️ Read-only by default.</b> Queries go through a guard: one <code>SELECT</code>, tables from the
catalog, a timeout and a row cap. Nothing that changes state runs without an approval gate.</p>

> [!NOTE]
> **v0.1.0 is Phase 1; Phase 2 is in progress on `main`.** Search, describe, query, and now `pack install`, `validate`
> and `preview` work. Deploying and the AI planner are next; see [docs/implementation-plan.md](docs/implementation-plan.md).

## Why

Ops automation is two problems: **find the data** ("which volumes are unattached?") and **take the action** ("open a
ticket, tell the owner, snapshot, delete after approval"). Tools solve one or the other, and an AI left to guess
table and parameter names gets both wrong. opslens ships the answer key:

| Catalog | What it holds | Size |
|---|---|---|
| **Tables** | Steampipe plugin tables: columns, types, descriptions, required and fast filters, examples | 670 tables, 5 plugins |
| **Pipelines** | Flowpipe library pipelines with typed params, outputs and a **read/write risk class** | 443 pipelines, 15 mods |

Both are built from source, and the table catalog is verified against the installed plugins
(`opslens catalog verify`: 670 of 670 tables, zero drift).

## Install

**macOS or Linux**, one command, no sudo. Installs pinned Flowpipe and Steampipe, the five plugins, and opslens in
its own isolated environment (each binary is checked against the release's `checksums.txt`):

```bash
curl -fsSL https://raw.githubusercontent.com/devops-monk/opslens/main/install.sh | sh
```

**Docker**: everything included, for amd64 and arm64.

```bash
docker build -t opslens .
docker run --rm opslens search "unattached ebs volumes then open a jira ticket"
```

`OPSLENS_DRY_RUN=1 sh install.sh` prints each step without changing anything.

## Try it in thirty seconds

Every command below works with **no cloud account and no credentials**:

```bash
opslens search "unattached ebs volumes older than 14 days, then open a jira ticket and post to teams"
opslens describe table aws_ebs_volume
opslens describe pipeline jira.create_issue
opslens query --source demo "select volume_id, size from aws_ebs_volume where state = 'available'"
```

`search` splits a requirement into **data** and **action** clauses and answers each from the right catalog:

```
Data (Steampipe tables) for: unattached ebs volumes older than 14 days
  aws_ebs_volume, aws_ebs_snapshot ...
Action (Flowpipe pipelines) for: open a jira ticket
  jira.pipeline.create_issue   write   Create a new issue in a Jira project.
Action (Flowpipe pipelines) for: post to teams
  teams.pipeline.send_channel_message   write   Send a new chat message in the specified channel.
```

## Against your own accounts

```bash
opslens doctor                      # tools, plugins, versions; says exactly how to fix anything missing
steampipe service start
opslens query "select count(*) from aws_ebs_volume where state = 'available'"
opslens catalog verify              # does the catalog match your installed plugins?
```

opslens uses whatever credentials the Steampipe plugins already use (your AWS profile, Jira token, ...). It stores none.

## Commands

| Command | What it does |
|---|---|
| `search "<requirement>"` | Both catalogs at once, split into data and action clauses |
| `find tables <words>` / `find pipelines <words>` | Ranked search; `--plugin`, `--mod`, `--writes`, `--reads` |
| `describe table <name>` / `describe pipeline <name>` | Columns, filters, examples / typed params, outputs, risk, usage snippet |
| `query "<sql>"` | One guarded read-only `SELECT`; `--source demo` for sample data; `-f table\|json\|csv` |
| `pack list\|show\|install` | Curated automations; `install` renders a Flowpipe mod you can read and review |
| `validate <mod>` / `preview <mod>` | Safety + catalog checks and Flowpipe's own parser / what a run would do right now (reads only) |
| `render <spec.yaml>` | Spec to Flowpipe mod |
| `catalog stats` / `catalog verify` | What ships / compare with installed plugins |
| `doctor`, `init`, `params`, `config` | Setup, layered settings (defaults, `opslens.yaml`, `OPSLENS__*` env, `--set`) |

Exit codes: `0` ok, `1` error, `2` bad settings or usage, `3` query refused by the guard.

## How it stays safe

1. **Guard**: a single `SELECT`/`WITH`; no `INSERT`, `DROP`, `COPY`, `SET`, file or sleep functions; no system schemas;
   every table must be in the catalog.
2. **Connection**: live queries run with `default_transaction_read_only = on`, a statement timeout and a row cap.
3. **Risk classes**: every pipeline is `read` or `write`. Phase 2's validator will require an approval gate before any
   `write` step in a generated pipeline.

More in [docs/safety.md](docs/safety.md).

## Licensing

opslens is **Apache-2.0**. Flowpipe and Steampipe are AGPL-3.0; opslens runs them as separate, unmodified programs and
talks to them over a database connection and HTTP. It does not link to them or vendor their source. See
[NOTICE](NOTICE).

## Roadmap

| Phase | Delivers | Status |
|---|---|---|
| 0 | Spike: validation and REST run flow confirmed ([findings](docs/phase0-findings.md)) | done |
| 1 | Catalogs, guard, no-AI CLI, packaging | **this release** |
| 2 | Mod spec, renderer, validator + preview, packs: **built**; deploy and run tracking, more packs: in progress | **in progress** |
| 3 | AI planner (any LLM provider), `generate`, `explain` | |
| 4 | Web UI: review, approve, runs | |
| 5 | More packs, incident-copilot demo, docs site | |

## Development

```bash
uv venv && uv pip install -e ".[dev]"
make test         # unit + integration, offline
make lint
make docker-build docker-smoke
make catalog      # rebuild catalogs (needs flowpipe and plugin source checkouts)
```

`OPSLENS_SYSTEM=1 make test-system` checks the catalog against a real Steampipe; see `tests/system/test_live.py`.
