# opslens: Implementation Plan

Working name: **opslens** (rename freely). An open-source platform that turns plain-English ops requirements into
reviewable, deterministic Flowpipe pipelines, using a catalog of Steampipe tables (what you can ask) and Flowpipe mod
pipelines (what you can do). AI is optional: everything it produces is plain HCL that runs without it.

Scope decided: directions **1 (Pipeline Studio) + 2 (Ops Autopilot packs) + 3 (Incident Copilot demo)**, **Python**,
**open source**. v1 integrations: **AWS, GitLab, Jira, Opsgenie, Microsoft Teams** (plus Slack/email via Flowpipe notifiers).

---

## 1. Goals and non-goals

**Goals**
1. `describe` the world: a searchable catalog of Steampipe tables and Flowpipe pipelines, with no AI needed.
2. `generate`: natural language to a Flowpipe mod, validated and previewed before anything can run.
3. `run`: deploy generated mods to a Flowpipe server, with approval gates, over its REST API.
4. Ship curated **packs** that work with zero AI (FinOps cleanup, security finding to Jira, incident enrichment).
5. Every AI path has a no-AI equivalent command (as SpendLens does with its "next time without AI" hints).

**Non-goals (v1)**
- Replacing Flowpipe's engine, or forking it. We run it as a separate process.
- Multi-tenant SaaS, RBAC and SSO. Single-team, self-hosted first.
- Visual drag-and-drop builder. The review UI shows and edits HCL; a graph view is read-only.
- Arbitrary `container` / `function` steps in generated code.

## 2. Principles (carried over from SpendLens)

- **Read-only by default.** The AI queries freely but cannot run a write step. Writes need an approval gate in the pipeline.
- **Catalog first, never guess.** The model may use only tables, columns and pipelines found through catalog tools.
- **Generated artifacts are inspectable HCL in git.** No hidden state.
- **Data is never instructions.** Ticket, alert and resource text is untrusted (prompt-injection hygiene).
- **Deterministic runtime.** After approval, no LLM is in the execution path.
- **Fail loud.** Unknown keys, bad references and failed validation stop the flow with a clear error.

## 3. Licensing and process boundary

- opslens: **Apache-2.0**.
- Flowpipe core is **AGPL-3.0**; library mods are Apache-2.0. opslens never links to or modifies Flowpipe: it installs
  the released binary and talks to it over its HTTP API and CLI. Document this boundary in `NOTICE` and `docs/licensing.md`.
- Do not vendor Flowpipe source. Do not redistribute a modified Flowpipe.
- Steampipe plugins are Apache-2.0; Steampipe itself is AGPL-3.0 (same process-boundary rule).
- Action item before first release: a licensing review of the Docker image, since it bundles Flowpipe and Steampipe binaries.

## 4. Architecture

```
                         ┌───────────────────────────── opslens (Python) ─────────────────────────────┐
 CLI / Web UI ─────────► │  Planner agent (LiteLLM, tool-calling)                                       │
                         │    tools: find_tables · describe_table · run_sql(guarded)                    │
                         │           find_pipelines · describe_pipeline · validate_mod · preview_mod    │
                         │                                                                               │
                         │  Catalogs        Generator         Validator            Deployer             │
                         │  tables.json     HCL templates     load-in-scratch      git commit +         │
                         │  pipelines.json  + LLM fill        + lint rules         Flowpipe REST API    │
                         │  (built offline) (typed slots)     + preview variant    + run/approval track │
                         └───────────┬───────────────────────────────┬──────────────────────┬───────────┘
                                     │ SQL (read-only role)           │ scratch mod dir      │ HTTP :7103
                                     ▼                                ▼                      ▼
                               Steampipe :9193                   flowpipe (load)       Flowpipe server
                               (aws, gitlab, jira,               validates HCL         triggers, input steps,
                                opsgenie, ...plugins)                                  notifiers, run store
```

### Components

| Component | Responsibility |
|---|---|
| **Catalog builder** | Offline: builds `tables.json` from Steampipe plugin docs/source (columns, types, required quals, examples) and `pipelines.json` from mod `.fp` files and `GET /api/latest/pipeline` (params, types, enums, outputs, tags). Merges live `information_schema` when Steampipe is reachable. |
| **Catalog search** | Keyword plus synonym plus embedding-free ranking first (SpendLens approach); optional embeddings later. Used by tools and the no-AI `find` command. |
| **SQL guard** | Single `SELECT`/`WITH` only (sqlglot), allow-list of tables from the catalog, statement timeout, row cap, read-only DB role. Reused and generalized from SpendLens `sql_guard.py`/`sql_check.py`. |
| **Planner agent** | Tool-calling loop: clarify intent, pick tables, test the query, pick action pipelines, emit a **mod spec** (JSON), not free-form HCL. |
| **Generator** | Renders a validated mod spec into HCL with deterministic templates (see section 6). The LLM fills typed slots; it does not write raw `.fp` files. |
| **Validator** | (a) schema check of the spec, (b) lint rules, (c) load the mod in a scratch workspace with `flowpipe` to catch parse/reference/type errors, (d) preview variant run. |
| **Deployer** | Writes the mod to a git-backed workspace, starts/updates the Flowpipe server, manages enable/disable of triggers, records runs. |
| **Run tracker** | Polls/streams `GET /process/:id`, mirrors state in local SQLite for the UI and audit. |
| **Packs** | Versioned, parameterized mod specs shipped in the repo; installable with no AI. |
| **Web UI** | FastAPI backend + small frontend: catalog browser, chat/generate, review (HCL diff, sample rows, plan preview), runs, approvals. |

### Why a mod *spec* instead of raw HCL from the LLM
Models write plausible but invalid HCL. A constrained spec (JSON schema) of
`{trigger, detect{table, sql}, per_item[...steps], approval{...}, notify{...}}` is validated before rendering, which
removes whole error classes and makes the preview variant mechanical to derive.

## 5. Repository layout

```
opslens/
  pyproject.toml          # python 3.11+, typer, rich, pydantic, litellm, sqlglot, psycopg, httpx, fastapi, jinja2
  src/opslens/
    cli.py                # typer app
    config.py             # layered config (defaults, opslens.yaml, env, --set), like SpendLens
    catalog/
      build_tables.py     # steampipe plugin metadata -> tables.json.gz
      build_pipelines.py  # mod .fp parse + REST -> pipelines.json.gz
      search.py           # find/describe, synonyms
      data/               # shipped catalogs per pinned plugin/mod version
    sql/guard.py          # sqlglot-based read-only guard
    ai/
      provider.py         # LiteLLM adapter: openai, azure, bedrock, anthropic, openai-compatible
      agent.py            # tool loop, step budget
      prompts.py          # stable system prompt (cache-friendly)
      tools.py
      sessions.py         # saved conversations, resumable
    spec/
      model.py            # pydantic mod spec
      render.py           # spec -> HCL (jinja2)
      lint.py             # rules in section 7
    validate/
      load.py             # scratch workspace + flowpipe load check
      preview.py          # builds the read-only preview variant, runs queries
    flowpipe/
      client.py           # REST client (typed from /docs/openapi.json)
      server.py           # start/stop/health, workspace management
    runs/store.py         # SQLite: generated mods, runs, approvals, audit
    packs/                # finops_cleanup/, sec_to_jira/, incident_enrichment/
    web/                  # fastapi app + static UI
  mods/                   # vendored list of library mods + pinned versions (mods.lock)
  tests/
  docs/  website/
  docker/
```

## 6. The mod spec and generated mod layout

A generated mod is a **top-level mod** (only top-level triggers fire in Flowpipe) that `require`s library mods:

```
generated/<slug>/
  mod.fp            # mod "<slug>" { require { mod "github.com/turbot/flowpipe-mod-jira" {version=...} ... } }
  pipelines.fp      # detect, per-item action, approval, notify
  triggers.fp       # schedule / query / (webhook disabled by default)
  variables.fp      # thresholds, schedule, notifier, approvers, with defaults
  README.md         # generated explanation + the original request
  spec.json         # the validated spec (source of truth)
```

Spec sketch (pydantic):

```
Spec: name, description, request_text, requires[mods],
      trigger: schedule|query|manual,
      detect: {database, sql, key_column?},           # SQL validated by guard + catalog
      for_each_item: [Step...],                       # ordered, typed
      approval: optional {notifier_param, approvers, options[], default_action, timeout},
      on_error: {retry, notify}
Step kinds (allow-list): query, http(read-only methods unless inside approval branch),
      pipeline(<catalog pipeline + args>), transform, message, input, sleep
```

Rules baked into rendering:
- Secrets and connections only as `param ... type = connection.<x>` defaulting to `connection.<x>.default`. Never inline.
- Notifier via `param "notifier"` and `notifier[param.notifier]`.
- External-call steps get `retry` (exponential, 3) and `error` handling; failures notify instead of silently stopping.
- Write actions (`delete_*`, `create_*`, `update_*`, `transition_*`, anything the catalog tags as `class=write`) must sit
  behind an `input` step unless the spec carries an explicit `auto_apply=true` that the user confirms at review.
- `container` / `function` steps are not emittable (admin allow-list only, off by default).

## 7. Validation pipeline (our own, since Flowpipe has no validate/dry-run command)

1. **Spec validation**: pydantic schema, referenced tables and columns exist in the catalog, referenced pipelines exist, args match param types and enums.
2. **SQL validation**: guard (single SELECT, allow-listed tables, required quals present) plus `EXPLAIN` against Steampipe.
3. **Lint rules** (`spec/lint.py`): no inline secrets, no unguarded write step, retry on external calls, bounded `for_each` (cap, default 50 items per run), no webhook trigger without an explicit flag, schedule not shorter than a configured minimum.
4. **Load check**: render into a scratch workspace, run `flowpipe pipeline list` against it with a throwaway data dir. Parse, reference and type errors surface here. (Verify in Phase 0 that this reports errors with a non-zero exit code; if not, parse the output.)
5. **Preview variant**: render a second copy in which every non-read step is replaced with a `transform`/`message` that echoes what *would* happen. Run the detect query for real, run the preview pipeline over the REST API, and show: row count, sample rows, the per-item plan, estimated blast radius (items affected), and the approval flow.
6. **Gate**: deploy is enabled only when 1-5 pass and a human approves in the review step. The reviewer approves a specific content hash of `spec.json`.

## 8. AI behaviour

- Provider-agnostic through LiteLLM; config `llm.provider`, `llm.model`, base URL for local models. Same providers as SpendLens.
- Tools exposed: `find_tables`, `describe_table`, `run_sql` (guarded, row-capped), `find_pipelines`, `describe_pipeline`,
  `validate_spec`, `preview_spec`. No tool can deploy or run a write step. Deploy is a human action in CLI/UI.
- Loop: clarify, explore data (tables + a sample query), choose actions, emit spec, auto-fix on validation errors
  (bounded retries, error text fed back), then stop and present for review.
- System prompt is stable per config for prompt caching. Tool-result text is wrapped and labeled as data.
- Fallback when a model lacks tool calling: say so, point at the no-AI commands.
- Cost controls: step budget, token logging per session, offline catalog (no per-question API calls to build context).
- Explanations: `opslens explain <mod|run>` summarizes a mod or a failed run in plain English (read-only).

## 9. CLI (v1)

```
opslens init                      # config, check tools, pin plugin/mod versions
opslens doctor                    # steampipe, flowpipe, plugins, connections, LLM reachable
opslens catalog build|show        # build/refresh catalogs
opslens find tables|pipelines <words>
opslens describe table|pipeline <name>
opslens query "<sql>"             # guarded, read-only
opslens generate "<request>"      # AI: request -> spec -> validate -> preview; writes generated/<slug>
opslens pack list|show|install <pack> --set key=value     # no AI
opslens validate <mod>            # steps 1-5 above
opslens preview <mod>
opslens deploy <mod>              # asks for approval of the spec hash; starts/updates server
opslens runs list|show|tail <id>
opslens enable|disable <mod>      # triggers
opslens explain <mod|run-id>
opslens serve                     # web UI + API
```

Every `generate` result prints the equivalent no-AI commands (`pack install ...`, `query ...`) for reuse without tokens.

## 10. Web UI (v1, thin)

- **Catalog**: search tables and pipelines, columns, params, examples.
- **Generate**: chat on the left; right pane shows spec, rendered HCL, sample rows, preview plan.
- **Review**: HCL diff vs. deployed version, lint results, blast radius, an explicit "Approve spec <hash>" button.
- **Runs**: live list from Flowpipe, run detail with step outputs, pending approvals with a link to the Flowpipe input form.
- Stack: FastAPI plus server-rendered templates plus htmx/Alpine (no heavy SPA), consistent with the self-contained approach of SpendLens.

## 11. Packs (the "Ops Autopilot" product layer)

Each pack is a spec template with variables, a README, sample data for demo mode, and tests.

| Pack | Detect (Steampipe) | Actions | Gate |
|---|---|---|---|
| **finops-cleanup** | unattached EBS, unused EIPs, old snapshots (aws-thrifty queries, adapted) | Jira ticket per owner tag, Teams notice, optional delete | Approval per batch |
| **tag-enforcement** | resources missing mandatory tags (aws-tags queries) | Notify owner, create Jira task, optional tag fix | Approval for tag writes |
| **security-to-jira** | GuardDuty / Security Hub / Inspector findings above severity | Dedupe by finding id, create Jira issue, page Opsgenie if critical | None for ticket; approval for remediation |
| **incident-copilot** (demo, direction 3) | Opsgenie alert (webhook/query) | Enrich with AWS context (instances, recent CloudTrail changes), recent GitLab deploys/MRs, related Jira issues; post a summary to Teams; attach to alert | Read-only, no gate needed |
| **access-review** (stretch) | IAM users with old keys / no MFA; Entra users | Ticket + notify | Approval |

Reuse: translate the aws-thrifty and aws-tags queries and the detect-and-correct pattern (variables for thresholds,
`default_action`, `enabled_actions`, notifier, approvers) rather than depending on those mods wholesale, so packs share one
config model.

## 12. Integration gap work

Verified from the repos: Jira 10, GitLab 8, Opsgenie 6, Teams 49 pipelines. Needed for the packs and likely missing:

- **Opsgenie**: get alert, add note, acknowledge, close alert; on-call lookup.
- **GitLab**: list deployments/pipelines/merge requests by project and time window (for incident-copilot); create MR comment.
- **Jira**: confirm `search_issue` (JQL) supports dedupe lookups; add label.
- **Teams**: confirm channel message posting (the mod is Microsoft Graph oriented: mail, chats, users); otherwise rely on the Flowpipe Teams integration/notifier for messages.
- **Steampipe plugin coverage**: verify in Phase 0 which plugins exist and are healthy for gitlab, jira, opsgenie and Microsoft Teams/Graph. Where a table is missing, add an `http` read pipeline in a `opslens-mod-extras` mod and mark it in the pipeline catalog as `source=api`.

Contribute new pipelines upstream where licensing and quality allow; otherwise ship them in `opslens-mod-extras` (Apache-2.0).

## 13. Security and safety

- Steampipe DB role read-only; opslens refuses to start `generate` against a role it can't confirm is read-only (best-effort check).
- Secrets only in Flowpipe `.fpc` connection files and env; opslens never stores or logs them; redaction in logs and LLM context (`llm.redact`).
- Prompt-injection: external text fields are fenced in tool results; lint blocks specs where a write step's args come
  directly from free-text columns without passing through an approval gate.
- Webhook triggers (no auth in Flowpipe, URL secret only) disabled by default; if enabled, UI warns and documents a reverse-proxy auth pattern.
- Audit log (SQLite, append-only): request text, model, spec hash, validator results, approver, deploy time, runs.
- Blast-radius caps: max items per run, max write actions per run, configurable.
- Supply chain: pinned plugin and mod versions in `mods.lock`; checksum on shipped catalogs.

## 14. Testing strategy

- **Unit**: catalog parsing, SQL guard (injection corpus), spec model, renderer (golden HCL files), lint rules.
- **Contract**: validate renderer output with the real `flowpipe` binary in CI (load check).
- **Integration**: Steampipe with a local emulator/fixtures (SpendLens tested against an AWS emulator through Steampipe; reuse
  that approach), Flowpipe server in Docker, run a pack end to end with HTTP mocks for Jira/Opsgenie/GitLab/Teams.
- **AI evals**: a fixed set of 30-50 requests with expected specs/properties (right tables, right pipelines, gated writes);
  run on each prompt/model change; track pass rate and tokens. Include adversarial cases (injection in ticket text, request for a destructive action with no approval).
- **Safety tests**: assert no generated mod contains an ungated write, inline secret, container/function step.
- CI: lint (ruff), types (mypy), tests, build Docker image for amd64/arm64.

## 15. Phased delivery

### Phase 0: Spike and decisions (about 1 week)
- Install Steampipe + Flowpipe locally; confirm plugin availability for gitlab, jira, opsgenie, Teams/Graph.
- Confirm the load-check behaviour (does `flowpipe pipeline list` on a broken mod exit non-zero?), the REST run flow (`POST /pipeline/:name/command`), and `GET /pipeline` shape from `/docs/openapi.json`.
- Choose final name and repo; set up CI skeleton.
- **Exit**: a script that loads a hand-written mod, runs it via REST, and reads results; a written list of plugin gaps.

### Phase 1: Catalogs and no-AI CLI (about 2-3 weeks)
- Catalog builders for tables and pipelines; `find`, `describe`, `query` with the SQL guard; `doctor`, `init`, config layering.
- Demo mode with bundled sample data.
- **Exit**: `opslens find tables "unattached volumes"` and `describe pipeline jira.create_issue` work offline and match live schema.

### Phase 2: Spec, renderer, validator, packs (about 3 weeks)
- Spec model, renderer, lint rules, load check, preview variant.
- Deployer + Flowpipe REST client + run tracker + audit store.
- First two packs: `finops-cleanup`, `tag-enforcement`. Add missing Jira/Opsgenie/GitLab pipelines needed.
- **Exit**: `pack install finops-cleanup` -> `validate` -> `preview` -> `deploy` -> approval in Teams/Slack -> action, entirely without AI.

### Phase 3: AI generator (about 3 weeks)
- LiteLLM adapter, agent loop, tools, prompts, sessions, auto-fix loop, `explain`.
- Eval set and CI gate on pass rate.
- **Exit**: eval suite >= 90% pass on the 40 requests, zero ungated writes in any generated output.

### Phase 4: Web UI (about 3 weeks)
- Catalog browser, generate/review/runs views, spec-hash approval.
- **Exit**: a non-CLI user can go from request to deployed, approved pipeline.

### Phase 5: Packs, demo, and launch (about 3 weeks)
- `security-to-jira`, `incident-copilot` (the demo), docs site (mirror SpendLens website), Docker image, install script, examples and a recorded demo.
- Licensing review, security review, CONTRIBUTING, issue templates, versioned release.

Rough total: 15-17 weeks for one engineer; Phases 3 and 4 can overlap with two.

## 16. Success metrics

- Time from request to a validated, previewed pipeline < 5 minutes in the demo scenarios.
- Eval pass rate >= 90%; 0 ungated writes in generated mods (hard gate).
- >= 5 packs working end to end against the emulator and mocks.
- Catalog coverage: 100% of tables for the v1 plugins; 100% of pipelines in the v1 mods with typed params.
- Token cost per `generate` tracked and below a set budget; repeat work possible with no AI via packs.

## 17. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Flowpipe/Steampipe license (AGPL) | Process boundary only, no vendoring, licensing review before release |
| Invalid or unsafe generated HCL | Spec-first generation, renderer templates, load check, lint, preview, hash-approved deploy |
| Missing Steampipe plugins or thin mods | Phase 0 audit; `opslens-mod-extras` with `http` pipelines; mark source in the catalog |
| No official validate/dry-run | Own validator (load check + preview variant); verify behaviour in Phase 0 |
| Flowpipe API changes | Generate the client from `/docs/openapi.json`; pin Flowpipe version; contract tests in CI |
| Prompt injection via tickets/alerts | Data fencing, lint on free-text-to-write paths, approvals |
| Upstream project direction (Turbot) | Keep to documented HCL and REST; keep packs as plain mods usable without opslens |
| Alert/query-trigger noise or runaway loops | Item caps, schedule minimums, per-run write caps, disable-all kill switch |

## 18. Open items to resolve in Phase 0

1. Final name and domain/org for the repo and Docker image.
2. Steampipe plugin availability for Opsgenie and Teams; exact table names.
3. Load-check exit-code behaviour; whether generated mods can be loaded without installing dependencies each time (cache `.flowpipe/mods`).
4. How the REST API reports a paused run (waiting for input) and how to link to the approval form (`/form/:id/:hash`).
5. Embedding-based catalog search: needed or are synonyms plus keywords enough (SpendLens suggests the latter is fine)?
6. Hosting of catalogs: ship in the wheel, or fetch versioned releases?
