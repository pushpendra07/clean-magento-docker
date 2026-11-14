# Clean Magento Docker + basic ERP

A new local development environment built from public base images and Magento source. It does not use the SellerRefund assignment images or data. The only custom Magento module is the small ERP connector in `src/app/code/Local/ErpConnector`.

## Guide contents

- [Development mode and PhpStorm](#development-mode-and-phpstorm)
- [Fresh setup](#fresh-setup-run-these-steps-in-order)
- [Daily start, stop and restart](#daily-start-stop-and-restart-commands)
- [Magento and container commands](#run-magento-and-container-commands)
- [Inspect vendor files](#inspect-magento-vendor-files)
- [Edit code and rebuild](#edit-code-and-rebuild-images)
- [Redis or Valkey](#choose-redis-or-valkey)
- [ERP integration](#basic-erp-integration)
- [Database backup and restore](#back-up-and-restore-the-magento-database)
- [Reset to a fresh install](#reset-everything-to-a-fresh-installation)
- [Build and publish images](#build-and-publish-your-own-images)
- [Troubleshooting](#troubleshooting-commands)
- [Reduce local disk usage](#reduce-local-disk-usage)
- [Validation](#validation-commands)

## Components

| Service | Version / role |
|---|---|
| Magento Open Source | 2.4.9 (latest stable release verified November 14, 2026) |
| PHP-FPM | 8.5 |
| Nginx | 1.30 |
| MariaDB | 12.3 |
| OpenSearch | 3.5.0 |
| RabbitMQ | 4.3 with management UI |
| Varnish | 8, Magento-generated VCL |
| Valkey | 9, default Magento cache and session backend |
| Redis | 7.2, selectable alternative cache and session backend |
| phpMyAdmin | 5 |
| ERP | Python 3.13, SQLite, simple browser dashboard |

Versions follow [Adobe's system requirements](https://experienceleague.adobe.com/en/docs/commerce-operations/installation-guide/system-requirements). Adobe lists Valkey for 2.4.9; the Redis option is a custom development configuration supported by Magento's Redis configuration options, outside that published matrix. Magento comes from the public [Mage-OS mirror](https://mirror.mage-os.org/) without Marketplace credentials. The base release is pinned; review Adobe security hotfixes separately before any public deployment. No production deployment is configured.

## Fresh setup: run these steps in order

Use Terminal on macOS/Linux, or a WSL2 terminal on Windows. The helper scripts require Bash. Run commands on your computer, **from the `clean-magento-docker` project directory**, unless a step says otherwise. Docker commands below run programs inside containers; PHP, Composer, MariaDB and Node.js do not need to be installed on your computer.

### 1. Start Docker and check prerequisites

Install Git, OpenSSL, and Docker with Compose. Start Docker Desktop or OrbStack before continuing. Allow approximately 10–12 GB RAM and ample disk space for Magento builds.

```bash
git --version
openssl version
docker --version
docker compose version
docker info
```

`docker info` must return engine information. If it reports a connection error, start your Docker application and run it again.

On Linux only, OpenSearch may require this command **on the Docker host**:

```bash
sudo sysctl -w vm.max_map_count=262144
```

### 2. Clone the public repository

The repository is public. Clone it over HTTPS without a GitHub login:

```bash
mkdir -p ~/MyDevelopment
cd ~/MyDevelopment
git clone https://github.com/pushpendra07/clean-magento-docker.git
cd clean-magento-docker
```

This guide uses `~/MyDevelopment/clean-magento-docker` as the example project directory. You can clone into another location; use that location in subsequent `cd` commands. If you already cloned the repository, open your existing project directory instead of cloning again:

```bash
cd ~/MyDevelopment/clean-magento-docker
```

Confirm you are in the project directory:

```bash
pwd
ls
```

You should see `compose.yaml`, `Dockerfile`, `bin`, `docker`, `erp`, and `src`.

### 3. Create and edit local settings

Generate local settings. This creates an ignored `.env` file and fills blank password/token fields with random values. Existing non-empty settings are preserved:

```bash
bin/setup
nano .env
```

In nano, save with **Ctrl+O**, press **Enter**, then exit with **Ctrl+X**. You can also edit `.env` in your usual editor.

Choose one cache engine before the first installation:

```dotenv
CACHE_ENGINE=valkey
```

Or change that line to:

```dotenv
CACHE_ENGINE=redis
```

Keep only one `CACHE_ENGINE` line. Both services run; Magento uses your selection for cache and sessions. Varnish handles full-page caching in either case.

Default ports and credential locations are shown below. Passwords and the ERP API token are generated on your machine; the repository contains no preset values. Review `.env` locally before first installation.

| Setting | Default | Purpose |
|---|---|---|
| `WEB_PORT` | `8090` | Storefront and Admin port |
| `BASE_URL` | `http://localhost:8090/` | Must match `WEB_PORT`, including the trailing slash |
| `PHPMYADMIN_PORT` | `8091` | phpMyAdmin port |
| `ERP_PORT` | `8092` | ERP dashboard/API port |
| `RABBITMQ_PORT` | `15673` | RabbitMQ management port |
| `ADMIN_USER` | `admin` | Initial Magento administrator |
| `ADMIN_PASSWORD` | Generated locally in `.env` | Initial administrator password |
| `DB_PASSWORD` | Generated locally in `.env` | MariaDB `magento` user password |
| `DB_ROOT_PASSWORD` | Generated locally in `.env` | MariaDB root password |
| `RABBITMQ_USER` | `magento` | RabbitMQ user |
| `RABBITMQ_PASSWORD` | Generated locally in `.env` | RabbitMQ password |
| `ERP_API_TOKEN` | Generated locally in `.env` | Shared Magento-to-ERP API token |

For example, if port 8090 is busy, set **both** `WEB_PORT=8095` and `BASE_URL=http://localhost:8095/` before installation. The other ports can be changed independently. For a separate second store, also use a different `COMPOSE_PROJECT_NAME`.

Keep `.env` local and do not commit or share its values. `.env` and environment-file variants are ignored by Git; `.env.example` contains blank secret fields. Changing database credentials or the initial Admin password in `.env` after installation does not update existing database users or Magento accounts; change those through MariaDB/Magento first.

### 4. Validate configuration and build/start everything

```bash
docker compose config --quiet
bin/dev
```

This starts the IDE-friendly development mode. For image-only use, run `bin/start` instead; vendor then stays inside the image.

No output from `config --quiet` means the Compose configuration is valid. `bin/dev` builds the Magento PHP, Nginx and ERP images, prepares the local `src` tree (including vendor), starts the infrastructure, installs Magento into the empty database, configures the cache engine, generates static assets and Varnish configuration, and waits for the stack to become ready.

The first run can take several minutes. Keep this terminal open until it finishes. In a **second terminal**, enter the same project directory and watch installation:

```bash
cd ~/MyDevelopment/clean-magento-docker
docker compose logs -f init
```

If you cloned elsewhere, replace that `cd` path with your project's location. Press **Ctrl+C** to stop following logs; the containers keep running.

For the image-only alternative on a fresh clone, these explicit commands are equivalent to `bin/start`. They do not prepare the development source tree:

```bash
bin/setup
docker compose build init nginx erp
docker compose up -d --wait --wait-timeout 2400
```

Do not run both alternatives at the same time.

### 5. Check status and open the applications

```bash
docker compose ps -a
```

The `init` container should show **Exited (0)**: it is a successful one-time installer, not a service that must stay running. PHP, Nginx, Varnish, database, search, Redis, Valkey, RabbitMQ and ERP should become healthy. Cron and phpMyAdmin should be running; they do not have separate Compose healthchecks.

| Application | Default URL | Login |
|---|---|---|
| Storefront | http://localhost:8090 | No products or customers initially |
| Magento Admin | http://localhost:8090/admin | `ADMIN_USER` / `ADMIN_PASSWORD` from your local `.env` |
| phpMyAdmin | http://localhost:8091 | User `magento`, `DB_PASSWORD` from your local `.env` |
| Basic ERP | http://localhost:8092 | No dashboard login for local use |
| RabbitMQ management | http://localhost:15673 | `RABBITMQ_USER` / `RABBITMQ_PASSWORD` from your local `.env` |

Use your local `.env` for generated credentials and any changed ports. In phpMyAdmin, the database is `magento`; the server is already configured as `db`.

```bash
curl -I http://localhost:8090/
curl -fsS http://localhost:8092/health
```

All host ports bind to `127.0.0.1`. Database, search, Redis, Valkey and PHP ports remain inside Docker. Magento runs in developer mode, with Admin two-factor authentication disabled for this local environment.

## Daily start, stop and restart commands

Run these from the project directory. All commands here preserve named volumes and the data in them.

| Task | Command |
|---|---|
| Start after `bin/stop`, using existing images | `docker compose up -d --wait --wait-timeout 2400` |
| Start/resume IDE development | `bin/dev` |
| Rebuild images and start the selected mode | `bin/start` |
| Stop and remove project containers/network | `bin/stop` |
| Pause all project containers without removing them | `docker compose stop` |
| Resume paused containers | `docker compose start` |
| Show status, including the installer | `docker compose ps -a` |
| Follow all service logs | `docker compose logs -f --tail=100` |
| Follow installer logs | `docker compose logs -f init` |
| Follow ERP logs | `docker compose logs -f erp` |
| Restart ERP after a configuration change | `docker compose up -d --force-recreate erp` |

A full stop/start is a reliable way to restart the web stack together:

```bash
bin/stop
docker compose up -d --wait --wait-timeout 2400
```

For container command help:

```bash
docker compose --help
docker compose logs --help
```

## Run Magento and container commands

`bin/magento` runs Magento CLI inside the PHP container as the application user. Start the stack first. Add Magento arguments after the helper:

```bash
bin/magento --version
bin/magento list
bin/magento help cache:flush
bin/magento cache:status
bin/magento cache:flush
bin/magento indexer:status
bin/magento indexer:reindex
bin/magento module:status Local_ErpConnector
bin/magento setup:db:status
```

The direct equivalent of the cache command is:

```bash
docker compose exec -u www-data php php bin/magento cache:flush
```

Here the first `php` names the Compose service, and the second `php` runs the PHP executable inside it.

Open a shell inside the PHP container:

```bash
docker compose exec -u www-data php bash
```

Inside that shell, the working directory is `/var/www/html`, so run commands without the `bin/magento` host helper:

```bash
php bin/magento --version
php bin/magento cache:flush
exit
```

Inspect Magento logs from the host:

```bash
docker compose exec -u www-data php tail -n 100 var/log/system.log
docker compose exec -u www-data php tail -n 100 var/log/exception.log
```

A log file may not exist until Magento writes its first entry.

Cron runs automatically every minute. To inspect queues or trigger a scheduler pass manually:

```bash
bin/magento queue:consumers:list
bin/magento cron:run
docker compose logs --tail=100 cron
```

Magento's configured cron runner starts its queue consumers. ERP delivery in this starter uses HTTP directly, not a RabbitMQ consumer.

## Development mode and PhpStorm

Use development mode for daily Magento work. It stores the full Magento tree on your computer in `src`, including `src/vendor`, and bind-mounts the same tree into PHP, Nginx, cron and the installer. Code edits are visible without rebuilding images. This requires Docker Compose 2.24.4 or later.

From the repository root:

```bash
bin/setup
bin/dev
```

On the first run, `bin/dev` builds the images, copies Magento and its dependencies into `src`, and preserves existing files such as your custom modules. For an existing image-based store, it also imports the current configuration, media and runtime files from its named volumes. It stops web requests/cron during this import; the database is preserved. A fresh clone gets a fresh Magento installation.

The helper saves `COMPOSE_FILE=compose.yaml:compose.dev.yaml` and your user/group IDs in the ignored `.env`. All normal `docker compose`, `bin/magento`, `bin/composer`, `bin/stop` and cache-switch commands then use the development mounts automatically. Subsequent `bin/dev` calls reuse local source and images. After Dockerfile/PHP-extension changes, run `docker compose build init nginx` before restarting the stack.

```text
clean-magento-docker/
├── compose.yaml
├── compose.dev.yaml
├── Dockerfile
└── src/
    ├── composer.json        # tracked
    ├── composer.lock        # tracked
    ├── app/code/            # tracked custom modules
    ├── app/design/          # tracked custom themes
    ├── vendor/              # local dependencies, ignored by Git
    ├── app/etc/env.php      # local Magento configuration, ignored
    ├── generated/           # ignored
    ├── var/                 # ignored
    └── pub/                 # generated/core files and media, ignored
```

`src/.gitignore` keeps the downloaded Magento tree and local credentials out of Git while allowing Composer files and custom code/themes. Runtime source and credentials are also excluded from the Docker build context. Do not delete `src` to restart the store: in development mode it contains your active configuration and media. `docker compose down --volumes` does not delete these host files. Keep using development mode for that store; switching back to the base file alone would use the older named-volume configuration/media.

### Open and configure PhpStorm

1. Open **`src`** as the PhpStorm project. Wait for indexing. `vendor` is now a real local directory; Composer packages can also appear under External Libraries.
2. In **Settings → Build, Execution, Deployment → Docker**, add/test your Docker Desktop or OrbStack connection.
3. In **Settings → PHP**, add a CLI interpreter from **Docker Compose**. Select `../compose.yaml` and `../compose.dev.yaml`, service **`php`**, executable **`/usr/local/bin/php`**, and use the existing running container.
4. Map the local `src` directory to **`/var/www/html`**. Set the PHP language level to **8.5**.
5. In **Settings → PHP → Composer**, select local `composer.json`, the Docker interpreter, and Composer executable **`/usr/local/bin/composer`**.
6. If using PHPUnit, select the same interpreter and `/var/www/html/vendor/autoload.php` as the Composer autoloader.
7. Exclude `var`, `generated`, `pub/static` and `pub/media` from indexing. Keep vendor available as Composer library sources.

The commands in this README run from the **repository root**, one directory above `src`. If PhpStorm's terminal opens in `src`, run `cd ..` first. Other IDEs can open `src` directly because every dependency is present locally. Xdebug is not installed by this change; code browsing, CLI execution and tests work without it.

### Daily development commands

```bash
bin/dev
bin/magento cache:flush
bin/magento indexer:reindex
bin/composer install
bin/composer show magento/product-community-edition
bin/stop
```

Run `composer install` through the helper so Composer uses the container's PHP version and updates local `src/vendor`. Commit intentional changes to `src/composer.json` and `src/composer.lock`; never commit vendor. Avoid editing vendor files as the permanent fix; use custom modules or managed patches.

| Change | Development command |
|---|---|
| PHP logic in a custom module | Save and refresh; flush Magento cache if the response is cached |
| Templates or configuration XML | `bin/magento cache:flush` |
| Dependency injection / constructors | Remove affected generated factories/proxies/interceptors, then `bin/magento cache:clean` |
| New module | `bin/magento module:enable Vendor_Module`, then `bin/magento setup:upgrade` |
| Database schema | `bin/magento setup:upgrade` |
| Theme JS/CSS/LESS | Remove the affected generated static assets, then hard-reload the browser; developer mode regenerates them |

In developer mode, generated classes and static assets are created on demand. Do not routinely run `setup:di:compile` or `setup:static-content:deploy`; use those for deployment/build workflows. After a constructor change, remove the affected files under `src/generated/code` so Magento regenerates them. See [Adobe development recommendations](https://experienceleague.adobe.com/en/docs/commerce-operations/performance-best-practices/development-environment).

### Inspect Magento vendor files

After `bin/dev`, browse `src/vendor/magento` directly in your IDE. You can still inspect the same files through Docker:

```bash
ls src/vendor/magento
bin/composer show magento/product-community-edition
docker compose exec -u www-data php bash
```

Inside the container:

```bash
cd /var/www/html
cat vendor/magento/module-page-cache/etc/module.xml
exit
```

In the original image-only mode, vendor remains inside the image; `bin/dev` is what makes it local and shared.

## Edit code and rebuild images

In development mode, edit custom modules under `src/app/code` and themes under `src/app/design`. Changes use the live mounts described above.

In the base image-only mode, application code is copied into images. After editing custom code or Docker/PHP/Nginx configuration, rebuild and restart:

```bash
bin/stop
docker compose build init nginx
docker compose up -d --wait --wait-timeout 2400
bin/magento cache:flush
```

The image build installs dependencies from the committed `src/composer.lock`. To change dependencies, run Composer inside the development container and commit both Composer files. If changing the Magento release, update the Composer requirement/lock file and image release setting together; this starter does not automate existing-store version upgrades.

After changing only the ERP server or dashboard:

```bash
docker compose build erp
docker compose up -d --no-deps --wait erp
```

## Choose Redis or Valkey

Before the first start:

```dotenv
CACHE_ENGINE=valkey
# or CACHE_ENGINE=redis
```

For an installed store, run **one** of these commands from the project directory. The helper updates `.env` as well as Magento's installed configuration.

Switch to Redis:

```bash
bin/switch-cache redis
```

Switch back to Valkey:

```bash
bin/switch-cache valkey
```

Check the result:

```bash
docker compose ps -a
bin/magento cache:status
```

Editing `.env` by itself does not reconfigure a running store; use the helper for an installed store.

The helper stops Varnish, Nginx, PHP and cron while updating shared Magento configuration, clears the selected engine's Magento cache, records the choice in `.env`, and recreates the web services and cron together. Application cache uses database 0, the fallback page-cache backend uses database 1, and sessions use database 2. Switching engines requires users to sign in again; old session data is left in the previous engine. Varnish remains the full-page cache in either case. Do not switch during an active checkout.

## Request flow

```text
Browser → Varnish → Nginx → PHP-FPM / Magento → MariaDB
                                ├── OpenSearch
                                ├── selected Redis or Valkey
                                ├── RabbitMQ (Magento queues / cron consumers)
                                └── ERP HTTP API → SQLite → basic ERP dashboard
```

The init container installs Magento and generates Varnish's VCL from this Magento release. Nginx and PHP each contain source from the same Docker build. Named volumes share runtime configuration, media and static assets. Cron runs Magento's scheduler every minute; Magento's configured cron consumer runner starts its queue consumers against RabbitMQ. RabbitMQ is wired into Magento's native queues; this basic ERP connector sends HTTP synchronously rather than through RabbitMQ.

## Basic ERP integration

The dashboard has counts and tables for products, orders, customers and the latest 200 integration requests. The entity table shows the latest 500 records. A new ERP database starts in **Pending** mode:

- **Pending:** incoming payload is saved, HTTP 202 returned, entity awaits your Accept/Fail decision.
- **Accept automatically:** incoming payload is saved, entity is upserted, HTTP 200 returned.
- **Fail automatically:** payload and failure are saved, HTTP 503 returned, no entity is updated.

Use the demo buttons to try each mode without Magento. Open View JSON to inspect a request. Accept applies it to ERP records; Fail records a manual failure. A failed request can later be accepted. Accepting an older request overwrites the entity with that older payload, so process revisions in order.

The Magento connector sends changes after a product, customer or order is committed. It sends basic fields and order line items, never passwords or payment information. ERP uses the Magento entity ID to update an existing record rather than create duplicates. Each delivery remains a separate request in the log. This is one-way Magento → ERP integration. Deletes and ERP → Magento writes are not implemented.

To test real Magento traffic:

1. Open ERP and select an integration mode.
2. Create/save a simple product in Magento Admin (name, SKU, price, stock and website assignment).
3. Create/save a customer; place an order or create one in Admin to send order data.
4. Review the ERP request and Accept/Fail it if pending.
5. Change the mode to Fail automatically and save again to test a failure.

The connector has a three-second HTTP timeout and logs errors in Magento `var/log`. An ERP failure does not undo a Magento save. There is no durable Magento outbox or automatic delivery retry in this intentionally basic connector. If ERP was offline, save the entity again after ERP recovers; if ERP received and recorded a failed request, accept it from the dashboard. Manual acceptance changes ERP state only and cannot change the already-returned HTTP response or Magento logs.

### Send ERP API requests from your terminal

Run these commands on your computer from the project directory. Set the URL to match your ERP port; read the API token from the ignored local `.env` without printing it. Do not paste token values into this README or commit them. These requests create demonstration records in ERP, not in Magento.

```bash
ERP_URL=http://localhost:8092
ERP_TOKEN=$(sed -n 's/^ERP_API_TOKEN=//p' .env)
```

Send a product:

```bash
curl -i -X POST "$ERP_URL/api/products" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ERP_TOKEN" \
  -d '{"external_id":"demo-product-1","sku":"DEMO-1","name":"Demo product","price":25}'
```

Send a customer:

```bash
curl -i -X POST "$ERP_URL/api/customers" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ERP_TOKEN" \
  -d '{"external_id":"demo-customer-1","email":"demo@example.com","firstname":"Demo","lastname":"Customer"}'
```

Send an order:

```bash
curl -i -X POST "$ERP_URL/api/orders" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ERP_TOKEN" \
  -d '{"external_id":"demo-order-1","increment_id":"DEMO-1001","total":25,"currency":"USD","status":"pending","items":[{"sku":"DEMO-1","qty":1,"price":25}]}'
```

Open the ERP dashboard to inspect each request. Select Pending, Accept automatically, or Fail automatically and click **Save mode** before sending a new request. `curl -i` prints the HTTP response code: expect `202`, `200`, or the intentionally simulated `503` respectively. A `401` response means the API token does not match `.env`.

Also available: `/api/orders` and `/api/customers`; all require a JSON object with an `external_id`. `/health` is the health endpoint. The dashboard is intentionally unauthenticated for local use, and its controls enforce same-origin browser requests. Do not expose this ERP to a public network.

## Back up and restore the Magento database

These commands back up **only the Magento database**. Keep the matching `.env`, Magento deployment configuration (including its encryption key), media, and ERP data separately if you need to migrate or recover the entire environment. A database dump alone is not a complete store backup.

Create the database backup outside the Git repository:

```bash
mkdir -p ../clean-magento-backups
docker compose exec -T db sh -c 'exec mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction --routines --triggers --events magento' > ../clean-magento-backups/magento.sql
```

To restore that dump to this same environment, first stop web requests and cron. **Restoring replaces database contents present in the dump**; keep a backup of the current database first.

```bash
docker compose stop varnish nginx php cron
docker compose exec -T db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" magento' < ../clean-magento-backups/magento.sql
docker compose run --rm --no-deps init php bin/magento cache:flush
docker compose up -d --wait --wait-timeout 2400
```

## Reset everything to a fresh installation

**Destructive, image-only mode:** this procedure deletes this Compose project's Magento database, media, deployment configuration, Redis/Valkey data, RabbitMQ data, and ERP database.** It also removes the users, products, orders and integration requests you created. Back up anything you need before running it. These are instructions only; do not run them for a normal restart.

From the correct project directory, with the same `COMPOSE_PROJECT_NAME` used to create your store:

```bash
docker compose down --volumes --remove-orphans
bin/start
```

This reset procedure applies to image-only mode. In development mode, `src/app/etc`, media and other local files survive volume removal; do not use this as a fresh-store reset. Back up your local source/configuration/media and create a separate clone with a different Compose project name for a clean development store.

In image-only mode, the next start installs a clean store using the current `.env` settings. Keep `.env` if you want the same ports/passwords, or edit it before `bin/start`. Existing images are reused unless source changes require a rebuild.

## Build and publish your own images

Build locally from the project directory:

```bash
docker compose build init nginx erp
docker image ls clean-magento-php
docker image ls clean-magento-nginx
docker image ls clean-magento-erp
```

This produces `clean-magento-php:local`, `clean-magento-nginx:local` and `clean-magento-erp:local`. MariaDB and other infrastructure use their public vendor images, initialized from scratch at runtime. Runtime databases, credentials and media are stored in volumes, not included in the images.

To publish, authenticate to GHCR using a GitHub account/token that can write packages:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

When prompted for the password, enter your GitHub package access token. Replace `YOUR_USER` in all commands below with your lowercase registry namespace:

```bash
docker tag clean-magento-php:local ghcr.io/YOUR_USER/clean-magento-php:2.4.9
docker tag clean-magento-nginx:local ghcr.io/YOUR_USER/clean-magento-nginx:2.4.9
docker tag clean-magento-erp:local ghcr.io/YOUR_USER/clean-magento-erp:1.0.0
docker push ghcr.io/YOUR_USER/clean-magento-php:2.4.9
docker push ghcr.io/YOUR_USER/clean-magento-nginx:2.4.9
docker push ghcr.io/YOUR_USER/clean-magento-erp:1.0.0
```

### Start from published images on another machine

Clone the repository and run `bin/setup` as described above. Set these lines in `.env` to your published references:

```dotenv
MAGENTO_IMAGE=ghcr.io/YOUR_USER/clean-magento-php:2.4.9
NGINX_IMAGE=ghcr.io/YOUR_USER/clean-magento-nginx:2.4.9
ERP_IMAGE=ghcr.io/YOUR_USER/clean-magento-erp:1.0.0
```

Public images can be pulled without authentication. Repository visibility and GHCR package visibility are separate: making this source repository public does not automatically make published images public. If your published images are private, first authenticate with an account/token that can read them:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Then pull and start without building:

```bash
docker compose pull
docker compose up -d --no-build --wait --wait-timeout 2400
```

Use these explicit commands rather than `bin/start` when you want to run published images without rebuilding. The init service still installs a new store into empty volumes. Builds target the host architecture; multi-architecture publication requires a buildx pipeline. The image build installs the pinned Magento release and dependencies from the committed Composer lock file.

## Troubleshooting commands

| Symptom | Check / action |
|---|---|
| Cannot connect to Docker | Start Docker Desktop/OrbStack, then run `docker info` |
| `.env` variable is missing | Run `bin/setup` to fill blank credentials, then run `docker compose config --quiet` |
| Port already allocated | Edit the matching port in `.env`; update `BASE_URL` too if changing `WEB_PORT` |
| Installer exited with an error | Run `docker compose logs --tail=100 init` |
| OpenSearch is unhealthy | Run `docker compose logs --tail=100 search`; check Docker RAM and Linux `vm.max_map_count` |
| Storefront is unavailable | Run `docker compose ps -a` and `docker compose logs --tail=100 php nginx varnish` |
| ERP request failed | Inspect the ERP dashboard, `docker compose logs --tail=100 erp`, and Magento `var/log/system.log` |
| Shell says a helper is not executable | Run `chmod +x bin/setup bin/start bin/dev bin/stop bin/magento bin/composer bin/switch-cache` |

After fixing the underlying problem, retry:

```bash
bin/start
```

If `setup:install` itself was interrupted, it may leave partial database/configuration state. Use the reset procedure only if you want to discard that installation's data. An `init` status of **Exited (0)** is normal.

## Reduce local disk usage

Inspect your current usage:

```bash
du -sh src
du -sh src/vendor
docker system df
```

After builds complete, remove unused build cache if you need space:

```bash
docker builder prune -a
```

Review Docker's confirmation before approving. This removes unused build cache; later image rebuilds can take longer. It does not remove the running images, store volumes or local `src/vendor`. Keep vendor locally for IDE indexing. Avoid volume-pruning/reset commands when you want to preserve store data. Counts from `docker system df` include other Docker projects on the same machine.

## Validation commands

Run from the project directory. The first three checks do not create store data:

```bash
docker compose config --quiet
bash -n bin/setup bin/start bin/dev bin/stop bin/magento bin/composer bin/switch-cache docker/entrypoint.sh docker/configure-cache.sh
python3 -m unittest discover -s erp/tests -v
```

The ERP tests require Python 3 on the host. If it is not installed, run the same tests in a temporary Python container; they use a temporary test database, not the running ERP database:

```bash
docker run --rm -v "$PWD/erp:/work:ro" -w /work python:3.13-slim python -m unittest discover -s tests -v
```

With the stack running, check the actual services:

```bash
docker compose ps -a
bin/magento --version
bin/magento setup:db:status
curl -I http://localhost:8090/
curl -fsS http://localhost:8092/health
```

Adjust URLs if you changed ports. To verify both installed cache configurations, run each switch separately and wait for it to finish before the next:

```bash
bin/switch-cache redis
bin/switch-cache valkey
```

Verified locally on Apple Silicon: all three custom images build, Magento installs from an empty database, the storefront/Admin/phpMyAdmin return HTTP 200, and all configured healthchecks pass. Both cache-switching commands complete successfully. ERP logic tests and HTTP checks cover pending/accept/fail behavior, authorization and updates without duplicate entities. A Magento smoke check delivered product, customer and order changes to ERP, then removed its temporary records. The default running configuration was restored to Valkey.

Development mode was also verified with a local vendor tree, live host edits visible in PHP/Nginx, container-created files owned by the host user, writable Composer files, a warm restart without another source copy, preserved store encryption/database configuration, and successful storefront/ERP health requests.
