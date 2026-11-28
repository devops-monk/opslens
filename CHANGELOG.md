# Changelog

## 0.3.3 (2026-11-28)

- **`opslens connect <service>`**, `opslens connections [--test]` and `opslens disconnect <service>`: opslens now owns the credentials for
  Jira, Teams, Slack, GitLab, Opsgenie, AWS and ipstack. They are saved privately (`~/.config/opslens/connections.json`, mode 600) and
  handed to the programs opslens starts, so there are no helper config files to edit. Real environment variables still win.
  Non-secret details can go in `opslens.yaml` under `connections:`; secrets are refused there.
- The data service now starts automatically when a live query needs it (`steampipe.auto_start`, on by default).

## 0.3.2 (2026-11-28)

- `opslens query` given plain words (not SQL) now says so and suggests `opslens search`.
- `opslens doctor` prints a link to the guide for connecting Jira, Teams, Slack, GitLab, Opsgenie and AWS.
- Docs: **Explained simply** (a story, a picture and a step-by-step example), a command map and glossary on the Commands page, a
  step-by-step search guide, a five-step recipe for connecting each service, and a worked ipstack example for finding a public IP.

## 0.3.1 (2026-11-28)

- Docs: a step-by-step AI setup guide with a worked "find the IP addresses" example, a **Connect your services** guide (Teams, Slack,
  Jira, GitLab, Opsgenie, AWS: tokens, variables, how to test), and a generated **Actions reference**.
- Site: a **Commands** page and an **Architecture** page (C4 context, container and component diagrams, and sequence diagrams) in the header.
- `opslens doctor` now checks for Docker, which AWS action pipelines need.
- Sample data: demo EC2 instances now have public and private IP addresses.

## 0.3.0 (2026-11-28)

- **Team mode** (`opslens serve --mode team`): host the full web app for a team. It refuses to start without sign-in and a
  `--allow-host`. Sign in with a shared password (`OPSLENS_TEAM_PASSWORD`, signed `HttpOnly`/`SameSite=Strict`/`Secure` session
  cookie, rate-limited) or through an identity proxy (`--auth proxy`, shared secret so identity headers cannot be forged). The audit
  log records who deployed, ran and approved. `/healthz` for health checks. Local mode still binds loopback only; demo is unchanged.
- **`deploy/team/`**: Docker Compose stack (opslens + Caddy with automatic HTTPS), `.env.example` and a hosting guide in the docs.
- Fix: a recycled process id after a container or machine restart could be mistaken for a running Flowpipe server (blocking a deploy) or,
  worse, be sent a kill signal on undeploy. A server now counts as running only when Flowpipe answers on its recorded port.

- **28 new templates (32 in total)**, in six categories. Every one validates, renders, and finds rows on the built-in sample data.
  - Cost: unattached Elastic IPs, old EBS snapshots, gp2 to gp3, stop dev and staging instances, non-production NAT gateways.
  - Governance: S3 cost-center tags, deprecated Lambda runtimes, IAM users without MFA, KMS key rotation, expiring ACM certificates.
  - Security: public S3 buckets, SSH/RDP open to the world, stale IAM access keys, RDS public or unencrypted, RDS without backups, unencrypted snapshots.
  - Incident: CloudWatch alarms to Teams, unacknowledged P1/P2 alerts, failed GitLab deployments, Opsgenie alert to Jira.
  - ChatOps: daily ops digest, new IAM access keys, public GitLab projects, new S3 files to Teams.
  - Engineering: stale merge requests, inactive GitLab projects, stale and overdue Jira issues.
  Anything that deletes, stops, revokes or modifies asks for approval first; the rest never changes anything.
- Sample data covers 15 more tables so every template can be tried with no account.
- The web app gallery sorts and filters by the new categories; the Templates docs page is grouped by category with an overview table.

## 0.2.1 (2026-11-28)

A redesigned web app, website and docs. No change to specs, rendering or safety behaviour.

- **Web app**: Zapier-style builder (trigger, find, actions, approval) with a template gallery, action picker, plain-English summary,
  Test panel, YAML dialog, Explore and My automations. New endpoints `/api/columns`, `/api/pipelines`, `/api/mods/{name}`; richer `/api/packs`.
- **Website**: new landing page with screenshots, feature explanations, use cases and install options (one command, pipx/pip, Docker, source).
- **Docs**: restructured into grouped pages (Get started, Build automations, Trust and help, Reference) with sidebar filter, table of contents and pager.
- `scripts/screenshots.mjs` regenerates the site screenshots; `pillow` added to the dev extras for the site build.

## 0.2.0 (2026-11-27)

Phases 2 to 5: specs and packs, deploy and run, AI planner, web app, docs and packaging.

- **Packs `security/guardduty-to-jira` and `incident/incident-copilot`**: one ticket per new high-severity GuardDuty finding (never filed twice:
  the query skips findings that already have a Jira issue); and an on-demand incident digest that enriches each open Opsgenie alert with
  recent GitLab deploys and open high-priority Jira issues in a single cross-plugin query, then posts to Teams.
- Validator: warns when a variable still has a `CHANGE-ME` placeholder default; the inner-LIMIT warning now fires only for a top-level LIMIT.
- **Docs site**: generated Packs and CLI reference pages; `examples/demo.sh` (a two-minute tour on sample data, covered by a test).
- **Releases**: tag-triggered workflow (build and clean-venv check, multi-arch image on GHCR and, when configured, Docker Hub
  `abhaypratap/opslens`, PyPI via Trusted Publishing, GitHub release with the changelog section).
- **Docker**: the image includes the web and AI extras; `serve --mode demo` works in a container without starting Steampipe.
- Demo data: sample GuardDuty findings with timestamps relative to now.

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
- **Demo deployment**: `scripts/deploy_app.sh` ships the public demo to `/app/` on the VPS (unprivileged `opslens` user, systemd sandbox with
  memory/CPU limits, loopback-only, one additive nginx location). UI uses relative URLs so it works under a path prefix.
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
