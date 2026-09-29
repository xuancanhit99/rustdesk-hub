#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

purge_data=false
confirmed=false
for arg in "$@"; do
  case "$arg" in
    --purge-data) purge_data=true ;;
    --yes) confirmed=true ;;
    *) echo "Usage: $0 [--purge-data --yes]" >&2; exit 2 ;;
  esac
done

ensure_env
require_docker_cli
require_docker_daemon

if [[ "$purge_data" == "true" ]]; then
  if [[ "$confirmed" != "true" ]]; then
    echo "Data purge requires both --purge-data and --yes." >&2
    exit 2
  fi
  compose down --remove-orphans --volumes
  echo "Stopped RustDesk Hub and deleted its named data volume."
else
  compose down --remove-orphans
  echo "Stopped RustDesk Hub; keys and database were preserved."
fi
