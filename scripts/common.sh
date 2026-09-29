#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${RUSTDESK_ENV_FILE:-$ROOT_DIR/.env}"
COMPOSE_FILE="$ROOT_DIR/compose.yaml"

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ROOT_DIR/.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE from .env.example"
  fi
}

require_docker_cli() {
  command -v docker >/dev/null 2>&1 || {
    echo "Docker CLI was not found." >&2
    return 1
  }
  docker compose version >/dev/null
}

require_docker_daemon() {
  docker info >/dev/null 2>&1 || {
    echo "Docker daemon is not reachable. Start Docker and retry." >&2
    return 1
  }
}

compose() {
  docker compose \
    --project-directory "$ROOT_DIR" \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    "$@"
}

env_value() {
  local name="$1" value=""
  if [[ -n "${!name:-}" ]]; then
    printf '%s' "${!name}"
    return
  fi
  value="$(sed -n -E "s/^${name}=(.*)$/\1/p" "$ENV_FILE" | tail -n 1)"
  printf '%s' "$value"
}

validate_exposure() {
  local bind public_host
  bind="$(env_value RUSTDESK_BIND_ADDRESS)"
  public_host="$(env_value RUSTDESK_PUBLIC_HOST)"
  bind="${bind:-127.0.0.1}"
  public_host="${public_host:-127.0.0.1}"

  if [[ "$bind" != "127.0.0.1" && "$bind" != "::1" ]]; then
    case "$public_host" in
      127.0.0.1|localhost|rustdesk.example.com|"")
        echo "Refusing public bind with placeholder RUSTDESK_PUBLIC_HOST=$public_host" >&2
        echo "Set a reachable DNS name/IP in $ENV_FILE first." >&2
        return 1
        ;;
    esac
  fi
}
