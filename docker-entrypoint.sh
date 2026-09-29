#!/bin/sh
set -eu

umask 077

case "${1:-}" in
  hbbs|hbbr)
    if [ "$(id -u)" = "0" ]; then
      mkdir -p /data
      chown -R rustdesk:rustdesk /data
      if [ -f /data/id_ed25519 ]; then
        chmod 0600 /data/id_ed25519
      fi
      exec su-exec rustdesk "$@"
    fi
    ;;
esac

exec "$@"
