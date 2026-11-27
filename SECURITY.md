# Security

opslens runs read-only SQL and can, when you approve it, trigger state-changing pipelines, so its guard rails matter. See
[docs/safety.md](docs/safety.md) for the model: the SQL guard, approval gates, spec-hash deploys, and what the AI planner can and
cannot do.

**Reporting a vulnerability:** please use GitHub's private reporting
(Security tab, "Report a vulnerability") rather than a public issue. Include the version (`opslens --version`), what you did and
what you expected. Reports about bypassing the SQL guard, the approval gate or the web app's token/Host protections are the most
valuable.

Supported: the latest release.
