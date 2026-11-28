# Install

One command installs everything on macOS and Linux: opslens, Flowpipe, Steampipe and the five Steampipe plugins, all in your home directory, with no sudo and no changes to your cloud credentials.

## The one-line installer

```bash
curl -fsSL https://opslens.devops-monk.com/install.sh | sh
```

It does, in order:

1. Installs **Flowpipe** and **Steampipe** at pinned versions (through Homebrew when you have it, otherwise release binaries into `~/.local/bin`, each verified against the release's checksums).
2. Installs the **Steampipe plugins** opslens ships catalogs for, at pinned versions: `aws`, `jira`, `microsoft365`, `gitlab`, `opsgenie`.
3. Installs **opslens** in its own isolated environment (pipx, else `uv tool`, else a private virtualenv), so it never touches your other Python projects.

It installs tools only. It never reads your cloud credentials and never calls a cloud API.

### Read it first

That is the better habit for any script you pipe into a shell:

```bash
curl -fsSLO https://opslens.devops-monk.com/install.sh
less install.sh
OPSLENS_DRY_RUN=1 sh install.sh      # prints every command it would run; changes nothing
sh install.sh
```

### Options

Set these as environment variables in front of the command.

| Variable | Effect |
|---|---|
| `OPSLENS_EXTRAS="ai web"` | Also install the AI planner and the web app (`opslens serve`). Recommended |
| `OPSLENS_SKIP_ENGINES=1` | Install only opslens; you manage Flowpipe and Steampipe yourself |
| `OPSLENS_SKIP_PLUGINS=1` | Install the engines but no plugins |
| `OPSLENS_PLUGINS="aws jira"` | Only these plugins (default: all five) |
| `OPSLENS_REF=v0.3.2` | Which release to install (default: the one the script shipped with) |
| `OPSLENS_BIN_DIR=~/.local/bin` | Where binaries go |
| `OPSLENS_PACKAGE=<path or URL>` | Install opslens from this wheel or sdist instead of GitHub |
| `OPSLENS_DRY_RUN=1` | Print, don't run |

```bash
curl -fsSL https://opslens.devops-monk.com/install.sh | OPSLENS_EXTRAS="ai web" sh
```

## Other ways

**pip or pipx** (Python 3.11 or newer). This installs opslens only; add Flowpipe and Steampipe yourself if you want live data and deploys.

```bash
pipx install "opslens[web,ai] @ https://github.com/devops-monk/opslens/archive/v0.3.2.tar.gz"
# once published to PyPI:  pipx install "opslens[web,ai]"
```

**Docker** (opslens, Flowpipe, Steampipe and the plugins are in the image; linux/amd64 and linux/arm64):

```bash
docker run --rm abhaypratap/opslens doctor
docker run --rm -p 8077:8077 abhaypratap/opslens serve --mode demo --host 0.0.0.0 --allow-host localhost
```

**From source:**

```bash
git clone https://github.com/devops-monk/opslens && cd opslens
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## Check it worked

```bash
opslens --version
opslens doctor          # checks opslens, the catalogs, Flowpipe, Steampipe and the plugins; says how to fix what is missing
```

`opslens doctor --offline` skips anything that needs a running service, which is what you want on a laptop with no cloud access yet. You can do everything on [sample data](../quickstart/) without connecting an account.

## Connect your accounts (only when you want live data)

opslens stores no credentials. Each service has two halves, **reading** (a Steampipe plugin) and **acting** (a Flowpipe mod), and each reads its credentials from environment variables or a small config file. Jira, for example:

```bash
export JIRA_URL="https://your-domain.atlassian.net/"
export JIRA_USER="you@company.com"
export JIRA_TOKEN="<atlassian api token>"        # read:  the Steampipe plugin
export JIRA_API_TOKEN="<atlassian api token>"    # act:   the Flowpipe mod (same token, different name)
steampipe service start
opslens doctor
opslens query "select key, summary from jira_issue limit 3"
```

**The full guide, with Jira, Teams, Slack, GitLab, Opsgenie, AWS and ipstack (variables, config files, how to get a token, how to test each, and the errors you will see) is [Connect your services](../integrations/).** AWS uses your normal profile or environment variables.

## Uninstall

Remove `~/.local/bin/{flowpipe,steampipe}` (or `brew uninstall`), then `pipx uninstall opslens` (or `uv tool uninstall opslens`). Mods you generated live in the `generated/` folder you chose and are plain files.
