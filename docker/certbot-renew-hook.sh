#!/bin/sh
set -eu

cd /opt/santehgo
docker compose exec -T nginx nginx -s reload
