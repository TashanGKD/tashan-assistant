#!/usr/bin/env bash
set -Eeuo pipefail

domain="${1:?Usage: configure-domain.sh DOMAIN UPSTREAM_PORT [EMAIL]}"
upstream_port="${2:?Usage: configure-domain.sh DOMAIN UPSTREAM_PORT [EMAIL]}"
email="${3:-}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vhost_dir="${NGINX_VHOST_DIR:-/www/server/panel/vhost/nginx}"
nginx_bin="${NGINX_BIN:-/www/server/nginx/sbin/nginx}"
webroot="${ACME_WEBROOT:-/www/wwwroot/${domain}}"
vhost_path="${vhost_dir}/${domain}.conf"
backup_path=""
expected_public_ip="${EXPECTED_PUBLIC_IP:-}"

[[ "$EUID" -eq 0 ]] || {
  echo "Run this script as root." >&2
  exit 1
}

[[ "$domain" =~ ^[A-Za-z0-9.-]+$ ]] || {
  echo "Invalid domain: ${domain}" >&2
  exit 1
}

[[ "$upstream_port" =~ ^[0-9]+$ ]] || {
  echo "Invalid upstream port: ${upstream_port}" >&2
  exit 1
}

render_template() {
  local template="$1"
  local output="$2"
  sed -e "s/__DOMAIN__/${domain}/g" -e "s/__UPSTREAM_PORT__/${upstream_port}/g" "$template" > "$output"
}

restore_previous_config() {
  local status=$?
  trap - ERR
  if [[ -n "$backup_path" && -f "$backup_path" ]]; then
    cp -p "$backup_path" "$vhost_path"
    "$nginx_bin" -t && "$nginx_bin" -s reload
  elif [[ -f "$vhost_path" ]]; then
    "$nginx_bin" -t && "$nginx_bin" -s reload
  fi
  exit "$status"
}

trap restore_previous_config ERR

resolved_ips="$(getent ahostsv4 "$domain" | awk '{print $1}' | sort -u)"
if [[ -z "$resolved_ips" ]]; then
  echo "${domain} does not have an IPv4 DNS record." >&2
  exit 1
fi
if [[ -n "$expected_public_ip" ]] && ! grep -Fxq "$expected_public_ip" <<< "$resolved_ips"; then
  echo "${domain} does not resolve to ${expected_public_ip}." >&2
  exit 1
fi

mkdir -p "$vhost_dir" "$webroot"
if [[ -f "$vhost_path" ]]; then
  backup_path="${vhost_path}.backup-$(date +%Y%m%d%H%M%S)"
  cp -p "$vhost_path" "$backup_path"
fi

http_config="$(mktemp)"
https_config="$(mktemp)"
trap 'rm -f "$http_config" "$https_config"' EXIT

render_template "$repo_dir/deploy/nginx/askpanshi.http.conf.template" "$http_config"
install -m 0644 "$http_config" "$vhost_path"
"$nginx_bin" -t
"$nginx_bin" -s reload

certbot_args=(certonly --webroot -w "$webroot" -d "$domain" --non-interactive --agree-tos --keep-until-expiring)
if [[ -n "$email" ]]; then
  certbot_args+=(--email "$email")
else
  certbot_args+=(--register-unsafely-without-email)
fi
certbot "${certbot_args[@]}"

render_template "$repo_dir/deploy/nginx/askpanshi.https.conf.template" "$https_config"
install -m 0644 "$https_config" "$vhost_path"
"$nginx_bin" -t
"$nginx_bin" -s reload

trap - ERR
echo "Configured https://${domain} -> http://127.0.0.1:${upstream_port}."
