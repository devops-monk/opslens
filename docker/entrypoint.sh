#!/usr/bin/env bash
# Container entrypoint: start the local Steampipe service when the command needs live data, run opslens, stop the
# service, and pass opslens's exit code through (3 = a query was refused by the guard).
#
#   OPSLENS_STEAMPIPE_SERVICE=auto (default) | on | off
#     off: use an external Steampipe (set steampipe.* in opslens.yaml or OPSLENS__STEAMPIPE__*)
set -euo pipefail

if [ "$(id -u)" = "0" ]; then
  echo "opslens: Steampipe refuses to run as root; do not override the image user with --user 0." >&2
  exit 2
fi

needs_service() {
  # Commands that never query Steampipe.
  case "${1:-}" in
    ""|-h|--help|--version|--install-completion|--show-completion|init|params|config|find|describe|search) return 1 ;;
  esac
  for a in "$@"; do case "$a" in -h|--help|--offline) return 1 ;; esac; done
  if [ "${1:-}" = catalog ] && [ "${2:-}" != verify ]; then return 1; fi
  # the demo web app and anything on the bundled sample data never touch Steampipe.
  local prev=""
  for a in "$@"; do
    case "$a" in --source=demo|--mode=demo) return 1 ;; esac
    if { [ "$prev" = "--source" ] || [ "$prev" = "--mode" ]; } && [ "$a" = "demo" ]; then return 1; fi
    prev="$a"
  done
  return 0
}

mode="${OPSLENS_STEAMPIPE_SERVICE:-auto}"
started=0
if [ "$mode" = "on" ] || { [ "$mode" = "auto" ] && needs_service "$@"; }; then
  steampipe service start --database-listen local >/dev/null
  started=1
fi

status=0
opslens "$@" || status=$?

if [ "$started" = "1" ]; then
  steampipe service stop >/dev/null 2>&1 || steampipe service stop --force >/dev/null 2>&1 || true
fi
exit "$status"
