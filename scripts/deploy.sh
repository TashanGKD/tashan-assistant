#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="${DEPLOY_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
previous_sha="${1:-}"
target_sha="${2:-$(git -C "$repo_dir" rev-parse HEAD)}"
compose_files="${DEPLOY_COMPOSE_FILES:-docker-compose.yml}"
require_feishu="${DEPLOY_REQUIRE_FEISHU:-1}"

cd "$repo_dir"

compose=(docker compose)
IFS=':' read -r -a compose_file_list <<< "$compose_files"
for compose_file in "${compose_file_list[@]}"; do
  compose+=(--file "$compose_file")
done

env_value() {
  sed -n -E "s/^${1}=(.*)$/\1/p" .env | tail -n 1 | tr -d '\r'
}

require_env_value() {
  local key="$1"
  local value
  value="$(env_value "$key")"
  if [[ -z "$value" ]]; then
    echo "Required production setting ${key} is missing from ${repo_dir}/.env." >&2
    return 1
  fi
  if [[ "$value" == *"replace-with"* || "$value" == *"your_key"* || "$value" == "change-me-before-production" ]]; then
    echo "Required production setting ${key} still contains a placeholder." >&2
    return 1
  fi
}

validate_production_env() {
  [[ -f .env ]] || {
    echo "Production environment file is missing: ${repo_dir}/.env" >&2
    return 1
  }

  require_env_value DEEPSEEK_API_KEY
  require_env_value ADMIN_TOKEN

  if [[ "$require_feishu" == "1" ]]; then
    require_env_value FEISHU_APP_ID
    require_env_value FEISHU_APP_SECRET
    require_env_value FEISHU_APP_TOKEN
    require_env_value FEISHU_CASE_TABLE_ID
    require_env_value FEISHU_REPORT_TABLE_ID
  fi
}

wait_for_application() {
  local bind_ip app_port health_url payload
  bind_ip="$(env_value APP_BIND_IP)"
  app_port="$(env_value APP_PORT)"
  bind_ip="${bind_ip:-127.0.0.1}"
  app_port="${app_port:-8000}"
  health_url="http://${bind_ip}:${app_port}/api/health"

  for _ in $(seq 1 30); do
    payload="$(curl --silent --show-error --fail --max-time 5 "$health_url" 2>/dev/null || true)"
    if [[ "$payload" == *'"ok":true'* && "$payload" == *'"deepseek":true'* ]]; then
      if [[ "$require_feishu" != "1" || "$payload" == *'"feishu":true'* ]]; then
        echo "Application health check passed at ${health_url}."
        return 0
      fi
    fi
    sleep 2
  done

  echo "Application did not become production-ready at ${health_url}." >&2
  return 1
}

rollback() {
  local status=$?
  trap - ERR

  if [[ -n "$previous_sha" && "$previous_sha" != "$target_sha" ]] && git cat-file -e "${previous_sha}^{commit}" 2>/dev/null; then
    echo "Deployment failed. Restoring ${previous_sha}." >&2
    git checkout --detach "$previous_sha"
    "${compose[@]}" config --quiet
    "${compose[@]}" build
    "${compose[@]}" up --detach --remove-orphans
    wait_for_application || echo "Rollback completed, but the restored service is not ready." >&2
  fi

  exit "$status"
}

trap rollback ERR

validate_production_env
"${compose[@]}" config --quiet
"${compose[@]}" build --pull
"${compose[@]}" up --detach --remove-orphans
wait_for_application

mkdir -p .deploy
printf '%s\n' "$target_sha" > .deploy/current-sha
trap - ERR

echo "Deployed ${target_sha}."
