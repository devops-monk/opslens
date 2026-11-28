# Connect your services

How to give opslens access to Teams, Slack, Jira, GitLab, Opsgenie and AWS, and how to check each connection works before you rely on it.

## Two sides, two sets of credentials

An automation has two halves, and each is a separate program with its own credentials. opslens stores neither.

| Half | Program | What it does | Where its credentials live |
|---|---|---|---|
| **Read** (the `detect` query) | Steampipe plugins | Looks up rows: instances, issues, alerts, projects | `~/.steampipe/config/<plugin>.spc`, or the plugin's environment variables |
| **Act** (the `actions`) | Flowpipe library mods | Posts a message, opens a ticket, tags a resource | `~/.flowpipe/config/<service>.fpc`, or the mod's environment variables |

A service you both read from and write to (Jira, GitLab, Opsgenie) needs **both**. A service you only post to (Slack) needs only the Flowpipe side. A service you only read (the AWS plugin for most reports) needs only the Steampipe side.

Two rules apply everywhere:

- **Secrets never go in a spec.** opslens refuses an inline secret, and a spec is meant to be shared. Put them in environment variables or a `.spc`/`.fpc` file.
- **Start read-only.** Use a read-only credential for the Steampipe side, and a token that can only do what the automation needs for the Flowpipe side.

Environment variables are the simplest route and the only practical one in a container. Set them **before** the program starts: Steampipe reads them when its service starts, and Flowpipe when `opslens deploy` starts its server. If you change one, restart (`steampipe service restart`, then deploy again).

## Check everything first

```bash
opslens doctor
```

shows which tools and plugins are installed, and whether Docker is available (needed for AWS actions only). To test a Steampipe credential, run a one-row query; to test a Flowpipe credential, run one read-only action. Each service below shows both.

```bash
opslens query "select 1 as ok from jira_issue limit 1"      # reads through Steampipe, needs steampipe service start
```

## Microsoft Teams

The Teams mod sends messages through the Microsoft Graph API with an **access token**.

**Act (post a message).** Give the Teams mod one of:

```bash
export TEAMS_ACCESS_TOKEN="eyJ0eXAi..."
```

or a credential file, `~/.flowpipe/config/teams.fpc`:

```hcl
credential "teams" "default" {
  access_token = "<access_token>"
}
```

**What kind of token.** Sending a channel message needs the Graph permission `ChannelMessage.Send` as a **delegated** permission, which means a token issued on behalf of a signed-in work or school user. Microsoft's own documentation says application (app-only) permissions are not available for sending a channel message, only for migration, and personal Microsoft accounts are not supported. Listing teams needs `Team.ReadBasic.All`.

**Important limit: tokens expire.** A Microsoft access token lasts roughly 60 to 90 minutes by default. A static `TEAMS_ACCESS_TOKEN` is therefore good for trying an automation and for on-demand runs, but a **scheduled** automation will start failing with `401 Unauthorized` once the token expires. For unattended use you need something that refreshes the token and updates the variable or the `.fpc` file before each run, or you can post to Slack instead (a Slack bot token does not expire unless you turn on token rotation). `az account get-access-token --resource-type ms-graph` prints a Graph token for the signed-in Azure CLI user; check its scopes first (the `scp` claim) because it only carries what the Azure CLI app was granted.

**Find the ids.** Posting needs a `team_id` and a `channel_id`. With a working token, from a folder whose `mod.fp` uses the Teams mod (any deployed mod that posts to Teams):

```bash
flowpipe pipeline run teams.pipeline.list_teams
flowpipe pipeline run teams.pipeline.list_channels --arg team_id=<team id>
```

Put the two ids into the automation's `teams_team_id` and `teams_channel_id` variables (the templates ship them as `CHANGE-ME`; validation warns until you set them).

**Read (look up teams and users).** The `microsoft365` Steampipe plugin uses an app registration, in `~/.steampipe/config/microsoft365.spc`:

```hcl
connection "microsoft365" {
  plugin        = "microsoft365@1.3.0"
  tenant_id     = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
  client_id     = "YYYYYYYY-YYYY-YYYY-YYYY-YYYYYYYYYYYY"
  client_secret = "ZZZZZZZZZZZZZZZZZZZZZZZZ"
}
```

Without these it falls back to Azure CLI sign-in. Then `opslens query "select id, display_name from microsoft365_team"` lists your teams and their ids.

**Check.** A wrong or expired token fails like this, which is how you know the call reached Microsoft:

```text
Error: Unauthorized
401 Unauthorized
```

## Slack

**Act.** One token, from a Slack app you create at api.slack.com/apps:

```bash
export SLACK_TOKEN="xoxb-..."
```

or `~/.flowpipe/config/slack.fpc`:

```hcl
connection "slack" "default" {
  token = "xoxb-..."
}
```

Name the connection `default` so actions use it without a `conn` argument (Flowpipe's convention); give it any other name and an action must name it with `--arg conn=connection.slack.<name>`.

**What the app needs.** A bot token (`xoxb-`) with the `chat:write` scope can post. Invite the bot to a private channel (`/invite @yourbot`), or add `chat:write.public` to post to public channels it has not joined. Use the channel name or id in the automation's `channel` argument.

**Even simpler: an incoming webhook.** `slack.post_message_to_webhook` needs only a webhook URL and a text, and no token. A webhook URL is a secret, so keep it in a variable you set at deploy time, not in a shared spec.

**Check.** From a mod folder that uses the Slack mod:

```bash
flowpipe pipeline run slack.pipeline.get_current_user
```

A bad token answers `invalid_auth`; no token at all answers `not_authed`. Both mean Flowpipe reached Slack and Slack refused the credential.

## Jira

Jira has different variable names on its two sides. This trips people up.

| Side | Variables |
|---|---|
| Act (Flowpipe) | `JIRA_URL`, `JIRA_USER`, `JIRA_API_TOKEN` |
| Read (Steampipe) | `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN` |

```bash
export JIRA_URL="https://your-domain.atlassian.net/"
export JIRA_USER="you@company.com"
export JIRA_API_TOKEN="ATATT3..."     # for actions
export JIRA_TOKEN="ATATT3..."         # the same token, for the Steampipe plugin
```

Create the token in your Atlassian account under security, API tokens. Or use files. Flowpipe, `~/.flowpipe/config/jira.fpc`:

```hcl
connection "jira" "default" {
  base_url  = "https://your-domain.atlassian.net/"
  username  = "you@company.com"
  api_token = "ATATT3..."
}
```

Steampipe, `~/.steampipe/config/jira.spc`:

```hcl
connection "jira" {
  plugin   = "jira@2.0.5"
  base_url = "https://your-domain.atlassian.net/"
  username = "you@company.com"
  token    = "ATATT3..."
}
```

The account must be able to create issues in the project your automation names (`jira_project`). **Check:** `opslens query "select key, summary from jira_issue limit 3"`.

## GitLab

One token works for both sides. Create a personal access token with `read_api` for reading; actions that change things (creating issues, updating a project) need `api`.

```bash
export GITLAB_TOKEN="glpat-..."
export GITLAB_ADDR="https://gitlab.company.com/api/v4"     # self-managed only, Steampipe side
```

or `~/.flowpipe/config/gitlab.fpc`:

```hcl
connection "gitlab" "default" {
  token = "glpat-..."
}
```

and, for a self-managed server, `~/.steampipe/config/gitlab.spc` with `baseurl` and `token`. **Check:** `opslens query "select full_path, visibility from gitlab_project limit 3"`.

## Opsgenie

Create API keys under Settings, API key management. Alerts and incidents use separate keys.

| Side | Setting |
|---|---|
| Act (Flowpipe) | `OPSGENIE_ALERT_API_KEY`, `OPSGENIE_INCIDENT_API_KEY`, or `connection "opsgenie" "default" { alert_api_key = ...  incident_api_key = ... }` in `~/.flowpipe/config/opsgenie.fpc` |
| Read (Steampipe) | `token` (and `url`, which must be `api.eu.opsgenie.com` for an EU account) in `~/.steampipe/config/opsgenie.spc` |

**Check:** `opslens query "select message, priority from opsgenie_alert limit 3"`.

## AWS

**Read.** The Steampipe AWS plugin uses the standard AWS credential chain, exactly like the AWS CLI: environment variables, a profile, or an instance role. Nothing opslens-specific is needed, and a read-only policy such as `ReadOnlyAccess` or `SecurityAudit` is enough for the templates' queries.

```bash
export AWS_PROFILE=my-profile            # or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

**Act.** The Flowpipe AWS mod reads `AWS_PROFILE`, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or a connection in `~/.flowpipe/config/aws.fpc`:

```hcl
connection "aws" "aws_profile" {
  profile = "my-profile"
}

connection "aws" "aws_access_key_pair" {
  access_key = "AKIA..."
  secret_key = "dP+C+J..."
}
```

**AWS actions need Docker.** Unlike every other service here, the AWS mod runs the AWS CLI inside a container. So any automation with an `aws.*` action (stopping instances, deleting volumes, tagging, closing a security group, and so on; 10 of the 32 templates) needs a **running Docker daemon** where Flowpipe runs. `opslens doctor` reports it. Reading AWS data does not need Docker, and neither do the Teams, Slack, Jira, GitLab and Opsgenie actions.

This matters for the [team Docker image](../hosting/): it has no Docker daemon inside, so AWS actions cannot run in it as shipped. Reading AWS, previews, and every non-AWS action work. To run the AWS actions, run opslens on a host that has Docker ([the installer or pip](../install/)), and treat giving a container the host's Docker socket as a privileged setup you test for yourself.

## ipstack (IP lookup)

Look up an IP address, or the caller's own address. Act side only: `IPSTACK_ACCESS_KEY`, or `~/.flowpipe/config/ipstack.fpc`:

```hcl
connection "ipstack" "default" {
  access_key = "<your ipstack access key>"
}
```

The mod calls `http://api.ipstack.com`, plain HTTP, so use a key you can rotate. A bad key answers `401 Unauthorized`. A worked example is in the [AI guide](../ai/#bonus-find-this-machines-public-ip-with-the-ipstack-mod). The `abuseipdb`, `ip2locationio` and `ipstack` mods work the same way for reputation and location lookups.

## Make a connection once, use it everywhere

Everything above is configured once per machine or container, not per automation. After that, any [template](../packs/) or [AI-drafted spec](../ai/) that uses the service just works, and the [Actions reference](../actions/) lists every action you can use with it.

## When it fails

| You see | It means |
|---|---|
| `401 Unauthorized` from a Teams action | The token is wrong, or expired (they last about an hour) |
| `invalid_auth` / `not_authed` from Slack | The token is wrong / missing |
| `Unable to initialize the Docker client` | An AWS action ran with no Docker daemon |
| A query returns no rows or "plugin" errors | The Steampipe credential is missing: `steampipe service restart` after setting it |
| Actions fail but queries work | You configured the Steampipe side but not the Flowpipe side (they are separate) |

More in [Troubleshooting](../troubleshooting/).
