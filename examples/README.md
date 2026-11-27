# Examples

- `demo.sh`: a two-minute tour on sample data (no cloud, no credentials, no AI). Run it after `pip install opslens`.
- **Specs** to copy from live under `src/opslens/packs/` (`opslens pack show <name>` prints one).
- **Incident copilot** (`incident/incident-copilot`): enriches each open Opsgenie alert with recent GitLab deploys and open
  high-priority Jira issues in a single cross-plugin query, then posts a summary to Teams. Edit the GitLab project id (`42`) and
  Jira project (`OPS`) in the SQL, set `teams_team_id` / `teams_channel_id`, preview, deploy.
- **AI drafting**: `opslens generate "..." --set llm.provider=anthropic` (or openai, glm, openrouter, ollama, litellm).
