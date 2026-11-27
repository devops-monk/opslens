# opslens docs

opslens turns a plain-English ops requirement into a Flowpipe pipeline you can read, review and approve. It works fully offline with no AI. An AI planner is optional and arrives in a later release.

## Install

```bash
# with pip (Python 3.11+)
pip install opslens

# or the container (Flowpipe, Steampipe and five plugins included)
docker run --rm ghcr.io/devops-monk/opslens doctor
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

## Exit codes

| code | meaning |
|---|---|
| 0 | ok |
| 1 | error |
| 2 | bad settings or usage |
| 3 | query refused by the safety guard |
