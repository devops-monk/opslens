#!/bin/sh
# opslens installer: one command for macOS and Linux:
#
#   curl -fsSL https://opslens.devops-monk.com/install.sh | sh
#
# Installs, without sudo and without touching other Python environments:
#   1. Flowpipe + Steampipe (pinned): via Homebrew when available, otherwise release binaries into ~/.local/bin
#      (each download is verified against the release's checksums.txt)
#   2. the Steampipe plugins opslens ships catalogs for (pinned): aws, jira, microsoft365, gitlab, opsgenie
#   3. opslens, isolated: pipx > uv tool > a private venv
#
# It installs tools only. It never reads cloud credentials or calls any cloud API.
#
# Options (environment variables):
#   OPSLENS_REF=v0.3.3            git tag/branch to install (default: the release this script shipped with)
#   OPSLENS_EXTRAS=               pip extras, e.g. "ai" for the AI planner (default: none)
#   OPSLENS_SKIP_ENGINES=1        don't install Flowpipe/Steampipe or any plugin
#   OPSLENS_SKIP_PLUGINS=1        install the engines but no plugins
#   OPSLENS_PLUGINS="aws jira"    only these plugins (default: all five)
#   OPSLENS_BIN_DIR=~/.local/bin
#   OPSLENS_PACKAGE=<path|url>    install opslens from this wheel/sdist instead of GitHub
#   OPSLENS_DRY_RUN=1             print what would run, change nothing
set -eu

REPO="https://github.com/devops-monk/opslens"
FLOWPIPE_VERSION="1.2.4"
STEAMPIPE_VERSION="2.5.0"
PLUGIN_SPECS="aws@1.35.0 jira@2.0.5 microsoft365@1.3.0 theapsgroup/gitlab jplanckeel/opsgenie"
REF="${OPSLENS_REF:-v0.3.3}"
EXTRAS="${OPSLENS_EXTRAS-}"
BIN_DIR="${OPSLENS_BIN_DIR:-$HOME/.local/bin}"
DRY="${OPSLENS_DRY_RUN:-0}"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if [ "$DRY" = "1" ]; then printf '    + %s\n' "$*"; else "$@"; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

[ "$(id -u)" = "0" ] && die "run as your normal user, not root (Steampipe refuses to run as root)"
have curl || die "curl is required"

case "$(uname -s)" in
  Darwin) OS=darwin ;;
  Linux)  OS=linux ;;
  *) die "unsupported OS: $(uname -s); use the Docker image instead (see README)" ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  ARCH=amd64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) die "unsupported CPU: $(uname -m)" ;;
esac

# ---------------------------------------------------------------- python
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || die "Python 3.11+ is required (macOS: brew install python; Debian/Ubuntu: apt install python3 python3-venv)"

run mkdir -p "$BIN_DIR"

# ---------------------------------------------------------------- engines
sha256_of() { if have sha256sum; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

fetch_bin() {  # url, archive kind (zip|tgz), binary name, checksums url
  tmp=$(mktemp -d)
  run curl -fsSL "$1" -o "$tmp/pkg"
  if [ "$DRY" != "1" ]; then
    if curl -fsSL "$4" -o "$tmp/sums" 2>/dev/null; then
      want=$(grep " $(basename "$1")\$" "$tmp/sums" | cut -d' ' -f1 || true)
      if [ -n "$want" ] && [ "$want" != "$(sha256_of "$tmp/pkg")" ]; then die "checksum mismatch for $1"; fi
      [ -n "$want" ] || warn "no checksum listed for $(basename "$1"); continuing"
    else
      warn "could not fetch $4; skipping checksum verification"
    fi
    case "$2" in
      zip) have unzip || die "unzip is required"; unzip -q "$tmp/pkg" -d "$tmp/x" ;;
      tgz) mkdir -p "$tmp/x" && tar -xzf "$tmp/pkg" -C "$tmp/x" ;;
    esac
    found=$(find "$tmp/x" -type f -name "$3" | head -1)
    [ -n "$found" ] || die "$3 not found in $1"
    install -m 0755 "$found" "$BIN_DIR/$3"
  fi
  rm -rf "$tmp"
}

if [ "${OPSLENS_SKIP_ENGINES:-0}" != "1" ]; then
  if have flowpipe; then
    say "Flowpipe already installed ($(flowpipe --version 2>/dev/null | head -1))"
  elif have brew; then
    say "Installing Flowpipe with Homebrew"
    run brew install turbot/tap/flowpipe
  else
    say "Installing Flowpipe v$FLOWPIPE_VERSION into $BIN_DIR"
    base="https://github.com/turbot/flowpipe/releases/download/v$FLOWPIPE_VERSION"
    fetch_bin "$base/flowpipe.${OS}.${ARCH}.tar.gz" tgz flowpipe "$base/checksums.txt"
  fi

  if have steampipe; then
    say "Steampipe already installed ($(steampipe --version 2>/dev/null | head -1))"
  elif have brew; then
    say "Installing Steampipe with Homebrew"
    run brew install turbot/tap/steampipe
  else
    say "Installing Steampipe v$STEAMPIPE_VERSION into $BIN_DIR"
    base="https://github.com/turbot/steampipe/releases/download/v$STEAMPIPE_VERSION"
    if [ "$OS" = darwin ]; then
      fetch_bin "$base/steampipe_${OS}_${ARCH}.zip" zip steampipe "$base/checksums.txt"
    else
      fetch_bin "$base/steampipe_${OS}_${ARCH}.tar.gz" tgz steampipe "$base/checksums.txt"
    fi
  fi

  if [ "${OPSLENS_SKIP_PLUGINS:-0}" != "1" ]; then
    SP=$(command -v steampipe 2>/dev/null || echo "$BIN_DIR/steampipe")
    for spec in ${OPSLENS_PLUGINS:-$PLUGIN_SPECS}; do
      say "Installing the Steampipe plugin $spec"
      run "$SP" plugin install "$spec" || warn "plugin $spec failed to install; install it later with: steampipe plugin install $spec"
    done
  fi
fi

# ---------------------------------------------------------------- opslens
SRC="$REPO/archive/$REF.tar.gz"
if [ -n "$EXTRAS" ]; then SPEC="opslens[$EXTRAS] @ $SRC"; else SPEC="opslens @ $SRC"; fi
if [ -n "${OPSLENS_PACKAGE:-}" ]; then
  case "$OPSLENS_PACKAGE" in
    *://*) SPEC="opslens @ $OPSLENS_PACKAGE" ;;
    *)     SPEC="$OPSLENS_PACKAGE" ;;
  esac
  [ -z "$EXTRAS" ] || SPEC="$SPEC[$EXTRAS]"
fi

if have pipx; then
  say "Installing opslens with pipx"
  run pipx install --force "$SPEC"
elif have uv; then
  say "Installing opslens with uv tool"
  run uv tool install --force --python "$PY" "$SPEC"
else
  VENV="$HOME/.local/share/opslens/venv"
  say "Installing opslens into a private virtualenv ($VENV)"
  run "$PY" -m venv "$VENV"
  run "$VENV/bin/pip" install --quiet --upgrade pip
  run "$VENV/bin/pip" install --quiet "$SPEC"
  run ln -sf "$VENV/bin/opslens" "$BIN_DIR/opslens"
fi

case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR is not on your PATH; add it to your shell profile" ;; esac

say "Done. Try it (no cloud account needed):"
printf '    opslens doctor\n    opslens search "unattached ebs volumes then open a jira ticket"\n    opslens query --source demo "select volume_id, size from aws_ebs_volume where state = '"'"'available'"'"'"\n'
