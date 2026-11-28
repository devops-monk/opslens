# How it works

opslens sits between a requirement and Flowpipe. Everything before deploy is files and read-only queries you can inspect; nothing before the approval can change a resource.

<div class="arch">
<div class="stage"><span class="n">1</span><div><b>Describe</b><p>Pick a template, build it in the visual builder, or write a sentence (optionally drafted by an AI). All three produce the same thing: a spec.</p></div></div>
<div class="stage"><span class="n">2</span><div><b>Spec</b><p>A small typed YAML file: a trigger, one read-only query, and the actions to take per row. The source of truth, and what the deploy hash covers.</p></div></div>
<div class="stage side"><span class="n">3</span><div><b>Validate</b><p>Against two catalogs (670 tables, 443 pipelines) and the safety rules: the SQL guard, real columns for every placeholder, typed arguments, <em>changes must wait for approval</em>, no inline secrets.</p></div></div>
<div class="stage"><span class="n">4</span><div><b>Render</b><p>A deterministic generator writes the Flowpipe mod (HCL). Every literal is escaped. Nobody, human or model, writes pipeline code, so whole classes of bad output cannot exist.</p></div></div>
<div class="stage"><span class="n">5</span><div><b>Preview</b><p>Run the query read-only on sample or live data and show every action's exact arguments. Nothing is sent. This is where you review.</p></div></div>
<div class="stage gate"><span class="n">6</span><div><b>Deploy: you approve the spec hash</b><p>One Flowpipe server per automation. The deploy is refused unless you pass the hash of the spec you reviewed.</p></div></div>
<div class="stage"><span class="n">7</span><div><b>Run</b><p>On a schedule or on demand: Steampipe finds the rows; Flowpipe runs the actions. Tickets and messages go out; <em>changes pause at the approval step</em>.</p></div></div>
<div class="stage gate"><span class="n">8</span><div><b>Approve, then change</b><p>A person answers in the browser, the terminal or the app. Only then do the gated actions run.</p></div></div>
<div class="stage"><span class="n">9</span><div><b>Audit</b><p>An append-only log of every deploy (with the approved hash), run and approval.</p></div></div>
</div>

## The pieces

| Piece | Role | Notes |
|---|---|---|
| **Steampipe** | Turns cloud and SaaS APIs into SQL tables | Plugins for AWS, Jira, Microsoft 365, GitLab, Opsgenie. Cross-plugin joins work, which the [incident copilot](../use-cases/) uses |
| **Flowpipe** | Runs pipelines: query, call, wait for input, send a message | Provides triggers, the approval form and the REST API |
| **opslens** | The part between: catalogs, the spec, validation, rendering, preview, deploy, the app and the optional AI | Python; Apache-2.0 |

Steampipe and Flowpipe are separate, unmodified programs (AGPL-3.0). opslens talks to them over their normal interfaces, a Postgres connection and a REST API, and never links to them.

## Why a spec instead of generated code

The obvious design is "have a model write the pipeline". opslens deliberately doesn't:

- **Reviewability.** A spec is twenty lines a person can read. Pipeline HCL is not.
- **Safety by construction.** The renderer can only emit four kinds of step, escapes every literal and always puts an approval in front of a change. A bad draft can be *wrong* but not *unsafe*.
- **Stable diffs.** Same spec, same output. The hash a deploy is tied to means something.
- **No AI needed.** Templates, the builder and hand-written specs all produce the same spec.

## Where the intelligence lives

The **catalogs** are what make search, validation and drafting good. They are built offline from the Steampipe plugin source and the Flowpipe library (parsed with Flowpipe's own parser, so parameter types and enums are what Flowpipe will enforce), and shipped in the package. That is why search works in your browser with no server, and why a model is never asked to remember a table name.

## What the generated mod looks like

```
generated/unattached_volume_cleanup/
├── spec.yaml        the source of truth (edit this)
├── mod.fp           the Flowpipe mod definition
├── pipelines.fp     detect, per-row actions, approval
├── triggers.fp      the schedule (off until you enable it)
└── README.md        what it does and its hash
```

Everything but `spec.yaml` is generated, and `opslens validate` fails if it drifts.
