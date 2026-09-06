#!/bin/sh
set -e

git config --global --add safe.directory "*" > /dev/null 2>&1

exec "$@"
