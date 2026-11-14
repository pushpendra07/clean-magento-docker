#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html
# In development, keep PHP-created bind-mounted files owned by the host user.
if [ -n "${DEV_UID:-}" ]; then
    case "$DEV_UID:${DEV_GID:-}" in *[!0-9:]*|:*) echo 'DEV_UID and DEV_GID must be numeric' >&2; exit 2;; esac
    if [ "$DEV_UID" -eq 0 ] || [ -z "${DEV_GID:-}" ]; then
        echo 'Development mode requires a non-root host user and DEV_GID.' >&2; exit 2
    fi
    if ! getent group "$DEV_GID" >/dev/null; then groupadd -g "$DEV_GID" magento-dev; fi
    if [ "$(id -u www-data)" != "$DEV_UID" ] || [ "$(id -g www-data)" != "$DEV_GID" ]; then
        usermod -u "$DEV_UID" -g "$DEV_GID" www-data
    fi
fi
if [ "${1:-}" != install ]; then
    if [ "${1:-}" = php-fpm ]; then exec docker-php-entrypoint "$@"; fi
    exec gosu www-data "$@"
fi
case "${CACHE_ENGINE:-valkey}" in redis|valkey) ;; *) echo 'CACHE_ENGINE must be redis or valkey' >&2; exit 2;; esac
mkdir -p app/etc pub/media var generated pub/static /varnish
chown -R www-data:www-data app/etc pub/media var generated pub/static /varnish
mage() { gosu www-data php bin/magento "$@"; }
if [ ! -f app/etc/env.php ]; then
    echo 'Installing clean Magento...'
    mage setup:install \
      --base-url="$BASE_URL" \
      --db-host=db --db-name=magento --db-user=magento --db-password="$DB_PASSWORD" \
      --search-engine=opensearch --opensearch-host=search --opensearch-port=9200 \
      --opensearch-enable-auth=0 --opensearch-index-prefix=magento2 \
      --amqp-host=rabbitmq --amqp-port=5672 --amqp-user="$RABBITMQ_USER" --amqp-password="$RABBITMQ_PASSWORD" \
      --backend-frontname=admin --admin-user="$ADMIN_USER" \
      --admin-password="$ADMIN_PASSWORD" --admin-email="$ADMIN_EMAIL" \
      --admin-firstname=Store --admin-lastname=Admin \
      --language=en_US --currency=USD --timezone=UTC --use-rewrites=1 \
      --session-save=files \
      --disable-modules=Magento_TwoFactorAuth,Magento_AdminAdobeImsTwoFactorAuth
fi
gosu www-data php /usr/local/bin/configure-runtime.php
if [ ! -f app/etc/.cache-engine ] || [ "$(cat app/etc/.cache-engine)" != "$CACHE_ENGINE" ]; then
    gosu www-data configure-cache
fi
if [ ! -f app/etc/.docker-ready ]; then
    mage module:enable Local_ErpConnector
    mage setup:upgrade
    mage deploy:mode:set developer
    mage config:set system/full_page_cache/caching_application 2
    mage setup:static-content:deploy -f en_US
    mage indexer:reindex
    mage cache:flush
    gosu www-data touch app/etc/.docker-ready
fi
mage varnish:vcl:generate --export-version=6 --backend-host=nginx --backend-port=8080 \
  --access-list=127.0.0.1 --access-list=172.16.0.0/12 --access-list=192.168.0.0/16 --output-file=/varnish/default.vcl
chmod 644 /varnish/default.vcl
echo 'Magento initialization complete.'
