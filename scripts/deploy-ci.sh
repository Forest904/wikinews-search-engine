#!/usr/bin/env bash
# Invoked over SSH by the production workflow. Infrastructure stays operator-managed.
set -Eeuo pipefail
revision="${1:?Usage: deploy-ci.sh FULL_COMMIT_SHA}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA'; exit 1; }
cd /opt/newsfinder/current
exec 9>/opt/newsfinder/deploy.lock
flock -w 600 9
dc() { docker compose --env-file /opt/newsfinder/production.env -f compose.production.yaml "$@"; }

# A slower CI run must not replace a newer push already on main.
latest=$(git ls-remote origin refs/heads/main | cut -f1)
if [[ "$latest" != "$revision" ]]; then
  echo "Skipping superseded revision $revision (main: $latest)"
  exit 0
fi

container=$(dc ps -q app)
test -n "$container"
previous_image=$(docker inspect --format '{{.Config.Image}}' "$container")
docker image inspect "$previous_image" >/dev/null
export APP_IMAGE="newsfinder-app:$revision"
docker image inspect "$APP_IMAGE" >/dev/null
dc config --quiet
# Fail before replacement if the existing database requires a manual migration.
dc run --rm --no-deps app python -m wikinews_ir.operations check

rollback() {
  result=$?
  trap - ERR HUP INT TERM
  echo "Deployment failed; restoring $previous_image" >&2
  export APP_IMAGE="$previous_image"
  if ! dc up -d --no-deps --no-build --wait --wait-timeout 120 app; then
    echo 'ROLLBACK FAILED: operator intervention required' >&2
  fi
  exit "$result"
}
trap rollback ERR
trap 'false' HUP INT TERM
dc up -d --no-deps --no-build --wait --wait-timeout 120 app
dc exec -T app python -m wikinews_ir.operations check
dc exec -T app python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=10)"
printf '%s\n' "$revision" > /opt/newsfinder/deployed-revision.tmp
mv /opt/newsfinder/deployed-revision.tmp /opt/newsfinder/deployed-revision
trap - ERR HUP INT TERM
echo "Deployed $revision"
