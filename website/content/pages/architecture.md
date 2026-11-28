# Architecture

How opslens is put together and why it is safe, as C4 diagrams (context, containers, components) and sequence diagrams of the flows that matter. The idea in one sentence: **a requirement becomes a small reviewed spec, a deterministic renderer turns the spec into a Flowpipe pipeline, and nothing that changes state runs until a person approves the exact spec they read.**

## Level 1: system context

Who uses opslens and what it talks to.

[[diagram:c4_context]]

- The **ops engineer** describes the need, reviews the result and approves changes. There is no other actor.
- **Steampipe** is the read path: the `detect` query is SQL against its tables. Credentials for it are yours and read-only where you can make them so.
- **Flowpipe** is the act path: it schedules, runs the pipelines, calls the services and asks for approval.
- The **AI model is optional**. It sees catalog names and your (scrubbed) sentence, never your data or credentials.

## Level 2: containers

The runnable parts. opslens itself is one Python package with two front doors; Steampipe and Flowpipe are separate, unmodified programs it talks to over their normal interfaces (a Postgres connection and a REST API).

[[diagram:c4_containers]]

| Container | Technology | Responsibility |
|---|---|---|
| **CLI** | Typer | Every operation, scriptable, with exit codes for CI |
| **Web app** | FastAPI and a static UI | The visual builder; local, team (sign-in, audit actor) and demo (sample data, no writes) modes |
| **Core library** | Python | Everything below; the CLI and web app contain no logic of their own |
| **AI planner** | Provider adapters | Optional; prompt, call, validate, retry |
| **Workspace** | Files on disk | `spec.yaml`, generated `.fp` files, the audit log |
| **Steampipe** | Separate program | Plugins call the cloud and SaaS APIs and expose them as SQL |
| **Flowpipe** | Separate program | Runs pipelines and triggers, serves the approval form |

## Level 3: components of the core library

[[diagram:c4_components]]

| Component | Why it exists |
|---|---|
| **Catalogs** | 670 tables and 443 pipelines, built offline from the plugin source and the Flowpipe library, so search and validation never rely on a model's memory |
| **Spec model and validator** | The small typed YAML. The validator checks real columns, typed arguments, and that **every change is gated** |
| **SQL guard** | Parses the query (sqlglot): one `SELECT`, only catalog tables, a timeout and a row cap |
| **Renderer** | Deterministic: can emit only four step kinds, escapes every literal, always puts approval before a change. The hash of the spec ties a deploy to what you read |
| **SQL client** | Live: the Steampipe service. Demo: the same Postgres SQL transpiled to SQLite over sample data |
| **Preview** | Runs the read-only query and shows each action's exact arguments; sends nothing |
| **Flowpipe client** | Starts one Flowpipe server per automation and runs, approves and stops it |
| **Runs and audit** | An append-only record: every deploy (with the approved hash), run and approval, and who did it in team mode |

## Sequence: from a requirement to an approved change

The whole life of one automation. Everything above the highlighted bands is read-only or files; the first band is where you decide.

[[diagram:seq_lifecycle]]

Two properties come from this order. **Review comes before anything runs**: the preview shows the exact arguments, and the deploy is refused unless you pass the hash of the spec you reviewed. **A change cannot run unattended**: the validator rejects a spec whose change action is not gated, and Flowpipe holds the run at the approval step.

## Sequence: drafting with AI

[[diagram:seq_ai]]

The model fills in the same spec a person would, and its answer goes through the same validator as a template. It cannot write pipeline code because the renderer, not the model, writes the pipeline, and it cannot skip approval because that rule is enforced after the draft, in code. See [AI planner](../docs/ai/) and [Data and privacy](../docs/data-security/) for what is sent.

## Sequence: team mode

[[diagram:seq_team]]

The shared password is checked once, the session cookie is signed, `HttpOnly` and `Secure`, and mutating requests also need a per-session token. Behind an identity proxy, opslens can instead trust the signed-in user's header (only when it also carries a shared secret). See [Host it for your team](../docs/hosting/).

## Design decisions

- **A spec, not generated code.** Twenty lines a person can read, with stable diffs. A bad draft can be wrong, but not unsafe.
- **Two catalogs, built offline.** Validation is exact, and works in a browser with no server.
- **Separate programs.** Steampipe and Flowpipe (AGPL-3.0) are run unmodified over their own interfaces, never linked.
- **No stored credentials.** opslens never holds a cloud credential; it lives in Steampipe and Flowpipe, set up as [Connect your services](../docs/integrations/) describes.
- **No AI required.** Templates, the builder and hand-written specs all produce the same spec.

More detail on each step is in [How it works](../docs/architecture/), and the checks are in the [Safety model](../docs/safety/).
