# Safety model

opslens is built so that a wrong guess, by a person or a model, cannot change anything in your accounts.

## Reads

1. **SQL guard.** Every query is parsed (with sqlglot) and accepted only if it is exactly one `SELECT`, `WITH` or `UNION`. Refused: every DML and DDL statement, `COPY`, `SET`, `PRAGMA`, `ATTACH`, transactions, `SELECT ... INTO`, file and network functions (`pg_read_file`, `dblink`, `lo_import`, and so on), `pg_sleep`, stacked statements, and reads of `information_schema`, `pg_catalog` and `steampipe_internal`.
2. **Catalog allow-list.** Unless you pass `--any-table`, every table in a query must exist in the catalog. A hallucinated or misspelled table is refused with a pointer to `opslens find tables`.
3. **Connection limits.** Live connections set `default_transaction_read_only = on` and a `statement_timeout`; results are capped at `steampipe.max_rows` and flagged when truncated.

The guard is a fast, explainable "no", not the only protection: layers 2 and 3 hold even if the parser were bypassed.

## Changes

Each catalogued pipeline has an **effect**: `read`, `notify` (additive: a ticket, an alert, a message) or `change`. The classification is conservative: a pipeline is `read` only if its name starts with a read verb and it has no mutating step; everything else, including every `detect_and_correct_*`, is a write.

- A `change` step **must** be gated behind an approval, or the spec does not validate.
- `auto_apply` (changes with no approval) exists for completeness, is flagged at review, and is forced **off** for AI-drafted specs.
- `detect.max_items` caps how many rows one run can act on.
- Schedules tighter than 5 minutes are refused (runaway-loop protection).

## What you reviewed is what runs

- A deploy requires `--approve <spec hash>` for the exact spec you read; change one character and the hash changes.
- `validate` fails if a generated file no longer matches `spec.yaml`, so a hand edit to generated code is noticed.
- Every literal that reaches generated code is escaped; a value from your data cannot become pipeline code.
- The renderer emits only `pipeline`, `query`, `input` and `message` steps: no `container` or `function` steps.

## Secrets

Credentials live in Flowpipe and Steampipe configuration. A spec argument named like a secret (token, password, key, credential) that carries a value is refused (`inline-secret`). AI provider keys are read from environment variables only.

## Data is never instructions

Text from tickets, alerts and resource names is **data**. It is substituted into message text as a value; it is never interpreted as instructions or as code, and a free-text column cannot turn a read into a change, because every change waits for a person regardless.

## The web app

| Protection | Local | Public demo |
|---|---|---|
| Bind address | Loopback only (refuses otherwise) | Any, behind your proxy |
| `Host` header allow-list (anti DNS-rebinding) | Yes | Yes |
| Per-session token on every state-changing call | Yes | n/a (no state-changing calls) |
| Save, deploy, run, approve | Yes | **403** |
| AI | If configured | **Off** |
| Live data | Yes | **Never** |
| Input size limits and a SQL guard | Yes | Yes |
| Rate limit | n/a | 120 requests/min per client |
| UI inserts dynamic text as text, never HTML | Yes | Yes |

## Reporting a problem

Please use GitHub's [private vulnerability reporting](https://github.com/devops-monk/opslens/security/advisories/new) for anything security-sensitive, and ordinary [issues](https://github.com/devops-monk/opslens/issues) for everything else. Reports about bypassing the SQL guard, the approval gate or the web app's token and Host protections are the most valuable.
