# Introduction

opslens turns a plain-English ops requirement into an automation you can read, test and approve. It knows every table you can query and every action you can take across AWS, GitLab, Jira, Opsgenie and Microsoft Teams, and it works fully without AI.

![Pick a template, describe what you want, or start from scratch](screens/templates.webp)

## What it does

| You want to | How | Where |
|---|---|---|
| Start from something that works | Ready-made **templates** (packs) for cost cleanup, tag compliance, security tickets and incident response | App: Templates · CLI: `opslens pack` |
| Build your own | A **visual builder**: pick a trigger, say what to find, add actions, mark what needs your approval | App: Builder |
| Know what exists | Search **670 tables** and **443 actions** in plain words; data and actions are matched separately | App: Explore · CLI: `opslens search` |
| Be sure before it runs | **Test** on sample data or read-only on live data; see every payload; nothing changes | App: Test · CLI: `opslens preview` |
| Keep a person in charge | Anything that changes things **waits for your approval**; deploys are tied to the exact reviewed spec | `opslens deploy --approve` |
| Skip the typing (optional) | **Describe it in a sentence** and let an AI draft the spec; it goes through the same checks | App: Templates · CLI: `opslens generate` |

## How it works, in one paragraph

An automation is a small **spec**: when it runs, what to look for (a read-only SQL query over [Steampipe](https://steampipe.io) tables), and what to do for each row (a [Flowpipe](https://flowpipe.io) pipeline such as `jira.create_issue`). opslens checks the spec against the catalogs and safety rules, renders it into a Flowpipe mod deterministically (nobody, human or model, writes pipeline code), shows you what a run would do right now, and only then deploys it. See [How it works](../architecture/) for the picture.

## Principles

- **Read first, change last.** Queries are read-only and guarded. Creating a ticket or message may run on its own; anything that *changes* a resource sits behind an approval.
- **What you reviewed is what runs.** A deploy needs the hash of the exact spec you read. Edit the spec and the hash changes.
- **No hidden steps.** Every generated file is plain text you can open. Nothing is hand-edited without being noticed.
- **AI is a convenience, not a dependency.** It fills in a spec; it never writes code, never sees your cloud data, and never skips the checks.
- **Credentials stay in Flowpipe and Steampipe.** Specs never contain secrets; opslens refuses any that look like one. How to connect each tool: [Connect your services](integrations/).

## Where to start

Try the [live demo](../../app/) on sample data, then [install](../install/) it and follow the [quick start](../quickstart/). If you would rather read first, the [use cases](../use-cases/) show four real automations end to end.
