#!/bin/sh
set -eu

backup_dir="${1:?Użycie: deploy/verify-restore.sh KATALOG_BACKUPU}"
database_name="${MYSQL_DATABASE:-ems}"
suffix="$(date +%s)-$$"
maria_container="internship-restore-mariadb-${suffix}"
mongo_container="internship-restore-mongo-${suffix}"

cleanup() {
    docker rm -f "${maria_container}" "${mongo_container}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

(
    cd "${backup_dir}"
    sha256sum -c SHA256SUMS
)
gzip -t "${backup_dir}/mariadb.sql.gz"
gzip -t "${backup_dir}/mongo.archive.gz"
tar -tzf "${backup_dir}/app-data.tar.gz" >/dev/null

docker run -d --name "${maria_container}" \
    -e MARIADB_ROOT_PASSWORD=restore-test-password mariadb:11 >/dev/null
until docker exec "${maria_container}" \
    mariadb-admin ping -uroot -prestore-test-password --silent; do
    sleep 2
done
gunzip -c "${backup_dir}/mariadb.sql.gz" | docker exec -i "${maria_container}" \
    mariadb -uroot -prestore-test-password
docker exec "${maria_container}" mariadb -uroot -prestore-test-password \
    -e "USE \`${database_name}\`; SHOW TABLES;" >/dev/null

docker run -d --name "${mongo_container}" mongo:7 --noauth >/dev/null
until docker exec "${mongo_container}" \
    mongosh --quiet --eval "db.adminCommand('ping')" >/dev/null; do
    sleep 2
done
cat "${backup_dir}/mongo.archive.gz" | docker exec -i "${mongo_container}" \
    mongorestore --archive --gzip >/dev/null
docker exec "${mongo_container}" mongosh --quiet "${database_name}" \
    --eval "if (db.getCollectionNames().length === 0) { quit(2) }" >/dev/null

printf 'Test odtworzenia zakończony poprawnie: %s\n' "${backup_dir}"
