#!/usr/bin/env bash
# Run with bash from a checked-out release on the Ubuntu server.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${APP_IMAGE:-}" && -f /opt/newsfinder/deployed-revision ]]; then
  export APP_IMAGE="newsfinder-app:$(cat /opt/newsfinder/deployed-revision)"
fi
dc() { docker compose --env-file /opt/newsfinder/production.env -f compose.production.yaml "$@"; }
case "${1:-help}" in
  bootstrap)
    [[ $EUID -eq 0 ]] || { echo 'Run bootstrap with sudo'; exit 1; }
    . /etc/os-release
    [[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'Requires Ubuntu 24.04'; exit 1; }
    apt-get update
    apt-get install -y ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    printf 'vm.max_map_count=1048576\n' > /etc/sysctl.d/90-newsfinder.conf
    sysctl --system
    install -d -m 0700 /opt/newsfinder/secrets
    install -d -m 0755 /opt/newsfinder/imports
    install -d -m 0700 /opt/newsfinder/reports
    ;;
  cloudflare-ips)
    python3 - <<'PY'
import ipaddress
import urllib.request
networks = []
for version in (4, 6):
    with urllib.request.urlopen(f'https://www.cloudflare.com/ips-v{version}', timeout=15) as response:
        values = response.read().decode().split()
    if not values:
        raise SystemExit('Empty Cloudflare range list')
    networks.extend(str(ipaddress.ip_network(value)) for value in values)
print('CLOUDFLARE_CIDRS="' + ' '.join(networks) + '"')
PY
    ;;
  deploy)
    revision="${2:?Usage: deploy FULL_COMMIT_SHA}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Use a full commit SHA'; exit 1; }
    [[ "$(git rev-parse HEAD)" == "$revision" && -z "$(git status --porcelain)" ]] || { echo 'Checkout the exact clean revision first'; exit 1; }
    test -s /opt/newsfinder/secrets/origin.pem
    test -s /opt/newsfinder/secrets/origin.key
    export APP_IMAGE="newsfinder-app:$revision"
    dc config --quiet
    dc build app
    dc run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile
    dc stop app
    # Explicit administration step performs schema migrations, not health requests.
    dc run --rm --no-deps app wikinews-ir annotation init
    dc up -d
    printf '%s\n' "$revision" > /opt/newsfinder/deployed-revision
    for attempt in {1..15}; do
      if dc exec -T app python -m wikinews_ir.operations check; then exit 0; fi
      sleep 2
    done
    echo 'Annotation readiness failed; inspect logs before reopening collection'
    exit 1
    ;;
  status)
    dc ps
    dc exec -T app python -m wikinews_ir.operations check
    docker stats --no-stream
    df -h /var/lib/docker
    ;;
  compose)
    shift
    dc "$@"
    ;;
  *) echo 'Usage: bash scripts/server.sh {bootstrap|cloudflare-ips|deploy SHA|status|compose ...}'; exit 2 ;;
esac
