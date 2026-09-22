# Fase 5 — Operação contínua e preparação para produção

## Entregue

- snapshots persistentes da carteira em `portfolio_snapshots`, separados por moeda;
- registro de valor investido, valor atualizado, resultado, quantidade de posições e cobertura de cotações;
- classificação de cada captura como `complete` ou `partial`;
- consulta `GET /clients/{client_id}/investment-snapshots` com filtro de moeda e limite de registros;
- captura manual `POST /clients/{client_id}/investment-snapshots/capture` no fluxo operacional do Advisor/Admin;
- rotina automática em segundo plano para capturar carteiras ativas;
- intervalo configurável por `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS`, com proteção mínima de cinco minutos;
- painel “Evolução da carteira”, com resumo do último registro, histórico e ação de captura imediata;
- endpoint `/health/ready`, que só responde pronto quando a API e o banco estão acessíveis;
- logs de contagem de clientes, snapshots criados e falhas da rotina automática;
- migração Alembic `0013_create_portfolio_snapshots`;
- cobertura de registro de rotas e modelos nos testes automatizados.

## Operação

1. Aplicar as migrações antes de iniciar a API.
2. Manter `PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS=3600` para uma captura horária em produção, ajustando conforme o limite do provedor de cotações.
3. Usar “Capturar agora” somente quando for necessário registrar uma atualização imediata; capturas repetidas em menos de cinco minutos são deduplicadas.
4. Consultar `/health/ready` no health check do processo ou do container.
5. Acompanhar os logs da API para falhas de provedor, banco ou snapshots parciais.

## Limitações conhecidas

Os snapshots dependem da disponibilidade das fontes de cotação. A carteira mantém BRL e moedas estrangeiras separadas,
sem conversão cambial implícita. Notificações por e-mail, push ou WhatsApp ainda dependem da configuração de um provedor
externo; nesta fase, o histórico e os avisos operacionais ficam disponíveis no sistema e nos logs.
