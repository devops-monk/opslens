#!/usr/bin/env bash
# Deploy the public DEMO app (opslens serve --mode demo) to the shared VPS under https://<domain>/app/.
#
#   OPSLENS_SITE_HOST=user@host scripts/deploy_app.sh
#
# Safety: runs as an unprivileged `opslens` user in a venv under /opt/opslens, bound to 127.0.0.1:8077, systemd-sandboxed
# with memory/CPU limits. The only change to nginx is one additive `location ^~ /app/` block in this site's own server
# block; the config is backed up, `nginx -t` must pass before the reload, and on failure it is restored.
# shellcheck disable=SC2029
set -euo pipefail

HOST="${OPSLENS_SITE_HOST:?set OPSLENS_SITE_HOST to the deploy target, e.g. user@host or an ~/.ssh/config alias}"
DOMAIN="opslens.devops-monk.com"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> building wheel"
uv build --wheel -o "$TMP" "$ROOT" >/dev/null
WHEEL="$(ls "$TMP"/*.whl)"
scp -q "$WHEEL" "$HOST:/tmp/$(basename "$WHEEL")"
scp -q "$ROOT/website/deploy/opslens-app.service" "$HOST:/tmp/opslens-app.service"
scp -q "$ROOT/website/deploy/opslens-app.nginx" "$HOST:/tmp/opslens-app.nginx"

echo "==> installing on $HOST"
ssh "$HOST" bash -s -- "$(basename "$WHEEL")" "$DOMAIN" <<'REMOTE'
set -euo pipefail
WHL="/tmp/$1"; DOMAIN="$2"
id opslens >/dev/null 2>&1 || useradd --system --home-dir /opt/opslens --shell /usr/sbin/nologin opslens
mkdir -p /opt/opslens
if [ ! -x /opt/opslens/venv/bin/pip ]; then
  rm -rf /opt/opslens/venv
  python3 -m venv /opt/opslens/venv || { echo "python3 -m venv failed: apt install python3-venv" >&2; exit 1; }
fi
/opt/opslens/venv/bin/pip install -q --upgrade pip
/opt/opslens/venv/bin/pip install -q --upgrade --force-reinstall --no-deps "$WHL"
/opt/opslens/venv/bin/pip install -q "$WHL[web]"
chown -R root:root /opt/opslens && chmod -R go-w /opt/opslens
install -m 644 /tmp/opslens-app.service /etc/systemd/system/opslens-app.service
systemctl daemon-reload
systemctl enable opslens-app >/dev/null 2>&1
systemctl restart opslens-app

CONF="/etc/nginx/sites-available/$DOMAIN"
if ! grep -q 'location ^~ /app/' "$CONF"; then
  ts=$(date +%Y%m%d-%H%M%S)
  cp "$CONF" "/root/$DOMAIN.conf.bak-$ts"
  python3 - "$CONF" <<'PY'
import sys
p = sys.argv[1]
c = open(p).read()
block = open("/tmp/opslens-app.nginx").read()
marker = "    # Never serve deploy helpers"
assert marker in c, "marker not found; add the block by hand"
open(p, "w").write(c.replace(marker, block + marker, 1))
PY
  if nginx -t 2>/dev/null; then
    systemctl reload nginx
  else
    echo "nginx -t FAILED: restoring previous config" >&2
    cp "/root/$DOMAIN.conf.bak-$ts" "$CONF"
    nginx -t && exit 1
  fi
fi
rm -f "$WHL" /tmp/opslens-app.service /tmp/opslens-app.nginx
for i in $(seq 1 20); do curl -fsS http://127.0.0.1:8077/api/meta >/dev/null 2>&1 && break; sleep 1; done
systemctl is-active opslens-app
REMOTE

echo "==> smoke test"
curl -fsS "https://$DOMAIN/app/api/meta" | head -c 160; echo
curl -fsS -o /dev/null -w "ui   %{http_code}\n" "https://$DOMAIN/app/"
curl -fsS -o /dev/null -w "js   %{http_code}\n" "https://$DOMAIN/app/static/app.js"
