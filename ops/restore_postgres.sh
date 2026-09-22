#!/usr/bin/env bash
set -euo pipefail

umask 077
container_name="${POSTGRES_CONTAINER:-talentum-postgres}"
database_name="${POSTGRES_DB:-talentum}"
database_user="${POSTGRES_USER:-talentum_user}"
backup_file="${1:-}"

: "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD antes de executar a restauração}"
: "${CONFIRM_RESTORE:?Defina CONFIRM_RESTORE=YES para confirmar a restauração}"

if [[ "$CONFIRM_RESTORE" != "YES" ]]; then
  printf 'Restauração cancelada: use CONFIRM_RESTORE=YES somente após validar o arquivo.\n' >&2
  exit 1
fi

if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
  printf 'Uso: POSTGRES_PASSWORD=... CONFIRM_RESTORE=YES %s arquivo.dump\n' "$0" >&2
  exit 1
fi

if [[ -f "$backup_file.sha256" ]]; then
  sha256sum -c "$backup_file.sha256"
fi

printf 'Atenção: os objetos presentes no backup serão restaurados sobre %s.\n' "$database_name" >&2
docker exec -i \
  -e "PGPASSWORD=$POSTGRES_PASSWORD" \
  "$container_name" \
  pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl \
  --username="$database_user" --dbname="$database_name" < "$backup_file"

printf 'Restauração concluída a partir de %s\n' "$backup_file"
