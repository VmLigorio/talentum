#!/usr/bin/env bash
set -euo pipefail

umask 077
container_name="${POSTGRES_CONTAINER:-talentum-postgres}"
database_name="${POSTGRES_DB:-talentum}"
database_user="${POSTGRES_USER:-talentum_user}"
backup_dir="${BACKUP_DIR:-./backups}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"

: "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD antes de executar o backup}"
mkdir -p "$backup_dir"
backup_file="$backup_dir/talentum-${database_name}-$(date -u +%Y%m%dT%H%M%SZ).dump"
temporary_file="$(mktemp "$backup_dir/.talentum-${database_name}-XXXXXX.dump")"

cleanup() {
  rm -f -- "$temporary_file"
}
trap cleanup EXIT

docker exec \
  -e "PGPASSWORD=$POSTGRES_PASSWORD" \
  "$container_name" \
  pg_dump --format=custom --no-owner --no-acl --username="$database_user" --dbname="$database_name" \
  > "$temporary_file"

docker exec -i \
  -e "PGPASSWORD=$POSTGRES_PASSWORD" \
  "$container_name" \
  pg_restore --list - < "$temporary_file" > /dev/null

mv -- "$temporary_file" "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"

find "$backup_dir" -type f -name "talentum-${database_name}-*.dump" -mtime "+$retention_days" -delete
find "$backup_dir" -type f -name "talentum-${database_name}-*.dump.sha256" -mtime "+$retention_days" -delete
printf 'Backup criado e validado em %s\n' "$backup_file"
