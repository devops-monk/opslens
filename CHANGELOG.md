# Changelog

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
