#!/bin/sh
set -e
# Drop from root to non-root app user; ensure /data is writable on first use with a volume.
if [ "$(id -u)" = "0" ]; then
  chown -R app:app /data
  exec runuser -u app -- "$@"
fi
exec "$@"
