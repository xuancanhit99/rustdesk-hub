#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

ensure_env
require_docker_cli
compose config --quiet
require_docker_daemon

compose ps

failed=0
for service in hbbs hbbr; do
  container_id="$(compose ps --quiet "$service")"
  if [[ -z "$container_id" ]]; then
    echo "$service: not created" >&2
    failed=1
    continue
  fi

  running="$(docker inspect --format '{{.State.Running}}' "$container_id")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container_id")"
  echo "$service: running=$running health=$health"
  if [[ "$running" != "true" || "$health" != "healthy" ]]; then
    failed=1
  fi
done

if [[ "$failed" -eq 0 ]]; then
  public_key="$(compose exec --no-TTY hbbs sh -c 'cat /data/id_ed25519.pub 2>/dev/null || true')"
  if [[ -n "$public_key" ]]; then
    echo "RustDesk client public key: $public_key"
  else
    echo "RustDesk client public key is not available yet." >&2
    failed=1
  fi
else
  echo "RustDesk client public key check skipped because a service is unhealthy." >&2
fi

exit "$failed"
