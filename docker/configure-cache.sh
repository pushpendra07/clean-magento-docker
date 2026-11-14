#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html
engine=${CACHE_ENGINE:-valkey}
case "$engine" in redis|valkey) ;; *) echo 'CACHE_ENGINE must be redis or valkey' >&2; exit 2;; esac
php bin/magento setup:config:set --no-interaction \
  --cache-backend="$engine" \
  "--cache-backend-$engine-server=$engine" "--cache-backend-$engine-db=0" \
  --page-cache="$engine" \
  "--page-cache-$engine-server=$engine" "--page-cache-$engine-db=1" \
  --session-save="$engine" \
  "--session-save-$engine-host=$engine" "--session-save-$engine-db=2" \
  --http-cache-hosts=varnish:80
php bin/magento cache:flush
printf '%s\n' "$engine" > app/etc/.cache-engine
echo "Cache and sessions now use $engine. Existing sessions may require login again."
