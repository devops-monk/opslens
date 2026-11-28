# Commands

What you can really do from the terminal. Every command here exists in the installed version (the full list with every option is the [CLI reference](../docs/cli/)). Add `--source demo` to `query` and `preview` to try anything on sample data, with no cloud account.

## The map

Lots of commands, but they follow one journey. Read the picture left to right: you **get ready**, **find** what exists, **ask** a question, get a **plan**, **test** it, then **go live**.

[[diagram:command_map]]

## What the strange words mean

| Word | Plain meaning | Example |
|---|---|---|
| **doctor** | A health check: is everything installed? Tells you the fix for anything missing | `opslens doctor` |
| **connect** | Save the login for a tool (Jira, Teams, Slack, GitLab, Opsgenie, AWS, ipstack) inside opslens, so you never edit other programs' files | `opslens connect jira` |
| **connections** | Show which tools are connected and where each value comes from (never the secret itself). `--test` checks each one | `opslens connections --test` |
| **params** | Short for parameters. Lists every **setting** opslens has, its current value, and where the value came from | `opslens params` |
| **config** | Shows the settings opslens is using right now, as a file | `opslens config` |
| **search / find** | Look things up using plain words, like a search box | `opslens search "unused disks"` |
| **describe** | Show everything about one table or action | `opslens describe table aws_ebs_volume` |
| **query** | Ask a question of your data. It takes SQL (a small question language), not plain words | `opslens query "select ..."` |
| **pack / template** | A ready-made plan someone already wrote | `opslens pack list` |
| **spec** | The plan itself, a short file you can read | `spec.yaml` |
| **generate** | Let an AI write the plan from a sentence (optional) | `opslens generate "..."` |
| **render** | Turn the plan into the files that Flowpipe runs | `opslens render my-spec.yaml` |
| **explain** | Read the plan back in plain words | `opslens explain <folder>` |
| **validate** | Check the plan is correct and safe | `opslens validate <folder>` |
| **preview** | A **pretend run**: shows what would happen and does none of it | `opslens preview <folder>` |
| **deploy** | **Start** the plan so it can run. You must give the plan's fingerprint (hash), so you only start what you read | `opslens deploy <folder> --approve <hash>` |
| **run** | Run it **right now**, once | `opslens run <folder>` |
| **approve** | Answer yes or skip when a run is **waiting** before a change | `opslens approve <folder> <id>` |
| **runs** | The history: what was deployed, run and approved | `opslens runs <folder>` |
| **undeploy** | **Stop** it | `opslens undeploy <folder>` |
| **serve** | Open the **web app**, so you can click instead of type | `opslens serve` |

New to all this? Read [Explained simply](../docs/simple/) first; it walks the same journey with one example.

## Set up and check

```bash
opslens --version                     # which version is installed
opslens doctor                        # tools, plugins, Docker (for AWS actions), and the fix for anything missing
opslens connect jira                  # save a tool's login inside opslens (prompts; secrets are hidden)
opslens connections --test            # which tools are connected, and does each one answer?
opslens disconnect jira               # forget a tool's saved login
opslens init                          # write a commented opslens.yaml with every setting at its default
opslens params                        # every setting, its value, where it came from, and its env variable
opslens config                        # the merged configuration as YAML
opslens catalog stats                 # what the two shipped catalogs contain
opslens catalog verify                # compare the catalog with your installed Steampipe plugins
```

## Find the data and the action

```bash
opslens search "public ip addresses of my ec2 instances"     # tables AND actions for one question
opslens find tables "unattached ebs volumes"                  # only tables
opslens find pipelines "create jira issue"                    # only actions
opslens describe table aws_ec2_instance                       # columns, types, filters, examples
opslens describe pipeline teams.send_channel_message          # typed parameters, outputs, risk, a usage snippet
```

## Ask questions of your cloud

Read-only SQL: a single `SELECT` on catalog tables, with a timeout and a row cap. Nothing here can change anything.

```bash
opslens query "select instance_id, public_ip_address, region from aws_ec2_instance where instance_state = 'running'"
opslens query "select full_path, visibility from gitlab_project where visibility = 'public'" -f csv
opslens query -F report.sql -f json -n 100                    # SQL from a file, JSON out, at most 100 rows
opslens query --source demo "select * from aws_ebs_volume where state = 'available'"
```

Handy questions to start with:

| Question | Query |
|---|---|
| What public IPs do I have? | `select instance_id, public_ip_address, region from aws_ec2_instance where public_ip_address is not null` |
| What is costing money for nothing? | `select volume_id, size, region from aws_ebs_volume where state = 'available'` |
| Which buckets are risky? | `select name, region from aws_s3_bucket where bucket_policy_is_public` |
| Whose keys are old? | `select user_name, access_key_id, create_date from aws_iam_access_key where status = 'Active'` |
| Which projects are public? | `select full_path, web_url from gitlab_project where visibility = 'public'` |
| What is overdue? | `select key, summary, duedate from jira_issue where duedate < current_date and status_category <> 'Done'` |

## Start from a ready-made template

```bash
opslens pack list                                             # all 32, with trigger, actions and variables
opslens pack show finops-cleanup/unattached-volumes           # read the spec you would be installing
opslens pack install finops-cleanup/unattached-volumes --var jira_project=INFRA
```

## Read, check and test an automation

```bash
opslens explain generated/unattached_volume_cleanup           # plain English: what it queries, what runs, what waits
opslens validate generated/unattached_volume_cleanup          # catalog, safety rules, generated files, Flowpipe's own parser
opslens preview generated/unattached_volume_cleanup --source demo    # the rows found and every action's exact arguments
opslens preview generated/unattached_volume_cleanup           # the same on your real account, still sends nothing
opslens render my-spec.yaml --out generated                   # turn a spec you wrote into a Flowpipe mod
```

`validate` prints the **spec hash**. `preview` ends with how many state changes *would* be requested and how many were made (always zero).

## Deploy, run, approve, audit

```bash
opslens deploy generated/unattached_volume_cleanup --approve <hash>              # start it, tied to the spec you reviewed
opslens deploy generated/unattached_volume_cleanup --approve <hash> --enable-schedule   # and turn its schedule on
opslens run generated/unattached_volume_cleanup               # run now; if a change is waiting it prints the approval link
opslens approve generated/unattached_volume_cleanup <execution-id>              # answer a waiting approval here
opslens approve generated/unattached_volume_cleanup <execution-id> --choice skip
opslens runs generated/unattached_volume_cleanup              # audit log: deploys with the approved hash, runs, approvals
opslens undeploy generated/unattached_volume_cleanup          # stop it
```

## Draft with AI (optional)

```bash
opslens generate "stop dev EC2 instances at night" --show-context     # what would be sent, then stop
opslens generate "stop dev EC2 instances at night" --dry-run          # show the validated spec, write nothing
opslens generate "stop dev EC2 instances at night"                    # write the mod
opslens generate "..." --set llm.provider=ollama --set llm.model=<model>    # a local model
```

Needs a provider: the [step-by-step AI guide](../docs/ai/) walks through one, using "find my IP addresses" as the example.

## Run the web app

```bash
opslens serve                                                  # local: just you, loopback only, opens the builder
opslens serve --mode demo --port 8078                          # sample data, no writes, safe to put on the internet
OPSLENS_TEAM_PASSWORD='a long shared password' \
  opslens serve --mode team --auth password --host 0.0.0.0 --allow-host ops.example.com   # for a team, behind HTTPS
```

See [Host it for your team](../docs/hosting/).

## Find an IP address

```bash
opslens query "select instance_id, public_ip_address, private_ip_address, region from aws_ec2_instance where instance_state = 'running'"   # IPs in your AWS account
opslens describe pipeline ipstack.lookup_requester_ip_address   # the action that finds THIS machine's public IP
curl ifconfig.me                                                # the plain, no-account way
```

To run the ipstack lookup itself (a free key and a folder that uses the mod), follow the [worked example](../docs/ai/#bonus-find-this-machines-public-ip-with-the-ipstack-mod).

## Common recipes

**Find where an IP lives.**

```bash
opslens query "select instance_id, region, public_ip_address from aws_ec2_instance where public_ip_address = '203.0.113.11'"
```

**Review a template before you install it, then try it on sample data.**

```bash
opslens pack show security/public-s3-buckets
opslens pack install security/public-s3-buckets
opslens preview generated/public_s3_buckets --source demo      # the folder name is printed by install
```

**Get notified of something new every day.** Install a `chatops/*` template, set the Teams or Slack ids, then `deploy --enable-schedule`. [Connect your services](../docs/integrations/) shows how.

**Use it in CI.** `opslens validate` exits non-zero on any problem, so it can gate a merge of specs kept in git.
