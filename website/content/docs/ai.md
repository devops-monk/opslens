# AI planner (optional)

Everything in opslens works without AI. If you would rather describe an automation than build it, an AI model can **draft the spec** for you. It fills in the same small [spec format](../spec/), and the draft goes through exactly the same checks as a template. You read it before anything runs.

## What the model does, and doesn't

| The model does | The model never does |
|---|---|
| Reads your sentence | Write pipeline code (a deterministic renderer does that) |
| Reads public **catalog metadata**: table and column names, pipeline parameters | See your cloud data, tickets, alerts or credentials |
| Fills in a spec | Skip validation, or approve anything |
| Gets validation errors back and fixes them (up to 3 attempts) | Turn on `auto_apply` (it is forced off) |

## Turn it on

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
