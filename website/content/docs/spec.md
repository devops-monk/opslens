# The spec format

An automation is one small YAML file, `spec.yaml`. It is the source of truth: opslens renders it into a Flowpipe mod, the builder edits it, and a deploy is tied to its hash. The format is deliberately small so that a person can review it, and so a model filling it in cannot express anything unsafe.

## A complete example

```yaml
name: unattached_volume_cleanup          # lowercase letters, digits, underscores
title: Unattached EBS volume cleanup
description: Finds unattached volumes, opens a Jira ticket for each, deletes them after approval.
variables:                                # optional knobs, used as {var.name}
  jira_project:
    default: OPS
    description: Jira project key tickets are created in.
trigger:
  kind: schedule                          # manual | schedule
  schedule: daily                         # hourly | daily | weekly | 15m ... 24h | a 5-field cron
detect:
  max_items: 50                           # hard cap on rows acted on per run (1 to 500)
  sql: |
    select volume_id, region, account_id, size, volume_type
    from aws_ebs_volume
    where state = 'available'
notify: true                              # one-line summary through the notifier when something is found
approval:
  prompt: Delete these unattached volumes?
actions:
  - pipeline: jira.create_issue
    title: Open a ticket per volume
    args:
      project_key: "{var.jira_project}"
      issue_type: Task
      summary: "Unattached EBS volume {volume_id} ({size} GiB {volume_type}) in {region}"
      description: "Volume {volume_id} in account {account_id} has no attachments."
  - pipeline: aws.delete_ebs_volume
    title: Delete the volume
    gated: true                           # runs only after approval
    args:
      volume_id: "{volume_id}"
      region: "{region}"
```

## Fields

| Field | Meaning |
|---|---|
| `name` | Identifier: lowercase letters, digits and underscores, starting with a letter. Names the generated mod |
| `title`, `description` | For people |
| `request` | The plain-English request this answers (kept for the audit trail) |
| `variables` | Named values with a `default` and a `description`. Change them without editing the steps |
| `trigger.kind` | `manual` (you start it) or `schedule` |
| `trigger.schedule` | `hourly`, `daily`, `weekly`, an interval from `15m` to `24h`, or a five-field cron. Nothing tighter than 5 minutes |
| `detect.sql` | One read-only `SELECT` over catalogued tables. List the columns; no `SELECT *` |
| `detect.max_items` | Hard cap on rows acted on per run. Default 50, up to 500 |
| `notify` | Post a one-line summary through the notifier when items are found. Default on |
| `approval.prompt` | The question the approval asks |
| `actions` | One or more steps, run once per row |
| `actions[].pipeline` | A catalogued Flowpipe pipeline, such as `jira.create_issue` |
| `actions[].args` | Values for the pipeline's parameters |
| `actions[].gated` | `true` makes the step wait for approval |
| `actions[].title` | A readable name for the step |
| `auto_apply` | Allows changes with no approval. Flagged loudly; leave it off |

Unknown fields are rejected, so a typo is an error rather than a silently ignored setting.

## Placeholders

Inside `args` (and nowhere else), curly braces refer to data:

- `{column}` is a column your `detect.sql` returns, for the current row.
- `{var.name}` is a variable.

Everything else is a literal and is escaped when rendered, so a value from your data can never become pipeline code. opslens checks every placeholder: one that names a column the query doesn't return is an error you see before anything is deployed.

## Variables

```yaml
variables:
  jira_project:
    default: OPS
    description: Jira project key tickets are created in.
```

A variable is how you give a template to a colleague: they change `OPS` to `INFRA` without touching the steps. Install a pack with `--var jira_project=INFRA`, or edit the value in the builder's **Settings**. A default that still starts with `CHANGE-ME` raises a warning until you set it.

## Argument types

Parameter types come from the pipeline's own definition. In a spec you can set `string`, `number`, `bool`, `list(string)` and `map(string)` values. Write a map as `key=value,key2=value2` and a list as `a,b,c`:

```yaml
- pipeline: aws.tag_resources
  gated: true
  args:
    arn: "{arn}"
    tags: "compliance=missing-owner"
```

## The effect model

Every catalogued action has an **effect**, shown as a tag throughout the app:

| Effect | Meaning | Examples | Approval |
|---|---|---|---|
| **read** | Only reads | list, get, search | not needed |
| **notify** | Additive: creates a ticket, alert, message or comment | `jira.create_issue`, `teams.send_channel_message`, `opsgenie.create_alert` | your choice; `max_items` bounds how many |
| **change** | Changes or deletes something | `aws.delete_ebs_volume`, `aws.tag_resources` | **required** |

A `change` step without `gated: true` is an error (`ungated-write`) unless `auto_apply` is on, which is flagged at review.

## What validation checks

Errors block rendering and deploying; warnings are shown at review.

| Code | Level | Meaning |
|---|---|---|
| `sql` | error | The query failed the guard, or reads a table that is not in the catalog |
| `sql-star` | error | List the columns instead of `SELECT *` |
| `pipeline` | error | Unknown action (with "did you mean" suggestions) |
| `arg-unknown`, `arg-missing` | error | An argument the pipeline does not have, or a required one that is missing |
| `arg-type`, `arg-enum` | error | A value of the wrong type or outside the allowed set |
| `placeholder` | error | `{x}` is not a column of the query or a declared variable |
| `ungated-write` | error | A step that changes things has no approval |
| `inline-secret` | error | An argument named like a secret (token, password, key) holds a value |
| `schedule` | error | Not a valid schedule, or tighter than 5 minutes |
| `auto-apply`, `placeholder-default`, `gated-read`, `duplicate` | warning | Worth a look before you deploy |

## Render, validate, preview

```bash
opslens render stopped.yaml --out generated        # writes generated/<name>/ (mod.fp, pipelines.fp, triggers.fp, spec.yaml, README.md)
opslens validate generated/stopped_instances_review
opslens explain  generated/stopped_instances_review
opslens preview  generated/stopped_instances_review --source demo
```

`validate` also checks that the generated files still match `spec.yaml` (so a hand edit to generated code is noticed) and, unless you pass `--no-load`, that Flowpipe's own parser accepts the mod.
