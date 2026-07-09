#!/bin/sh
set -e

git config --global --add safe.directory '*'

if [ -n "$MATRIX_DEBUG" ] && echo "$MATRIX_DEBUG" | grep -qE '^(1|true|yes|on)$' >/dev/null 2>&1; then
    echo "[entrypoint] Applied safe.directory=* (HOME=${HOME}, UID=$(id -u))" >&2
    git config --global --get-all safe.directory >&2 || true
fi

exec "$@"
