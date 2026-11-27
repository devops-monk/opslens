# Safety model

opslens is built so that a wrong guess, by a person or a model, cannot change anything in your accounts.

## Layers (reads)

1. **SQL guard** (`opslens.sql.guard`): parses with sqlglot and accepts exactly one `SELECT`/`WITH`/`UNION`.
   Refused: every DML/DDL statement, `COPY`, `SET`, `PRAGMA`, `ATTACH`, transactions, `SELECT ... INTO`, file and
   network functions (`pg_read_file`, `dblink`, `lo_import`, ...), `pg_sleep`, stacked statements, and reads of
   `information_schema`, `pg_catalog` and `steampipe_internal`.
2. **Catalog allow-list**: unless you pass `--any-table`, every table in the query must exist in the catalog. A
   hallucinated or misspelled table is refused with a pointer to `opslens find tables`.
3. **Connection limits**: live connections set `default_transaction_read_only = on` and a `statement_timeout`; results
   are capped at `steampipe.max_rows` and flagged when truncated.

The guard is a fast, explainable "no", not the only protection: layers 2 and 3 hold even if the parser is bypassed.

## Writes (Phase 2 onward)

Each catalogued pipeline carries `risk: read | write`. The classification is conservative: a pipeline is `read`
only when its name starts with a read verb (`list_`, `get_`, `search_`, ...) and has no mutating step; everything else,
including every `detect_and_correct_*`, is `write`. Generated pipelines will be rejected unless every `write` step sits
behind an approval (`input`) step, secrets stay in Flowpipe connections (never inline), and `container`/`function`
steps are not emitted.

## Data is never instructions

Text from tickets, alerts and resource names is treated as data. The planner (Phase 3) fences it in tool results, and
the validator rejects specs where free-text columns flow into a write step without an approval gate.

## Reporting a problem

Open an issue at https://github.com/devops-monk/opslens/issues. For anything security-sensitive, say so in the title
without details and a maintainer will follow up privately.
