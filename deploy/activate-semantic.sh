#!/usr/bin/env bash
set -euo pipefail
package=$1
expected=$2
[[ "$package" =~ ^/imports/semantic-[0-9a-f]{16}$ && "$expected" =~ ^[1-9][0-9]*$ ]]
cd /opt/newsfinder/current
exec 9>/opt/newsfinder/deploy.lock
flock -w 600 9
envfile=/opt/newsfinder/production.env
dc() { docker compose --env-file "$envfile" -f compose.production.yaml "$@"; }
export APP_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$(dc ps -q app)")"
dc exec -T app wikinews-ir semantic import --check-archive --package "$package" </dev/null
dc exec -T app wikinews-ir semantic verify --check-archive --package "$package" </dev/null
probe() {
    dc exec -T app python -c '
import json, sys, urllib.request
base = "http://127.0.0.1:8000"
with urllib.request.urlopen(base + "/api/search?q=terremoto&profile=semantic&page_size=1", timeout=120) as r:
    data = json.load(r)
assert data["total"] == int(sys.argv[1]) and data["hits"]
with urllib.request.urlopen(base + "/articles/" + data["hits"][0]["document_id"], timeout=15) as r:
    assert r.status == 200
' "$expected" </dev/null
}
probe
if ! grep -qx SEMANTIC_ENABLED=1 "$envfile"; then
    backup=$(mktemp /opt/newsfinder/.semantic-env.XXXXXX)
    cp --preserve=mode "$envfile" "$backup"
    restore() {
        mv "$backup" "$envfile"
        dc up -d --wait --no-deps --no-build app
    }
    trap restore ERR
    if grep -q '^SEMANTIC_ENABLED=' "$envfile"; then
        sed -i 's/^SEMANTIC_ENABLED=.*/SEMANTIC_ENABLED=1/' "$envfile"
    else
        printf '\nSEMANTIC_ENABLED=1\n' >> "$envfile"
    fi
    dc up -d --wait --no-deps --no-build app
    probe
    dc exec -T app python -c 'import urllib.request; assert b"value=\"semantic\"" in urllib.request.urlopen("http://localhost:8000/").read()' </dev/null
    trap - ERR
    rm -f "$backup"
fi
