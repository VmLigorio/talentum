#!/usr/bin/env bash
set -euo pipefail

compose_file="docker-compose.production.yml"
env_file=".env.production"

if [[ ! -f "$env_file" ]]; then
  printf 'Arquivo %s não encontrado. Copie .env.production.example e preencha os valores reais.\n' "$env_file" >&2
  exit 1
fi

if grep -Eq 'SUBSTITUA|URL_ENCODE|seudominio|GERE_UM|COLOQUE' "$env_file"; then
  printf 'O arquivo %s ainda contém valores de exemplo.\n' "$env_file" >&2
  exit 1
fi

docker compose --env-file "$env_file" -f "$compose_file" config -q

api_port="$(awk -F= '/^API_BIND_PORT=/{print $2; exit}' "$env_file")"
api_port="${api_port:-8100}"
curl --fail --silent --show-error "http://127.0.0.1:${api_port}/health/ready" > /dev/null

printf 'Pré-verificação de produção concluída: Compose válido e API pronta em 127.0.0.1:%s.\n' "$api_port"
