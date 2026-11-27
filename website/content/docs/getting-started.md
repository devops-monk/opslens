# opslens docs

opslens turns a plain-English ops requirement into a Flowpipe pipeline you can read, review and approve. It works fully offline with no AI. An AI planner is optional and arrives in a later release.

## Install

One command for macOS and Linux. It installs Flowpipe, Steampipe, the five plugins (pinned, checksum-verified) and opslens itself, in your home directory, without sudo, and never touches your cloud credentials:

```bash
curl -fsSL https://opslens.devops-monk.com/install.sh | sh
```

Want to read it first? That is the better habit:

```bash
curl -fsSLO https://opslens.devops-monk.com/install.sh
less install.sh
OPSLENS_DRY_RUN=1 sh install.sh     # prints what it would do, changes nothing
sh install.sh
```

Options are environment variables: `OPSLENS_EXTRAS="ai web"` adds the AI planner and the web app, `OPSLENS_SKIP_ENGINES=1` installs only opslens, `OPSLENS_PLUGINS="aws jira"` limits the plugins.

Other ways:

```bash
pip install opslens                        # Python 3.11+, once published to PyPI
docker run --rm abhaypratap/opslens doctor # Flowpipe, Steampipe and plugins included
```

Then check your setup:

```bash
opslens init      # writes opslens.yaml
opslens doctor    # checks Steampipe, Flowpipe and plugins
```

## Find what you need

```bash
opslens search "unattached ebs volumes, then open a jira ticket and post to teams"
opslens describe table aws_ebs_volume
opslens describe pipeline jira.create_issue
opslens query "select volume_id, size from aws_ebs_volume where state = 'available'" --source demo
```

`--source demo` uses built-in sample data, so you can try everything without credentials.

## Use a pack

```bash
opslens pack list
opslens pack install finops-cleanup/unattached-volumes --var jira_project=INFRA
opslens validate generated/unattached_volume_cleanup
opslens preview  generated/unattached_volume_cleanup --source demo
```

A preview shows how many items match and what each action would do. Nothing runs.

## Deploy and run

```bash
opslens deploy generated/unattached_volume_cleanup          # shows what you are approving and its hash
opslens deploy generated/unattached_volume_cleanup --approve <hash>
opslens run     generated/unattached_volume_cleanup
opslens approve generated/unattached_volume_cleanup <execution-id> --choice approve
opslens runs    generated/unattached_volume_cleanup         # audit log
```

## Use AI (optional)

Everything above works without AI. If you want a model to draft the spec from a sentence, pick any provider:

```bash
# Anthropic (default model claude-opus-5-5)
export ANTHROPIC_API_KEY=...
opslens generate "find unattached EBS volumes older than 30 days, open a Jira ticket for each, delete them after approval" \
  --set llm.provider=anthropic

# OpenAI, GLM (Z.ai), OpenRouter, a local Ollama, or any OpenAI-compatible server: name the model
export OPENROUTER_API_KEY=...
opslens generate "..." --set llm.provider=openrouter --set llm.model=<model>
opslens generate "..." --set llm.provider=glm --set llm.model=<model>          # key in $ZAI_API_KEY
opslens generate "..." --set llm.provider=ollama --set llm.model=<model>       # no key
opslens generate "..." --set llm.provider=openai_compatible --set llm.base_url=http://gpu:8000/v1 --set llm.model=<model>
opslens generate "..." --set llm.provider=litellm --set llm.model=bedrock/<id>  # also azure, gemini... (pip install litellm)
```

The model only ever sees your sentence and public catalog metadata (table and column names, pipeline parameters), never your cloud data or credentials. Emails, account ids, ARNs and key-like strings are scrubbed first. `--show-context` prints exactly what would be sent.

The model fills in a spec; it never writes pipeline code. The result goes through the same validator as the packs, and validation errors are sent back to the model for up to three attempts. `auto_apply` is forced off, so anything that changes state still waits for your approval. Read it with `opslens explain <mod>`, then `preview` and `deploy` as usual.

## Web app

```bash
pip install 'opslens[web]'
opslens serve                 # http://127.0.0.1:8077, the full workflow on your machine
```

Three tabs: **Find** (search tables and pipelines), **Build** (start from a pack or write a spec, checked as you type, preview on sample or live data, draft with AI if a provider is configured) and **Mods** (save, deploy, run, answer approvals, read the audit log). Deploying still needs the exact spec hash you reviewed.

Local mode binds to loopback only, rejects unknown Host headers, and requires a per-session token on every state-changing call. `opslens serve --mode demo` is the public variant: sample data only, nothing saved, deployed or run, no AI, input limits and rate limiting.

## Exit codes

| code | meaning |
|---|---|
| 0 | ok |
| 1 | error |
| 2 | bad settings or usage |
| 3 | query refused by the safety guard |
