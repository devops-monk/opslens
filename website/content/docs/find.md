# Find tables and actions

Every automation starts with two questions: *what do I look at?* and *what do I do about it?* opslens answers both from two catalogs that ship with it, built from the plugin and library source and checked against the real thing, so nothing is guessed.

| Catalog | Answers | Size |
|---|---|---|
| **Tables** (Steampipe) | What can I query? Columns, types, descriptions, required filters, examples | 670 tables, five plugins |
| **Pipelines** (Flowpipe) | What can I do? Typed parameters, outputs, and whether it reads, notifies or changes | 443 pipelines, 15 library mods |

## Which command do I use?

| You want to... | Command |
|---|---|
| Find **both** the data and the action for a sentence | `opslens search "..."` |
| Find only a **table** (something to query) | `opslens find tables ...` |
| Find only an **action** (something to do) | `opslens find pipelines ...` |
| See a table's columns | `opslens describe table <name>` |
| See an action's parameters | `opslens describe pipeline <name>` |
| Run a SQL query | `opslens query "select ..."` (SQL only, not plain words) |

`search` and `find` take **words**. `query` takes **SQL**. If you give `query` a sentence, it refuses and tells you to use `search`.

## Step 1. One search for both

```bash
opslens search "unattached ebs volumes older than 14 days, then open a jira ticket and post to teams"
```

Your sentence is split at the "then": the first part is matched against **data** (tables), each later part against **actions** (pipelines). The output is one table per part. A real run prints this (trimmed):

```text
Data (Steampipe tables) for: unattached ebs volumes older than 14 days
 table                 description
 aws_ebs_volume        Allows users to query AWS Elastic Block Store (EBS) volumes ...
 aws_ebs_snapshot      Allows users to query AWS EBS snapshots ...

Action (Flowpipe pipelines) for: open a jira ticket
 pipeline                     risk   description                       requires
 jira.pipeline.create_issue   write  Create a new issue in a Jira ...  project_key, issue_type, summary

Action (Flowpipe pipelines) for: post to teams
 pipeline                              risk   description                      requires
 teams.pipeline.send_channel_message   write  Send a new chat message ...       team_id, channel_id, message
```

Read it like this: the **table** is what you will `select` from (`aws_ebs_volume`), and each **pipeline** is an action name you can put in a spec (`jira.create_issue`, `teams.send_channel_message`; drop the middle `.pipeline`). The `risk` column is the catalog's class: `read` only fetches, `write` adds or changes something. opslens's own finer labels (read, notify, change) are explained [below](#what-the-labels-mean).

The same search is in the app's **Explore** tab and at the top of every [template gallery](../app/). It also runs entirely in your browser on the [Explore page](../../explore/) of this site, with nothing to install.

![Explore: tables on the left, actions on the right](screens/explore.webp)

## Step 2. Narrow it down

```bash
opslens find tables unattached ebs volumes             # tables only
opslens find tables jira issue --plugin jira           # only the jira plugin
opslens find pipelines create jira issue               # actions only
opslens find pipelines tag --mod aws --writes          # only AWS actions that change things
opslens find pipelines list instances --reads          # only actions that just read
opslens find pipelines "ip address"                    # the IP lookups (ipstack, abuseipdb, ip2locationio)
```

## Step 3. Look at one in detail

```bash
opslens describe table aws_ebs_volume            # columns, types, required filters, examples
opslens describe table jira_issue
opslens describe pipeline jira.create_issue      # typed params, outputs, steps, a usage snippet
opslens describe pipeline teams.send_channel_message
```

`describe table` tells you which columns you can `select` and which are cheap to filter on. For an API-backed table, filtering on the right columns is the difference between one call and thousands. `describe pipeline` lists every parameter with its type and whether it is required (those are the ones your spec must fill in), and ends with a snippet showing how it is called.

## Step 4. Try a query

Now that you know the table and its columns, ask it something:

```bash
opslens query --source demo "select volume_id, region, size from aws_ebs_volume where state = 'available'"
opslens query "select count(*) from aws_ebs_volume"          # live: needs Steampipe and credentials
```

`--source demo` uses bundled sample data, which takes the same Postgres SQL as the live service, so what you write on sample data runs unchanged on live data. Queries pass the [safety guard](../safety/) first: one `SELECT`, catalog tables only, with a timeout and row cap. For live data you first need to [connect your services](../integrations/).

## Step 5. Use what you found

Put the table in the spec's `detect.sql` and the action in `actions`, then preview. [Quick start](../quickstart/) does this end to end, and the [spec format](../spec/) lists every field. Or start from the nearest [template](../packs/).

## What the labels mean

opslens uses three labels for an action, and they decide what happens in a run:

- **read**: only fetches data.
- **notify**: adds something (a ticket, an alert, a message). May run on its own.
- **change**: modifies or deletes. Always sits behind an [approval](../deploy/).

You see them in `opslens preview` and in the [Actions reference](../actions/). In `search` and `describe` the catalog's coarser `read` / `write` risk is shown instead; every `write` is treated with care (a `notify` still adds only, a `change` always waits for approval).

A search for "delete" will show deletions; a search that doesn't mention deleting will not lead with them.

## Keep the catalogs honest

```bash
opslens catalog stats                 # what is in the shipped catalogs
opslens catalog verify                # compare against your installed Steampipe plugins (no API calls)
```

`verify` catches the case where your installed plugin version differs from the one the catalog was built from. See [The catalogs](../catalog/).
