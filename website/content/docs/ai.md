# AI planner (optional)

Everything in opslens works without AI. If you would rather describe an automation than build it, an AI model can **draft the spec** for you. It fills in the same small [spec format](../spec/), and the draft goes through exactly the same checks as a template. You read it before anything runs.

## Step by step: connect an AI, then ask it something

This walks the whole path after [installing](../install/): check opslens, give it a model, ask a real question, read the answer, run it. The example is **"find the IP addresses of my running servers"**, which uses nothing but AWS data.

> **Note.** opslens reads the cloud accounts you connect. On its own it answers "which IPs does my AWS account have", which is the version of the question automations care about. For *this computer's* public IP and its location, the [bonus step](#bonus-find-this-machines-public-ip-with-the-ipstack-mod) uses the ipstack Flowpipe mod.

### 1. Check the install

```bash
opslens --version
opslens doctor
```

`doctor` lists each tool with `ok` or a `warn` and the command to fix it. Nothing below needs AI yet, and everything can be tried first on sample data with `--source demo`.

### 2. Pick a provider and set its key

Choose one row of the [providers table](#providers). The key lives in an **environment variable**, never in a file. For Claude:

```bash
pip install "opslens[ai]"            # only if you installed with pip; the installer already includes it
export ANTHROPIC_API_KEY="sk-ant-..."
```

For a local model that never leaves your machine, install [Ollama](https://ollama.com), pull a model, and use `llm.provider=ollama` instead (no key).

### 3. Tell opslens which provider, once

Either pass it each time:

```bash
opslens generate "..." --set llm.provider=anthropic
```

or write it down once, in `opslens.yaml` (`opslens init` creates a commented one):

```yaml
llm:
  provider: anthropic
```

Confirm what opslens will use, and where each value came from:

```bash
opslens params | grep "llm\."
```

`llm.provider` shows `none` until you set it, `llm.max_attempts` is 3 and `llm.redact` is on. With a provider and no `llm.model`, opslens uses the provider's default (Claude Opus 5.5 for `anthropic`); for `openrouter`, `ollama` and the others you name one with `--set llm.model=<model>`.

Without a provider, `opslens generate` stops with `no AI provider is configured` and tells you the setting to add, so a missing step is never silent.

### 4. See what would be sent, before sending anything

```bash
opslens generate "list the public IP addresses of my running EC2 instances" --show-context
```

This prints the instructions, the excerpt of the **catalog** (table and column names) and your sentence after scrubbing, then stops. No request is made. You are checking that nothing private is in it.

### 5. Ask

```bash
opslens generate "every morning, post the public IP address of each running EC2 instance to a Microsoft Teams channel" --dry-run
```

`--dry-run` shows the spec and writes nothing. opslens sends your sentence and the catalog excerpt, validates the model's answer, sends any errors back for another try (at most three), and prints a spec that passed. The wording of a draft differs from model to model. A good one looks like this (written by hand here as an example, not a recording of a model):

```yaml
name: running_instance_ips
title: Public IPs of running EC2 instances
description: Posts the public IP address of every running EC2 instance to Teams each morning.
variables:
  teams_team_id:    {default: CHANGE-ME, description: Microsoft Teams team id to post into.}
  teams_channel_id: {default: CHANGE-ME, description: Microsoft Teams channel id to post into.}
trigger: {kind: schedule, schedule: daily}
detect:
  max_items: 50
  sql: |
    select instance_id, public_ip_address, private_ip_address, region, account_id
    from aws_ec2_instance
    where instance_state = 'running' and public_ip_address is not null
notify: false
actions:
  - pipeline: teams.send_channel_message
    title: Post the address
    args:
      team_id: "{var.teams_team_id}"
      channel_id: "{var.teams_channel_id}"
      message: "{instance_id} in {region} is reachable at {public_ip_address} (private {private_ip_address})."
```

Happy with it? Run the same command without `--dry-run`: it writes the mod into your workspace folder, prints where (the examples below call it `generated/running_instance_ips`) and labels it AI-written. (To try a spec you wrote or saved yourself, skip the AI and use the same files with `validate`, `preview` and `render`.)

### 6. Read it in plain English

```bash
opslens explain generated/running_instance_ips
```

```text
- Public IPs of running EC2 instances: Posts the public IP address of every running EC2 instance to Teams each morning.
- Runs every 24h (the schedule ships switched off until you deploy with --enable-schedule), or on demand.
- Each run queries read-only for rows with: instance_id, public_ip_address, private_ip_address, region, account_id (at most 50 rows).
- For each row, immediately: Post the address (teams.send_channel_message, notify).
- It makes no state changes, so there is no approval step.
```

### 7. Preview on sample data, then on your account

```bash
opslens preview generated/running_instance_ips --source demo
```

```text
╭──────────────── preview: Public IPs of running EC2 instances ────────────────╮
│ 8 item(s) found from demo                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
 instance_id          public_ip_address  private_ip_address  region     account_id
 i-00000000000000001  203.0.113.11       10.0.1.21           us-east-1  222222222222
 i-00000000000000002  203.0.113.12       10.0.2.22           eu-west-1  111111111111
 i-00000000000000003  203.0.113.13       10.0.3.23           us-east-1  222222222222
first 3 of 8 row(s)

1. teams.pipeline.send_channel_message  notify  runs automatically  x 8
   team_id='CHANGE-ME', channel_id='CHANGE-ME', message='i-00000000000000001 in us-east-1 is reachable at 203.0.113.11 (private 10.0.1.21).'
   ...

0 state change(s) would be requested; 0 have been made (this was a preview).
```

(Trimmed and reformatted from the real output; the box-drawing table is plain here.) The addresses above are documentation-range sample data. To see **your** instances, make sure [AWS is connected](../integrations/#aws) and `steampipe service start` is running, then drop `--source demo`. You can also just ask the question, with no automation at all:

```bash
opslens query "select instance_id, public_ip_address, private_ip_address, region
               from aws_ec2_instance where instance_state = 'running'"
```

### Bonus: find *this machine's* public IP with the ipstack mod

The steps above list the IPs in your **cloud account**. To find the public IP of the machine you are on, and where it is, use the Flowpipe [ipstack mod](https://hub.flowpipe.io/mods/turbot/ipstack). Its `lookup_requester_ip_address` action asks the ipstack service who is calling and returns the details. opslens already knows it: `opslens describe pipeline ipstack.lookup_requester_ip_address` shows its parameters (all three are required, and it is a read-only action).

```bash
# 1. a key: create a free ipstack account and copy its access key
export IPSTACK_ACCESS_KEY="<your key>"

# 2. a folder that uses the mod
mkdir my-ip && cd my-ip
flowpipe mod init
flowpipe mod install github.com/turbot/flowpipe-mod-ipstack

# 3. ask
flowpipe pipeline run ipstack.pipeline.lookup_requester_ip_address \
  --arg output_type=json --arg security_module=0 --arg fields=ip,city,country_name
```

`fields` limits what comes back (here the IP, city and country); the result is in the pipeline's `requester_ip_address_details` output. With a wrong key, you get `401 Unauthorized`, which tells you the request reached ipstack and the key was refused. To look up any other address, for example one from the `aws_ec2_instance` query above, use `ipstack.pipeline.lookup_ip_address` and add `--arg ip_address=203.0.113.11`.

Two things to know. The mod calls ipstack over plain `http://` (as far as I know ipstack's free plan is HTTP-only; check their plans), so the key is sent unencrypted: use a key you can rotate. And the `security_module` option needs a paid ipstack plan, so keep it `0`. You can also keep the key in `~/.flowpipe/config/ipstack.fpc` as a `connection "ipstack" "default" { access_key = "..." }`.

### 8. Connect Teams (or Slack), then deploy

The preview sent nothing. To make it post for real, [connect the service](../integrations/#microsoft-teams) and set the two ids, then:

```bash
opslens validate generated/running_instance_ips      # prints the spec hash
opslens deploy generated/running_instance_ips --approve <that hash> --enable-schedule
opslens run generated/running_instance_ips            # run it now, once
```

This automation only reads and posts, so there is no approval step. If an AI draft includes a change (stopping an instance, say), it pauses and waits for you to approve it.

### No AI?

Skip steps 2 to 5. `opslens search "public ip of my ec2 instances"` finds the table (`aws_ec2_instance`) and `opslens describe table aws_ec2_instance` lists its columns, so you can write the spec above yourself, or start from the closest [template](../packs/).

## What the model does, and doesn't

| The model does | The model never does |
|---|---|
| Reads your sentence | Write pipeline code (a deterministic renderer does that) |
| Reads public **catalog metadata**: table and column names, pipeline parameters | See your cloud data, tickets, alerts or credentials |
| Fills in a spec | Skip validation, or approve anything |
| Gets validation errors back and fixes them (up to 3 attempts) | Turn on `auto_apply` (it is forced off) |

## The short version

```bash
export ANTHROPIC_API_KEY=...
opslens generate "find unattached EBS volumes older than 30 days, open a Jira ticket for each, delete them after approval" \
  --set llm.provider=anthropic
```

Set the provider once in `opslens.yaml` (or `OPSLENS__LLM__PROVIDER`) and drop the `--set`. In the [web app](../app/), the box on the Templates tab switches from "Find tables & actions" to **Draft with AI** as soon as a provider is configured.

## Providers

| `llm.provider` | Key variable | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | Default model `claude-opus-5-5`, with adaptive thinking and prompt caching. Needs the `ai` extra |
| `openai` | `OPENAI_API_KEY` | Name a model with `llm.model` |
| `openai_compatible` | `OPENAI_API_KEY` | Any OpenAI-style server: set `llm.base_url` and `llm.model` (vLLM, LM Studio, LocalAI, a gateway) |
| `glm` | `ZAI_API_KEY` | Zhipu / Z.ai |
| `openrouter` | `OPENROUTER_API_KEY` | Any model OpenRouter serves |
| `ollama` | none | Local models at `http://localhost:11434/v1` |
| `litellm` | per provider | Azure, Bedrock, Gemini and more. `pip install litellm` |

```bash
opslens generate "..." --set llm.provider=openrouter --set llm.model=<model>
opslens generate "..." --set llm.provider=ollama --set llm.model=<model>
opslens generate "..." --set llm.provider=openai_compatible --set llm.base_url=http://gpu:8000/v1 --set llm.model=<model>
opslens generate "..." --set llm.provider=litellm --set llm.model=bedrock/<model-id>
```

**API keys come from environment variables only.** They are never read from, or written to, a config file. Use `llm.api_key_env` to name a different variable.

## See what leaves your machine

```bash
opslens generate "..." --show-context
```

prints exactly what would be sent (the system prompt, the catalog excerpt, and your sentence after scrubbing) and stops. With `llm.redact` on (the default), email addresses, 12-digit account ids, ARNs and key-like strings are removed from your sentence first.

## The loop

1. Your sentence and the relevant catalog entries go to the model.
2. It answers with one spec.
3. opslens validates it. If there are errors, they go back to the model: "fix these".
4. After at most `llm.max_attempts` (default 3), you get a validated spec, or a clear failure.
5. You read it: `opslens explain`, then `preview`, then deploy as usual.

```bash
opslens generate "every week, find stopped EC2 instances and open a Jira ticket for each" --dry-run     # show the spec, write nothing
opslens generate "..."                                                                                # write the mod
opslens explain generated/<name>
```

An AI draft is a **suggestion**: it can pick a poor query or a wrong threshold. The checks guarantee it is *safe and well-formed*; only you can say whether it is *what you meant*. The builder labels AI drafts so you remember to read every step.

## Evaluating a model

`evals/planner_cases.yaml` holds requirements with the properties a good spec must have. Run it against any provider to compare models before you rely on one:

```bash
OPSLENS_SYSTEM=1 OPSLENS__LLM__PROVIDER=anthropic .venv/bin/python -m pytest -m system tests/system/test_planner_eval.py
```
