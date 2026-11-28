# Data and privacy

What is read, what leaves your machine, what is stored, and how to turn each down.

## What opslens reads

- **Catalog metadata** that ships with it: table, column and pipeline names and descriptions. No network needed.
- **Your cloud data**, only when you run a query or a live preview, through the Steampipe connection on your machine, with your own credentials, read-only.
- **Sample data** bundled with opslens, for `--source demo` and the hosted demo.

## What leaves your machine

| When | What | Where to |
|---|---|---|
| Normal use | **Nothing.** opslens has no telemetry and does not phone home | n/a |
| A live query or preview | Calls from Steampipe to your cloud APIs, as it always makes them | AWS, Jira, and so on |
| A deployed run | Calls from Flowpipe to create tickets, post messages and so on | The services you chose |
| `opslens generate` / Draft with AI | Your **sentence** (scrubbed) and the **relevant catalog metadata** | The AI provider you configured |
| Install | Downloads of Flowpipe, Steampipe and plugins | Their official releases (checksum-verified) |

### What the AI provider sees

Only your sentence and public catalog entries (table and column names, pipeline parameters). **Never** your cloud data, ticket text, alert contents, credentials or generated files. See it for yourself:

```bash
opslens generate "..." --show-context
```

With `llm.redact` on (default), email addresses, 12-digit account ids, ARNs and key-like strings are removed from your sentence before it is sent. If you want nothing to leave your machine, use `ollama` or another local server, or don't configure a provider at all.

## What is stored

| What | Where | Notes |
|---|---|---|
| Configuration | `opslens.yaml` | No secrets. Keys are environment variables |
| Generated mods | Your workspace folder (`generated/` by default) | Plain text you can read and version |
| Deploy state and the audit log | `.opslens/<mod>/` in the workspace | Local SQLite, append-only |
| API keys, cloud credentials | **Not stored by opslens** | Environment variables; Steampipe and Flowpipe's own config |

## The hosted demo

The public demo at `/app/` runs on a small server with **sample data only**. It cannot reach any cloud account, cannot save, deploy or run anything, has no AI, and limits input size and request rate. What you type into it (a query, a spec) is processed in memory to answer you and is not stored.

## Your responsibilities

- Run the local app on your own machine; it refuses to bind to a non-loopback address. To share it, use the demo mode instead.
- Give Steampipe **read-only** credentials where you can. opslens is read-only by construction, but least privilege is still the right default.
- Treat generated mods like any other infrastructure code: review, version, and keep secrets out.
