#!/bin/sh
set -eu

compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
env_file="${ENV_FILE:-.env.production}"
backup_root="${BACKUP_ROOT:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="${backup_root}/${timestamp}"

mkdir -p "${destination}/app-data"

docker compose --env-file "${env_file}" -f "${compose_file}" exec -T db \
    sh -c 'exec mariadb-dump -uroot -p"$MYSQL_ROOT_PASSWORD" --databases "$MYSQL_DATABASE" --single-transaction --routines --events' \
    | gzip > "${destination}/mariadb.sql.gz"

docker compose --env-file "${env_file}" -f "${compose_file}" exec -T mongo \
    sh -c 'exec mongodump --username "$MONGO_APP_USERNAME" --password "$MONGO_APP_PASSWORD" --authenticationDatabase "$MONGO_DATABASE" --db "$MONGO_DATABASE" --archive --gzip' \
    > "${destination}/mongo.archive.gz"

docker compose --env-file "${env_file}" -f "${compose_file}" \
    cp flask:/app/data/. "${destination}/app-data"
tar -czf "${destination}/app-data.tar.gz" -C "${destination}" app-data
rm -rf "${destination}/app-data"

(
    cd "${destination}"
    sha256sum mariadb.sql.gz mongo.archive.gz app-data.tar.gz > SHA256SUMS
)

printf 'Backup zapisany w %s\n' "${destination}"
