# opslens

Turn plain-English ops requirements into reviewable, deterministic [Flowpipe](https://flowpipe.io) pipelines. Catalogs of 670 Steampipe tables and 443 Flowpipe pipelines across AWS, GitLab, Jira, Opsgenie and Microsoft Teams; a read-only SQL guard; curated packs; a web app; and an optional AI planner (Anthropic, OpenAI, GLM, OpenRouter, Ollama, any OpenAI-compatible server, LiteLLM). Everything works without AI.

Flowpipe, Steampipe and the five Steampipe plugins are baked in as separate, unmodified programs.

## Try it (no cloud account, no credentials, no network)

```bash
docker run --rm --network none abhaypratap/opslens search "unattached ebs volumes, then open a jira ticket"
docker run --rm --network none abhaypratap/opslens pack list
docker run --rm --network none abhaypratap/opslens query --source demo "select volume_id, size from aws_ebs_volume where state = 'available'"

# the web app on sample data, at http://localhost:8077
docker run --rm -p 8077:8077 abhaypratap/opslens serve --mode demo --host 0.0.0.0 --allow-host localhost
```

## Use it on your own account

```bash
docker run --rm -e AWS_PROFILE=ops -v ~/.aws:/home/opslens/.aws:ro \
  abhaypratap/opslens query "select count(*) from aws_ebs_volume"

docker run --rm -v "$PWD:/work" -w /work abhaypratap/opslens pack install governance/tag-enforcement
docker run --rm -v "$PWD:/work" -w /work abhaypratap/opslens preview generated/ec2_tag_enforcement --source demo
```

Changes never run on their own: anything that modifies state sits behind an approval step, and `deploy` needs the exact spec hash you reviewed.

## Tags

`latest` and `X.Y.Z` (multi-arch: linux/amd64, linux/arm64). Runs as a non-root user; Steampipe starts on demand.

## Links

Docs: https://opslens.devops-monk.com · Source: https://github.com/devops-monk/opslens · License: Apache-2.0 (Flowpipe and Steampipe are AGPL-3.0, run as separate programs; see `/usr/share/doc/opslens/NOTICE`).
