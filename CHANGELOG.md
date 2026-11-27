# Changelog

## Unreleased (Phase 2, in progress)

- **Mod spec** (`opslens.spec`): a small typed description of one detect-and-act automation, and a deterministic
  **renderer** that turns it into a Flowpipe mod (`mod.fp`, `pipelines.fp`, `triggers.fp`, `spec.yaml`, `README.md`).
  Every literal is escaped (no HCL injection); connections and notifiers are params, never inline secrets.
- **Validator**: SQL guard + catalog allow-list, columns checked against `{placeholders}`, pipelines and params
  checked against the pipeline catalog, enum/type checks, inline-secret refusal, schedule floor (5 min), and a
  **hand-edit drift check** (generated files must match `spec.yaml`). `change` pipelines must sit behind approval;
  additive `notify` pipelines (tickets, alerts, messages) may run ungated.
- **Load check**: Flowpipe's own parser judges the generated mod (in a scratch copy).
- `opslens pack list|show|install`, `render`, `validate`, `preview` (what a run would do right now, nothing executed).
- First pack: `finops-cleanup/unattached-volumes` (Jira ticket per volume, delete after approval).
- Demo data now takes the same Postgres SQL as live queries (transpiled), e.g. `now() - interval '14 days'`.
- **Web app (Phase 4)**: `opslens serve` (FastAPI + a single-page UI): Find, Build and Mods tabs over the same engine. Local mode (loopback only,
  Host allow-list, per-session token) does the full workflow; `--mode demo` is public-safe (sample data, no writes, no AI, rate limited).
  Spec YAML now writes multi-line SQL as readable `|` blocks.
- **AI planner (Phase 3)**: `opslens generate` turns a requirement into a validated spec and mod; `opslens explain` reads any spec in
  plain English (no AI). Providers: anthropic (SDK, adaptive thinking, prompt caching, refusal fallback), openai, openai_compatible, glm,
  openrouter, ollama (plain HTTP, no extra dependency) and litellm (azure, bedrock, gemini...). Catalog-grounded prompt, validator feedback
  loop, `auto_apply` forced off, requirement redaction, `--show-context`. Live eval set in `evals/`.
- **Pack `governance/tag-enforcement`**: running EC2 instances with no Owner tag get a Jira ticket each; after approval they are
  tagged `compliance=missing-owner`. Specs can now set `map(string)` params as `key=value,key2=value2`.
- **Deploy and run**: `opslens deploy` (refuses unless you pass `--approve <spec hash>` for the exact spec you
  reviewed), `run`, `approve`, `runs`, `undeploy`. Handwritten Flowpipe REST client; a run waiting on an approval step
  is detected (Flowpipe reports it as `started`) and the approval form link is surfaced. Append-only SQLite audit log
  of deploys, runs and approvals. One Flowpipe server per deployed mod (triggers fire only for the top-level mod).
- Fix: an unknown param named like a secret (`token`) is now refused as an inline secret.

## 0.1.0 (unreleased)

First release (Phase 1): catalogs and the no-AI CLI.

- **Table catalog** for five Steampipe plugins (AWS, Jira, Microsoft 365, GitLab, Opsgenie): 670 tables with columns,
  types, descriptions, required and fast filters, and examples. Built from plugin source by
  `scripts/build_table_catalog.py`.
- **Pipeline catalog**: 443 Flowpipe pipelines from 15 library mods with typed params, outputs and a read/write risk
  class. Built with Flowpipe's own parser by `scripts/build_pipeline_catalog.py`.
- `opslens find` / `describe`: one search over tables and pipelines, offline, no AI.
- `opslens query`: read-only SQL through a guard (single SELECT, catalog allow-list, timeout, row cap).
- `opslens doctor`, `init`, `params`, `config`, `catalog stats|verify`. Layered configuration.
- Demo mode with bundled sample data (`--source demo`): no cloud account, no credentials.
- Packaging: wheel, Docker image (Flowpipe, Steampipe and plugins baked in), `install.sh`, CI.
