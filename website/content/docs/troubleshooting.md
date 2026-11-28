# Troubleshooting

Start with `opslens doctor`. It checks opslens, the catalogs, Flowpipe, Steampipe and each plugin, and says how to fix what is missing.

## Install and setup

**`opslens: command not found` after installing.** The installer puts it in `~/.local/bin`. Add that to your `PATH`:
`export PATH="$HOME/.local/bin:$PATH"`, then open a new shell.

**The installer says not to run as root.** Steampipe refuses to run as root. Run it as your normal user. It never needs sudo.

**`steampipe` or `flowpipe` is missing.** Re-run the installer, or install them yourself and rerun `opslens doctor`. `OPSLENS_SKIP_ENGINES=1` means you manage them.

**A plugin is missing or the wrong version.** `steampipe plugin install aws@1.35.0` (or the one `doctor` names). `opslens catalog verify` compares your installed plugins with the catalog.

## Queries

**Exit code 3: "refused".** The [safety guard](../safety/) said no. The message says why: more than one statement, not a `SELECT`, a table that is not in the catalog (check the spelling with `opslens find tables ...`), or a blocked function.

**`SELECT *` is refused in a spec** (`sql-star`). List the columns you need. It is what lets every `{placeholder}` be checked against a real column.

**A query times out or returns too few rows.** Steampipe tables call APIs. Filter on the columns the table marks as fast or required (`opslens describe table <name>`), and raise `steampipe.statement_timeout_s` or `steampipe.max_rows` if you must.

**Live queries fail but demo works.** Steampipe isn't running or a plugin has no credentials. `opslens doctor`, then check the plugin's own credential setup.

## Specs and validation

**`placeholder`: `{x}` is not a column.** Your query doesn't return `x`. Add it to the `SELECT`, or use a variable (`{var.name}`).

**`ungated-write`.** An action that changes things needs `gated: true` (in the builder the approval switch is locked on for these).

**`arg-missing`.** The pipeline has a required parameter you haven't set; the message names it. `opslens describe pipeline <name>` lists them.

**`validate` says a generated file differs from `spec.yaml`.** Someone edited generated code by hand. Change `spec.yaml` and re-render instead; `opslens render --force` regenerates.

## Deploy and run

**Deploy refuses: "spec hash does not match".** The spec changed after you reviewed it. Read it again and pass the new hash from `opslens deploy` (without `--approve`).

**The schedule never fires.** Schedules ship switched off. Deploy with `--enable-schedule`.

**A run is "waiting".** It reached the approval step. Open the approval link that `opslens run` printed, use `opslens approve`, or click Approve in **My automations**.

**A run fails creating a ticket or message.** The connection for that service isn't configured in Flowpipe (or its credentials are wrong). Configure it the Flowpipe way; opslens never stores credentials.

**Port already in use.** Each deployed mod gets its own Flowpipe port, chosen free. For the web app, `opslens serve --port 8078`.

## The web app

**"refusing to bind to a non-loopback address".** By design: the local app holds your credentials' reach and has no sign-in. Use `--mode demo` to share a sandbox, or [team mode](../hosting/) to host the full app with sign-in.

**The page says it cannot reach the API.** `opslens serve` isn't running, or you opened a different port. In a container, add `--host 0.0.0.0 --allow-host localhost`.

**Save, Deploy or Draft with AI is missing.** You are in demo mode, which is read-only by design. Run `opslens serve` locally. AI also needs a configured provider.

## AI

**"no llm provider".** Set `llm.provider` (see [AI planner](../ai/)) and the matching key variable.

**The draft fails validation three times.** The message shows the last errors. Make the request more specific (name the service and the condition), or use a stronger model, or start from a template.

## Connections

- **`401 Unauthorized` from a Teams action.** The access token is wrong or expired (Microsoft tokens last about an hour). See [Connect your services](../integrations/#microsoft-teams).
- **`invalid_auth` or `not_authed` from Slack.** The `SLACK_TOKEN` is wrong or missing.
- **`Unable to initialize the Docker client` on an AWS action.** AWS actions run in a container; start Docker where Flowpipe runs (`opslens doctor` shows it). The Docker image of opslens has no daemon.
- **Queries work but actions fail (or the reverse).** Steampipe and Flowpipe have separate credentials. Jira even uses `JIRA_TOKEN` for one and `JIRA_API_TOKEN` for the other.

## Still stuck

Run `opslens doctor` and `opslens --version`, then [open an issue](https://github.com/devops-monk/opslens/issues) with the output and what you expected.

**"team mode will not start without sign-in".** It needs `--auth password` with `OPSLENS_TEAM_PASSWORD` (12+ characters) or `--auth proxy` with `OPSLENS_PROXY_SECRET`, and `--allow-host <your host name>`. See [Host it for your team](../hosting/).

**Signed in but everything says "host not allowed".** The host name in the browser is not in `--allow-host`. Use the exact name, without a port.

**Automations stopped after a restart.** A deployed automation is a Flowpipe process; it ends with the container. Open *My automations* and deploy it again.
