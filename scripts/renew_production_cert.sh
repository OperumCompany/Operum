#!/bin/sh
set -eu

cd /opt/operum

exec /usr/bin/flock -n /tmp/operum-certbot.lock sh -c '
  docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot nginx renew --quiet --no-random-sleep-on-renew
  docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload
'
