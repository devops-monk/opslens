# Configuration

> This page is for opslens's own settings. To give opslens access to **Jira, Teams, Slack, GitLab, Opsgenie or AWS**, see [Connect your services](../integrations/).

opslens works with no configuration at all. Everything has a default; change only what you need.

## Where settings come from

Later sources win:

1. Built-in defaults
2. `opslens.yaml` in the current directory (or `--config path`)
3. Environment variables named `OPSLENS__SECTION__KEY`
4. `--set section.key=value` on the command line (repeatable)

```bash
opslens init                                    # writes a commented opslens.yaml with every default
opslens params                                  # every setting, its value, where it came from, and its env var
opslens params --filter llm                     # just the AI settings
opslens config                                  # the merged result as YAML
opslens query "select 1" --set steampipe.port=9194
```

## Settings

| Setting | Default | Environment variable | What it does |
|---|---|---|---|
| `steampipe.host` / `port` | `localhost` / `9193` | `OPSLENS__STEAMPIPE__HOST` / `__PORT` | Where the Steampipe service listens |
| `steampipe.database` / `user` | `steampipe` | `OPSLENS__STEAMPIPE__DATABASE` / `__USER` | Connection details |
| `steampipe.password` / `dsn` | none | `OPSLENS__STEAMPIPE__PASSWORD` / `__DSN` | Password, or a full connection string |
| `steampipe.statement_timeout_s` | `60` | `OPSLENS__STEAMPIPE__STATEMENT_TIMEOUT_S` | Per-query timeout, enforced by the database |
| `steampipe.max_rows` | `1000` | `OPSLENS__STEAMPIPE__MAX_ROWS` | Row cap for queries (results are flagged when truncated) |
| `flowpipe.url` | `http://localhost:7103` | `OPSLENS__FLOWPIPE__URL` | Flowpipe's REST API |
| `flowpipe.binary` | `flowpipe` | `OPSLENS__FLOWPIPE__BINARY` | The Flowpipe executable |
| `flowpipe.workspace_dir` | `generated` | `OPSLENS__FLOWPIPE__WORKSPACE_DIR` | Where generated mods are written and saved |
| `catalog.plugins` | all | `OPSLENS__CATALOG__PLUGINS` | Limit search to some plugins |
| `catalog.default_results` | `8` | `OPSLENS__CATALOG__DEFAULT_RESULTS` | How many hits search shows |
| `llm.provider` | `none` | `OPSLENS__LLM__PROVIDER` | The [AI provider](../ai/); `none` keeps AI off |
| `llm.model` / `base_url` | provider default | `OPSLENS__LLM__MODEL` / `__BASE_URL` | Model name; endpoint for OpenAI-compatible servers |
| `llm.api_key_env` | provider default | `OPSLENS__LLM__API_KEY_ENV` | Name of the variable that holds the key |
| `llm.effort` | `high` | `OPSLENS__LLM__EFFORT` | Reasoning effort, for models that support it |
| `llm.fallback` | `true` | `OPSLENS__LLM__FALLBACK` | Anthropic only: let the API fall back if a model refuses |
| `llm.max_attempts` | `3` | `OPSLENS__LLM__MAX_ATTEMPTS` | Validation-feedback rounds before giving up |
| `llm.redact` | `true` | `OPSLENS__LLM__REDACT` | Scrub emails, account ids, ARNs and keys from the request before it leaves your machine |

## Secrets

**API keys are read from environment variables only, never from a config file.** `llm.api_key_env` names the variable; the key itself is never written anywhere by opslens. Cloud credentials belong to Steampipe and Flowpipe (their own config files and the standard provider environment variables). opslens never stores them and refuses any spec that has something secret-looking inline.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | error |
| 2 | bad settings or usage |
| 3 | query refused by the safety guard |
