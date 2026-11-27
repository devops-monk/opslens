#!/usr/bin/env bash
# A two-minute tour of opslens on built-in sample data: no cloud account, no credentials, no network, no AI.
#   examples/demo.sh
set -euo pipefail
cd "$(mktemp -d)"
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

say "1. Find: split a requirement into data and actions"
opslens search "open opsgenie alerts, then post a summary to teams"

say "2. Pick a pack and render it into a Flowpipe mod"
opslens pack install incident/incident-copilot --var teams_team_id=demo-team --var teams_channel_id=demo-channel

say "3. Read it in plain English, then validate it"
opslens explain generated/incident_copilot
opslens validate generated/incident_copilot --no-load

say "4. Preview: what would a run do RIGHT NOW? (reads sample data; nothing is sent)"
opslens preview generated/incident_copilot --source demo

say "5. A pack that changes things: every change waits for approval"
opslens pack install finops-cleanup/unattached-volumes
opslens preview generated/unattached_volume_cleanup --source demo | tail -12

echo
echo "Next: opslens serve   (the web app on http://127.0.0.1:8077), or see docs: https://opslens.devops-monk.com/docs/"
