#!/usr/bin/env bash
# Talentum — ops/backup_postgres.sh
# Responsabilidade: Gera, valida, identifica e remove backups PostgreSQL vencidos.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
# Interrompe diante de erro, variável ausente ou falha em qualquer etapa de um pipeline.
set -euo pipefail

# Restringe aos usuários autorizados a leitura dos arquivos de backup criados pelo script.
umask 077
# Esse nome fixo existe no Compose local; produção precisa informar POSTGRES_CONTAINER.
container_name="${POSTGRES_CONTAINER:-talentum-postgres}"
# Permite selecionar o banco e, nas linhas seguintes, usuário, diretório e retenção pelo ambiente.
database_name="${POSTGRES_DB:-talentum}"
database_user="${POSTGRES_USER:-talentum_user}"
backup_dir="${BACKUP_DIR:-./backups}"
retention_days="${BACKUP_RETENTION_DAYS:-30}"

: "${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD antes de executar o backup}"
# Garante que o diretório de destino exista antes de criar o dump temporário.
mkdir -p "$backup_dir"
# Usa horário UTC no nome final para facilitar a ordenação dos backups entre servidores.
backup_file="$backup_dir/talentum-${database_name}-$(date -u +%Y%m%dT%H%M%SZ).dump"
# Mantém o temporário no diretório de destino para que a publicação final use o mesmo filesystem.
temporary_file="$(mktemp "$backup_dir/.talentum-${database_name}-XXXXXX.dump")"

# Remove o arquivo temporário caso a rotina termine antes da publicação do backup.
cleanup() {
  rm -f -- "$temporary_file"
}
trap cleanup EXIT

# Grava o dump em caminho temporário para não publicar um backup incompleto.
# Passa a credencial como variável herdada; o valor não aparece nos argumentos visíveis do Docker CLI.
PGPASSWORD="$POSTGRES_PASSWORD" docker exec \
  -e PGPASSWORD \
  "$container_name" \
  pg_dump --format=custom --no-owner --no-acl --username="$database_user" --dbname="$database_name" \
  > "$temporary_file"

# Confirma que o dump pode ser lido antes de movê-lo para o nome definitivo.
# Reutiliza a variável herdada para validar o dump sem expor o valor na linha de comando.
PGPASSWORD="$POSTGRES_PASSWORD" docker exec -i \
  -e PGPASSWORD \
  "$container_name" \
  pg_restore --list < "$temporary_file" > /dev/null

mv -- "$temporary_file" "$backup_file"
# Registra somente o nome do dump para validar o checksum mesmo quando o caminho recebido variar.
(
  cd -- "$backup_dir"
  sha256sum -- "$(basename -- "$backup_file")" > "$(basename -- "$backup_file").sha256"
)

# Aplica o prazo de retenção aos arquivos de backup e seus hashes de validação.
find "$backup_dir" -type f -name "talentum-${database_name}-*.dump" -mtime "+$retention_days" -delete
find "$backup_dir" -type f -name "talentum-${database_name}-*.dump.sha256" -mtime "+$retention_days" -delete
printf 'Backup criado e validado em %s\n' "$backup_file"
