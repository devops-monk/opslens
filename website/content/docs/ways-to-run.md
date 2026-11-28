# Ways to run

The same engine runs in several shapes. Pick the one that fits.

| Shape | Best for | Command |
|---|---|---|
| **Installer** | Your laptop or a jump box, with live data and deploys | `curl -fsSL https://opslens.devops-monk.com/install.sh \| sh` |
| **Hosted demo** | A look around, no install | [opslens.devops-monk.com/app](../../app/) |
| **Local web app** | The visual builder with your own data | `opslens serve` |
| **Team server** | The full app for a team, behind HTTPS, with sign-in | `opslens serve --mode team` ([guide](../hosting/)) |
| **CLI** | Scripts, CI, and people who live in a terminal | `opslens search`, `preview`, `deploy` |
| **Docker** | Reproducible runs, CI, no local installs | `docker run abhaypratap/opslens ...` |

## The hosted demo

[opslens.devops-monk.com/app](../../app/) is the same app in **demo mode**: sample data only. It cannot reach a cloud account, save, deploy, run or call an AI, and it rate-limits requests. It is safe to explore and to share a link to.

## The local web app

```bash
opslens serve                              # http://127.0.0.1:8077, full workflow on your machine
opslens serve --mode demo                  # the public variant, on sample data
```

Local mode binds to loopback only (it refuses to start on another address), rejects unknown `Host` headers, and requires a per-session token for every call that changes anything. See [Data and privacy](../data-security/).

## Docker

```bash
# no credentials, no network: explore and preview on sample data
docker run --rm --network none abhaypratap/opslens search "unattached ebs volumes then open a jira ticket"
docker run --rm --network none abhaypratap/opslens pack list

# the web app on sample data
docker run --rm -p 8077:8077 abhaypratap/opslens serve --mode demo --host 0.0.0.0 --allow-host localhost

# live data: pass your AWS profile read-only
docker run --rm -e AWS_PROFILE=ops -v ~/.aws:/home/opslens/.aws:ro abhaypratap/opslens query "select count(*) from aws_ebs_volume"

# keep generated mods on your disk
docker run --rm -v "$PWD:/work" -w /work abhaypratap/opslens pack install governance/tag-enforcement
```

The image runs as a non-root user and starts Steampipe only when a command needs it.

## In CI

Specs are plain files, so you can review and check them like code. A pull-request check that needs no cloud access:

```bash
opslens validate generated/my_automation --no-load      # catalogs, SQL guard, safety rules, drift check
opslens preview  generated/my_automation --source demo  # renders every action's arguments on sample data
```

`validate` also fails when a generated file no longer matches `spec.yaml`, which catches hand edits to generated code.
