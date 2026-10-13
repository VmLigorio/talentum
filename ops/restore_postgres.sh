#!/usr/bin/env bash
# Talentum — ops/restore_postgres.sh
# Responsabilidade: Valida um dump e restaura seus objetos no banco indicado.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
# Interrompe diante de erro, variável ausente ou falha em qualquer etapa de um pipeline.
set -euo pipefail

# Define permissões restritivas para eventuais arquivos criados durante a restauração.
umask 077
# Esse nome fixo existe no Compose local; produção precisa informar POSTGRES_CONTAINER.
container_name="${POSTGRES_CONTAINER:-talentum-postgres}"
# Permite informar a conexão lógica do banco e o arquivo dump a restaurar.
database_name="${POSTGRES_DB:-talentum}"
database_user="${POSTGRES_USER:-talentum_user}"
# Recebe como primeiro argumento o caminho do dump que será validado e restaurado.
backup_file="${1:-}"

: "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD antes de executar a restauração}"
: "${CONFIRM_RESTORE:?Defina CONFIRM_RESTORE=YES para confirmar a restauração}"

# Exige confirmação explícita antes de substituir objetos existentes no banco.
if [[ "$CONFIRM_RESTORE" != "YES" ]]; then
  printf 'Restauração cancelada: use CONFIRM_RESTORE=YES somente após validar o arquivo.\n' >&2
  exit 1
fi

# Interrompe a rotina se o caminho do dump estiver ausente ou não existir.
if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
  printf 'Uso: POSTGRES_PASSWORD=... CONFIRM_RESTORE=YES %s arquivo.dump\n' "$0" >&2
  exit 1
fi

# Exige e valida o checksum antes de qualquer operação que altere o banco.
if [[ ! -f "$backup_file.sha256" ]]; then
  printf 'Checksum %s não encontrado; restauração cancelada.\n' "$backup_file.sha256" >&2
  exit 1
fi
(
  cd -- "$(dirname -- "$backup_file")"
  sha256sum --check -- "$(basename -- "$backup_file").sha256"
)

printf 'Atenção: os objetos presentes no backup serão restaurados sobre %s.\n' "$database_name" >&2
# Passa a credencial como variável herdada; o valor não aparece nos argumentos visíveis do Docker CLI.
PGPASSWORD="$POSTGRES_PASSWORD" docker exec -i \
  -e PGPASSWORD \
  "$container_name" \
  pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl \
  --username="$database_user" --dbname="$database_name" < "$backup_file"

printf 'Restauração concluída a partir de %s\n' "$backup_file"
