#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="${DEPLOY_REPO_DIR:-/var/www/github-actions/repos/tashan-assistant}"
branch="${DEPLOY_BRANCH:-main}"
lock_file="${DEPLOY_LOCK_FILE:-/run/lock/tashan-assistant-deploy.lock}"
deploy_script="${DEPLOY_SCRIPT:-${repo_dir}/scripts/deploy.sh}"

mkdir -p "$(dirname "$lock_file")"
exec 9>"$lock_file"
if ! flock --nonblock 9; then
  echo "Another deployment check is already running."
  exit 0
fi

cd "$repo_dir"
git fetch --prune origin "$branch"
target_sha="$(git rev-parse "origin/${branch}")"
deployed_sha="$(sed -n '1p' .deploy/current-sha 2>/dev/null || true)"

if [[ "$target_sha" == "$deployed_sha" ]]; then
  echo "${target_sha} is already deployed."
  exit 0
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Tracked changes exist in ${repo_dir}; refusing to overwrite them." >&2
  exit 1
fi

previous_sha="$deployed_sha"
git checkout --detach "$target_sha"
DEPLOY_REPO_DIR="$repo_dir" "$deploy_script" "$previous_sha" "$target_sha"
