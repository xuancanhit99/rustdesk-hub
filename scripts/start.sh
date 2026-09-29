#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

ensure_env
require_docker_cli
validate_exposure
compose config --quiet
require_docker_daemon

compose up --detach --build --wait --wait-timeout 180
"$SCRIPT_DIR/status.sh"
