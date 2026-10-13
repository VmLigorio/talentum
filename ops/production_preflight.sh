#!/usr/bin/env bash
# Talentum — ops/production_preflight.sh
# Responsabilidade: Valida configurações de produção e a prontidão da API local.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
# Interrompe ao primeiro erro e trata variáveis ausentes como falha.
set -euo pipefail

# Usa o manifesto dedicado aos serviços e parâmetros de produção.
compose_file="docker-compose.production.yml"
# O preflight valida este caminho fixo; mantenha-o alinhado ao PRODUCTION_ENV_FILE do Compose.
env_file=".env.production"

# Exige um arquivo de ambiente antes de validar o Compose e consultar a API.
if [[ ! -f "$env_file" ]]; then
  printf 'Arquivo %s não encontrado. Copie .env.production.example e preencha os valores reais.\n' "$env_file" >&2
  exit 1
fi

# Recusa configurações que ainda contenham marcadores de exemplo.
if grep -Eq 'SUBSTITUA|URL_ENCODE|seudominio|GERE_UM|COLOQUE' "$env_file"; then
  printf 'O arquivo %s ainda contém valores de exemplo.\n' "$env_file" >&2
  exit 1
fi

# Confirma que as variáveis formam uma configuração Compose válida.
# Variáveis exportadas no shell podem prevalecer ao arquivo, enquanto a porta abaixo é lida do arquivo bruto (achado 107).
docker compose --env-file "$env_file" -f "$compose_file" config -q

# Confirma que existe exatamente um container da API, pois cada processo inicia seus próprios monitores.
api_container_count="$(docker compose --env-file "$env_file" -f "$compose_file" ps -q api | awk 'NF { count++ } END { print count + 0 }')"
if [[ "$api_container_count" != "1" ]]; then
  printf 'Esperada exatamente uma instância da API; encontradas %s. Não escale a API enquanto os monitores forem locais ao processo.\n' "$api_container_count" >&2
  exit 1
fi

# Lê a porta diretamente do arquivo de ambiente e usa 8100 quando ela não foi definida.
api_port="$(awk -F= '/^API_BIND_PORT=/{print $2; exit}' "$env_file")"
api_port="${api_port:-8100}"
# Limita a espera do preflight quando o serviço está travado ou não alcançável.
curl --connect-timeout 3 --max-time 10 --fail --silent --show-error "http://127.0.0.1:${api_port}/health/ready" > /dev/null

printf 'Pré-verificação de produção concluída: Compose válido e API pronta em 127.0.0.1:%s.\n' "$api_port"
