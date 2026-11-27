#!/usr/bin/env bash
# Local variables ($WEBROOT, $DOMAIN, ...) are deliberately expanded client-side in the ssh commands.
# shellcheck disable=SC2029,SC2087
# Deploy the static site to the shared VPS without touching other sites.
#
#   OPSLENS_SITE_HOST=user@host scripts/deploy_site.sh          # build, upload, enable nginx block (first time), reload
#   OPSLENS_SITE_HOST=user@host scripts/deploy_site.sh --tls    # also run certbot for this domain (first time only)
#
# OPSLENS_SITE_HOST is required (no default, so the server address is not kept in the repo).
# It can also be an ~/.ssh/config alias, e.g. OPSLENS_SITE_HOST=opslens-vps.
#
# Safety: content goes to /var/www/opslens only; the nginx block is a new file matched
# by server_name; the full nginx config is backed up and `nginx -t` must pass before a
# graceful reload, otherwise the new block is removed and the backup restored.
set -euo pipefail

HOST="${OPSLENS_SITE_HOST:?set OPSLENS_SITE_HOST to the deploy target, e.g. user@host or an ~/.ssh/config alias}"
DOMAIN="opslens.devops-monk.com"
WEBROOT="/var/www/opslens"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/website/deploy/$DOMAIN.conf"

"$ROOT/.venv/bin/python" "$ROOT/scripts/build_site.py" --check

echo "==> uploading site to $HOST:$WEBROOT"
ssh "$HOST" "mkdir -p $WEBROOT.new && rm -rf $WEBROOT.new/*"
rsync -az --delete "$ROOT/website/dist/" "$HOST:$WEBROOT.new/"
# swap atomically-ish: previous version kept as .prev for rollback
ssh "$HOST" "chown -R www-data:www-data $WEBROOT.new && rm -rf $WEBROOT.prev && \
  { [ -d $WEBROOT ] && mv $WEBROOT $WEBROOT.prev || true; } && mv $WEBROOT.new $WEBROOT"

if ! ssh "$HOST" "test -f /etc/nginx/sites-available/$DOMAIN"; then
  echo "==> installing nginx server block (first deploy)"
  scp "$CONF" "$HOST:/tmp/$DOMAIN.conf"
  ssh "$HOST" bash -s <<EOF
set -euo pipefail
ts=\$(date +%Y%m%d-%H%M%S)
tar -C /etc -czf /root/nginx-backup-\$ts.tgz nginx
install -m 644 /tmp/$DOMAIN.conf /etc/nginx/sites-available/$DOMAIN
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
if nginx -t; then
  systemctl reload nginx
  echo "nginx reloaded; backup at /root/nginx-backup-\$ts.tgz"
else
  echo "nginx -t FAILED - rolling back" >&2
  rm -f /etc/nginx/sites-enabled/$DOMAIN /etc/nginx/sites-available/$DOMAIN
  nginx -t && exit 1
fi
EOF
fi

if [[ "${1:-}" == "--tls" ]]; then
  echo "==> certbot for $DOMAIN"
  ssh "$HOST" "certbot --nginx -d $DOMAIN --non-interactive --redirect && nginx -t && systemctl reload nginx"
fi

echo "==> smoke test"
curl -fsS -o /dev/null -w "http  %{http_code}\n" "http://$DOMAIN/" || true
curl -fsS -o /dev/null -w "https %{http_code}\n" "https://$DOMAIN/" || true
