FROM composer:2.10 AS composer
FROM php:8.5-fpm-bookworm AS app
ARG MAGENTO_VERSION=2.4.9
ENV COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_MEMORY_LIMIT=-1
ADD https://github.com/mlocati/docker-php-extension-installer/releases/download/2.11.12/install-php-extensions /usr/local/bin/install-php-extensions
RUN chmod +x /usr/local/bin/install-php-extensions \
    && install-php-extensions bcmath ftp gd intl pdo_mysql soap sockets xsl zip opcache igbinary \
    && apt-get update \
    && apt-get install -y --no-install-recommends git unzip curl gosu \
    && rm -rf /var/lib/apt/lists/*
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
WORKDIR /var/www/html
RUN composer create-project --repository-url=https://mirror.mage-os.org/ \
      magento/project-community-edition=${MAGENTO_VERSION} . --no-install --no-interaction \
    && composer config repositories.0 composer https://mirror.mage-os.org/
COPY src/composer.json src/composer.lock /var/www/html/
RUN composer install --no-interaction --prefer-dist --no-progress
COPY src/app/code/Local/ErpConnector /var/www/html/app/code/Local/ErpConnector
COPY docker/php.ini /usr/local/etc/php/conf.d/magento.ini
COPY docker/fpm.conf /usr/local/etc/php-fpm.d/zz-local.conf
COPY docker/entrypoint.sh /usr/local/bin/magento-entrypoint
COPY docker/configure-cache.sh /usr/local/bin/configure-cache
COPY docker/configure-runtime.php /usr/local/bin/configure-runtime.php
RUN chmod +x /usr/local/bin/magento-entrypoint /usr/local/bin/configure-cache \
    && mkdir -p var generated pub/static pub/media \
    && chown -R www-data:www-data /var/www/html
ENTRYPOINT ["magento-entrypoint"]
CMD ["php-fpm", "-F"]

FROM nginx:1.30 AS nginx
COPY --from=app /var/www/html /var/www/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
